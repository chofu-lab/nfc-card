#include <avr/sleep.h>


const int powerBypassPin = PIN_PC0;
const int powerLedPin = PIN_PB0;


struct LedMap {
  uint8_t anodeIdx;
  uint8_t cathodeIdx;
};


const LedMap leds[20] = {
  {1, 4}, {4, 1}, {0, 4}, {4, 0}, {0, 1}, {1, 0}, {1, 2}, {2, 1},
  {2, 3}, {3, 2}, {3, 4}, {4, 3}, {0, 2}, {2, 0}, {1, 3}, {3, 1},
  {2, 4}, {4, 2}, {0, 3}, {3, 0}
};


struct LedMasks {
  uint8_t dir_mask;
  uint8_t out_mask;
};
LedMasks ledMasks[20];


// Each frame starts every FRAME_US, the same frame period as the original firmware.
// One LED at a given level has the same brightness and average current as before.
// Total red current still grows with the number of lit LEDs. The CPU sleeps until the next frame.
#define FRAME_US 6000
static_assert(FRAME_US >= 1000 && FRAME_US <= 65536, "FRAME_US must fit TCB0 (1 count = 1 us at 1 MHz)");
static_assert(F_CPU == 1000000UL, "the frame timer and the on-time table assume 1 MHz");
volatile bool frameDue = false;


// LED patterns, played in this order and repeated
#define TICK_MS 25          // the patterns are updated every tick
#define COMET_TICKS 6       // a comet moves by one LED every 6 ticks (150 ms)
#define BLINK_TICKS 12      // the alternating pattern swaps every 12 ticks (300 ms)
#define CHARGE_TICKS 240    // the ring charges up slowly and blinks twice with the power LED (6 s)
#define CHARGE_RAMP_TICKS 208   // charging part (5.2 s), the rest is the two blinks
#define TWINKLE_TICKS 17    // one twinkle fades in and out over this many ticks
#define FLASH_MS 500        // the power LED flashes and fades out over this time at each pattern change
static_assert(FLASH_MS >= 128 && FLASH_MS <= 65535, "FLASH_MS must be 128..65535");
constexpr uint16_t flashFadeK = 127UL * 65536UL / FLASH_MS;


enum Pattern : uint8_t { COMET, TWIN_COMETS, SPINNER, CROSSING, ALTERNATE, FILL, STACK, TWINKLE, CHARGE };


struct Segment {
  Pattern pattern;
  uint16_t ticks;           // length in TICK_MS (240 ticks = 6 s)
};


const Segment playlist[] = {
  {COMET, 240},             // 2 laps
  {TWIN_COMETS, 240},       // 2 laps
  {SPINNER, 240},           // four dots, 2 laps
  {CROSSING, 240},          // the two dots meet four times
  {ALTERNATE, 240},         // 20 blinks
  {FILL, 240},              // fill the ring one by one, then empty it in the same order
  {STACK, 240},             // a dot runs and piles up at the end (210 ticks), then the ring blinks
  {TWINKLE, 240},           // random LEDs fade in and out
  {CHARGE, 240},            // charges up once
};
const uint8_t playlistLength = sizeof(playlist) / sizeof(playlist[0]);


// brightness of each LED as an index into the on-time table (0 = brightest, 16 = dimmest), LED_OFF = dark
#define LED_OFF 0xFF
uint8_t ledLevel[20];


uint8_t segmentIndex = 0;
uint16_t segmentTick = 0;
uint8_t cometTick = 0;
uint16_t frameCounter = 0;
unsigned long tickStartTime = 0;
unsigned long segmentStartTime = 0;
uint8_t powerLevel = 0xFF;
uint8_t patternPowerLevel = 0;   // the power LED level a pattern asks for (CHARGE)


uint8_t twinkleWait[20];    // ticks until the next twinkle of each LED
uint8_t twinklePos[20];     // position in the current twinkle, 0 = not twinkling
uint16_t rngState = 0xACE1;


void setup() {
  // light the power LED right away: a background read from the iPhone home screen (no app)
  // keeps the NFC field on for only about 0.1 s, so in that case this is the only LED that lights up
  pinMode(powerLedPin, OUTPUT);
  analogWrite(powerLedPin, 127);


  // in-rush prevention
  delay(300);


  // enable bypass MOSFET
  pinMode(powerBypassPin, OUTPUT);
  digitalWrite(powerBypassPin, LOW);



  // pre-calculate hardware bitmasks
  for (int i = 0; i < 20; i++) {
    uint8_t aMask = (1 << (leds[i].anodeIdx + 1));
    uint8_t cMask = (1 << (leds[i].cathodeIdx + 1));
    ledMasks[i].dir_mask = aMask | cMask;
    ledMasks[i].out_mask = aMask;
  }


  PORTB.DIRCLR = 0x3E;


  // frame timer: TCB0 periodic interrupt, 1 count = 1 us at 1 MHz
  TCB0.CCMP = FRAME_US - 1;
  TCB0.CTRLB = TCB_CNTMODE_INT_gc;
  TCB0.INTCTRL = TCB_CAPT_bm;
  TCB0.CTRLA = TCB_CLKSEL_CLKDIV1_gc | TCB_ENABLE_bm;
  set_sleep_mode(SLEEP_MODE_IDLE);


  startSegment();
  uint32_t startupStart = millis();


  while (true) {
    uint32_t elapsed = millis() - startupStart;
    if (elapsed >= 300) break;
    waitFrame();
    // The counter has just restarted, so it is below the new limit.
    TCB0.CCMP = FRAME_US - 1 + (uint16_t)(300 - elapsed) * 25;   // a longer frame is dimmer: 13.5 ms -> 6 ms
    renderFrame(0);
  }
  // Only one render (~1.3 ms) has elapsed, so restoring the 6 ms limit is safe.
  TCB0.CCMP = FRAME_US - 1;


  // the power LED fades out like a pattern change flash
  tickStartTime = millis();
  segmentStartTime = tickStartTime;
}


void loop() {
  waitFrame();
  unsigned long now = millis();


  if (now - tickStartTime >= TICK_MS) {
    tickStartTime += TICK_MS;
    if (++cometTick >= COMET_TICKS) cometTick = 0;


    if (++segmentTick >= playlist[segmentIndex].ticks) {
      if (++segmentIndex >= playlistLength) {
        segmentIndex = 0;
      }
      segmentStartTime = now;
      startSegment();
    } else {
      updateLevels();
    }


    if (cometTick == 0) {
      frameCounter = 0;
    }
  }


  // time since the comet moved, for fading out the end of its tail
  uint16_t msInStep = cometTick * TICK_MS + (uint16_t)(now - tickStartTime);
  renderFrame(msInStep);
  frameCounter++;


  updatePowerLed(now);
}


ISR(TCB0_INT_vect) {
  TCB0.INTFLAGS = TCB_CAPT_bm;
  frameDue = true;
}


// sleep (IDLE) until the next frame starts. Interrupts are re-enabled right before sleep_cpu(),
// so a frame interrupt cannot slip in between the check and going to sleep
void waitFrame() {
  cli();
  while (!frameDue) {
    sleep_enable();
    sei();
    sleep_cpu();
    sleep_disable();
    cli();
  }
  frameDue = false;
  sei();
}


void startSegment() {
  segmentTick = 0;
  cometTick = 0;


  for (uint8_t i = 0; i < 20; i++) {
    twinkleWait[i] = random8() % 40;
    twinklePos[i] = 0;
  }


  updateLevels();
}


// recalculate ledLevel[] once per tick
void updateLevels() {
  Pattern pattern = playlist[segmentIndex].pattern;
  uint8_t step = segmentTick / COMET_TICKS;
  uint8_t head = step % 20;


  // STACK: find how many LEDs have piled up and where the running dot is
  uint8_t stacked = 0;
  uint8_t dot = LED_OFF;
  bool stackLit = false;
  if (pattern == STACK) {
    uint16_t t = segmentTick;
    while (stacked < 20 && t >= (uint8_t)(20 - stacked)) {
      t -= 20 - stacked;
      stacked++;
    }
    if (stacked < 20) {
      dot = t;
    } else {
      stackLit = t < 24 && (t / 6) % 2 == 0;   // blink twice when full, then go dark
    }
  }


  // CHARGE: the whole ring brightens (the on-time table is roughly exponential, so stepping
  // the level linearly looks like a smooth fade), then blinks twice together with the power LED
  uint8_t chargeLevel = LED_OFF;
  patternPowerLevel = 0;
  if (pattern == CHARGE) {
    uint8_t c = segmentTick % CHARGE_TICKS;
    if (c < CHARGE_RAMP_TICKS) {
      if (c >= 4) chargeLevel = 16 - (c - 4) * 16 / (CHARGE_RAMP_TICKS - 5);
    } else if ((c - CHARGE_RAMP_TICKS) / 8 % 2 == 0) {
      chargeLevel = 0;
      patternPowerLevel = 127;
    }
  }


  uint8_t blinkPhase = (segmentTick / BLINK_TICKS) & 1;


  // no divisions inside this loop: it runs every tick at 1 MHz
  for (uint8_t i = 0; i < 20; i++) {
    uint8_t d1 = head >= i ? head - i : head + 20 - i;   // behind the head that moves to higher indexes
    uint8_t level = LED_OFF;


    switch (pattern) {
      case COMET:
        if (d1 < 17) level = d1;
        break;


      case TWIN_COMETS: {
        uint8_t d2 = d1 >= 10 ? d1 - 10 : d1 + 10;           // second head on the opposite side
        uint8_t d = d1 < d2 ? d1 : d2;
        if (d < 8) level = d;
        break;
      }


      case SPINNER: {
        uint8_t d = d1;                    // behind the nearest of four heads 5 LEDs apart
        while (d >= 5) d -= 5;
        if (d < 4) level = d * 3;
        break;
      }


      case CROSSING: {
        uint8_t d2 = i + head >= 20 ? i + head - 20 : i + head;   // behind a head that moves to lower indexes
        uint8_t d = d1 < d2 ? d1 : d2;
        if (d < 6) level = d;
        break;
      }


      case ALTERNATE:
        if ((i & 1) == blinkPhase) level = 0;
        break;


      case FILL:
        if (step < 20 ? i <= step : i > step - 20) level = 0;
        break;


      case STACK:
        if (stacked < 20 ? (i >= 20 - stacked || i == dot) : stackLit) level = 0;
        break;


      case TWINKLE:
        if (twinklePos[i] > 0) {
          uint8_t p = twinklePos[i] - 1;   // 0 .. TWINKLE_TICKS - 1: dim -> bright -> dim
          level = (p < 8 ? 8 - p : p - 8) * 2;
          if (++twinklePos[i] > TWINKLE_TICKS) {
            twinklePos[i] = 0;
            twinkleWait[i] = 15 + random8() % 50;
          }
        } else if (twinkleWait[i] > 0) {
          twinkleWait[i]--;
        } else {
          twinklePos[i] = 1;
        }
        break;


      case CHARGE:
        level = chargeLevel;
        break;
    }


    ledLevel[i] = level;
  }
}


void renderFrame(uint16_t msInStep) {
  bool fadeTailEnd = playlist[segmentIndex].pattern == COMET;


  for (uint8_t i = 0; i < 20; i++) {
    uint8_t level = ledLevel[i];


    if (level == LED_OFF) {
      continue;
    }


    // the end of the long comet tail fades out over the step
    if (level == 16 && fadeTailEnd) {
      if (msInStep >= COMET_TICKS * TICK_MS * 50 / 67) continue;
      else if (msInStep >= COMET_TICKS * TICK_MS * 34 / 67 && (frameCounter & 3) != 0) continue;
      else if (msInStep >= COMET_TICKS * TICK_MS * 17 / 67 && (frameCounter & 1) != 0) continue;
    }


    uint8_t dm = ledMasks[i].dir_mask;
    uint8_t om = ledMasks[i].out_mask;


    PORTB.OUTCLR = dm;
    PORTB.OUTSET = om;
    PORTB.DIRSET = dm;


    switch (level) {
      case 0:
      case 1:
      case 2:  __builtin_avr_delay_cycles(100); break;
      case 3:  __builtin_avr_delay_cycles(70);  break;
      case 4:  __builtin_avr_delay_cycles(48);  break;
      case 5:  __builtin_avr_delay_cycles(32);  break;
      case 6:  __builtin_avr_delay_cycles(22);  break;
      case 7:  __builtin_avr_delay_cycles(15);  break;
      case 8:  __builtin_avr_delay_cycles(10);  break;
      case 9:  __builtin_avr_delay_cycles(7);   break;
      case 10: __builtin_avr_delay_cycles(5);   break;
      case 11: __builtin_avr_delay_cycles(4);   break;
      case 12: __builtin_avr_delay_cycles(3);   break;
      case 13: __builtin_avr_delay_cycles(2);   break;
      case 14: __builtin_avr_delay_cycles(1);   break;
      case 15: __builtin_avr_delay_cycles(1);   break;
      case 16: __builtin_avr_delay_cycles(1);   break;
    }


    PORTB.DIRCLR = dm;
  }
}


// flash the power LED at each pattern change and let it fade out
void updatePowerLed(unsigned long now) {
  unsigned long since = now - segmentStartTime;
  uint8_t level = 0;


  if (since < FLASH_MS) {
    uint16_t r = 127 - (((uint32_t)(uint16_t)since * flashFadeK) >> 16);
    level = (r * r) >> 7;   // fades softly
  }
  if (patternPowerLevel > level) {
    level = patternPowerLevel;
  }


  if (level != powerLevel) {
    analogWrite(powerLedPin, level);
    powerLevel = level;
  }
}


// 16-bit Galois LFSR for the twinkles
uint8_t random8() {
  uint8_t lsb = rngState & 1;
  rngState >>= 1;
  if (lsb) rngState ^= 0xB400;
  return rngState;
}
