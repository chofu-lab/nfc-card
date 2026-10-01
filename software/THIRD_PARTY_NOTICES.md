# サードパーティのライセンス表示（Third-party notices）

名刺のマイコン（ATtiny816）に書き込むファームウェア `nfc_card.ino` は、Arduino 環境で次のライブラリと一緒にビルドしています。ファームウェアを書き込んだ基板を人に渡すため、それぞれのライセンスが求める表示をここにまとめます。

The firmware `nfc_card.ino` is built with the libraries below. These notices accompany the boards we hand out.

## 配った基板のファームウェア（Distributed firmware）

- タグ `firmware-1` の `software/nfc_card.ino` をビルドしたもの（ファームウェアを変えたときは、新しいタグを打ってここに追記します）
- Built from `software/nfc_card.ino` at tag `firmware-1` (a new tag will be added here whenever the firmware changes).

## ビルドの方法（Build）

- ボード定義: megaTinyCore 2.6.11（Arduino のボードマネージャ。追加の URL は `http://drazzy.com/package_drazzy.com_index.json`）
- コンパイラ: avr-gcc 7.3.0-atmel3.6.1-azduino7b1（megaTinyCore を入れると、依存するツールとして一緒に入ります。AVR-LibC 2.0.0 を含みます）
- FQBN: `megaTinyCore:megaavr:atxy6:chip=816,clock=1internal`
- 書き込み: SerialUPDI（230400 baud、write delay あり）

Arduino のスケッチは「フォルダ名」と「.ino のファイル名」が同じである必要があるので、`nfc_card` という名前のフォルダに `nfc_card.ino` を置いてからビルドします。リポジトリのトップで実行します（`nfc_card/` と `build/` は作業用のフォルダです）。

```
arduino-cli core install megaTinyCore:megaavr@2.6.11 --additional-urls http://drazzy.com/package_drazzy.com_index.json
mkdir nfc_card && cp software/nfc_card.ino nfc_card/
arduino-cli compile -b megaTinyCore:megaavr:atxy6:chip=816,clock=1internal --output-dir build nfc_card
arduino-cli upload -b megaTinyCore:megaavr:atxy6:chip=816,clock=1internal -P serialupdi230k_wd1 -p <シリアルポート> --input-dir build nfc_card
```

## megaTinyCore — GNU LGPL 2.1

ファームウェアには、megaTinyCore 2.6.11 の次のファイルから作られた部分が静的にリンクされています。

- `cores/megatinycore/` の main.cpp・wiring.c・wiring_micros_ISR.h・wiring_digital.c・wiring_analog.c・Arduino.h
- `variants/txy6/pins_arduino.h`

著作権表示（各ファイルの見出しより）:

```
Copyright (c) 2005-2013 Arduino
Copyright (c) 2005-2006, 2007 David A. Mellis
Copyright (c) 2018-2022, 2025 Spence Konde
```

- ライセンスの全文: このフォルダの [`LICENSE-megaTinyCore.md`](LICENSE-megaTinyCore.md)（megaTinyCore 2.6.11 の LICENSE.md の写し。GNU LGPL 2.1 の全文を含みます）
- ソースコード: https://github.com/SpenceKonde/megaTinyCore （タグ 2.6.11）。ビルドに使ったソース一式は、このリポジトリの Release `firmware-1` にも `megaTinyCore-2.6.11.tar.bz2`（SHA-256: `1a2b5827777aa4c61ac5d9e96cf4ad9ebb34a2171a97288349df8eb61636cfb1`）として添付しています

このフォルダの `nfc_card.ino`（GPL-3.0-or-later）と megaTinyCore のソースがあれば、上の方法で同じファームウェアをビルドでき、megaTinyCore を変更してから再リンクすることもできます。

The firmware is statically linked with parts of megaTinyCore 2.6.11, licensed under the GNU LGPL 2.1 (full text in `LICENSE-megaTinyCore.md`). Together with `nfc_card.ino` in this folder and the megaTinyCore source (also attached to the release `firmware-1`), you can rebuild and relink the firmware.

## AVR-LibC 2.0.0 — Modified BSD License

ファームウェアには AVR-LibC 2.0.0（avr-gcc と一緒に入る C ライブラリとスタートアップコード）の一部が含まれます。条件に従い、著作権表示とライセンス条文を以下に掲載します（AVR-LibC 2.0.0 の `LICENSE` より。https://github.com/avrdudes/avr-libc/blob/avr-libc-2_0_0-release/LICENSE ）。

```
The contents of avr-libc are licensed with a Modified BSD License.

All of this is supposed to be Free Software, Open Source, DFSG-free,
GPL-compatible, and OK to use in both free and proprietary applications.

See the license information in the individual source files for details.

Additions and corrections to this file are welcome.

*******************************************************************************
Portions of avr-libc are Copyright (c) 1999-2010
Keith Gudger,
Bjoern Haase,
Steinar Haugen,
Peter Jansen,
Reinhard Jessich,
Magnus Johansson,
Artur Lipowski,
Marek Michalkiewicz,
Colin O'Flynn,
Bob Paddock,
Reiner Patommel,
Michael Rickman,
Theodore A. Roth,
Juergen Schilling,
Philip Soeberg,
Anatoly Sokolov,
Nils Kristian Strom,
Michael Stumpf,
Stefan Swanepoel,
Eric B. Weddington,
Joerg Wunsch,
Dmitry Xmelkov,
The Regents of the University of California.
All rights reserved.

   Redistribution and use in source and binary forms, with or without
   modification, are permitted provided that the following conditions are met:

   * Redistributions of source code must retain the above copyright
     notice, this list of conditions and the following disclaimer.

   * Redistributions in binary form must reproduce the above copyright
     notice, this list of conditions and the following disclaimer in
     the documentation and/or other materials provided with the
     distribution.

   * Neither the name of the copyright holders nor the names of
     contributors may be used to endorse or promote products derived
     from this software without specific prior written permission.

   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
   AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
   IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
   ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
   LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
   CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
   SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
   INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
   CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
   ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
   POSSIBILITY OF SUCH DAMAGE.
```

## GCC のランタイムライブラリ（libgcc）

libgcc は GCC Runtime Library Exception の対象で、ビルドしたファームウェアに表示の義務はありません。
