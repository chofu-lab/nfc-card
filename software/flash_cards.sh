#!/bin/bash
# 名刺のファームウェアを何枚も続けて書き込む（macOS + SerialUPDI のアダプタ）
#
#   ./software/flash_cards.sh                  # アダプタのポートは自動で探す
#   ./software/flash_cards.sh /dev/cu.usbserial-XXXX
#
# 最初に software/nfc_card.ino を 1 回だけビルドし、あとは
# 「基板をクリップではさむ → Enter → 書き込みと照合」を繰り返す。q で終了。
# アダプタは 3.3V で使う（NFC チップ NT3H2111 の VCC の上限は 3.6V）。
set -u

FQBN="megaTinyCore:megaavr:atxy6:chip=816,clock=1internal"
PROGRAMMER="serialupdi230k_wd1"   # SerialUPDI 230400 baud、write delay あり

CLI=$(command -v arduino-cli || true)
[ -z "$CLI" ] && CLI="/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli"
[ -x "$CLI" ] || { echo "arduino-cli が見つかりません（Arduino IDE か arduino-cli を入れてください）"; exit 1; }

REPO=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -r "$WORK"' EXIT

# Arduino のスケッチは「フォルダ名 = .ino の名前」が必要なので、作業用のフォルダにコピーしてビルドする
mkdir "$WORK/nfc_card" && cp "$REPO/software/nfc_card.ino" "$WORK/nfc_card/"
echo "ビルド中..."
"$CLI" compile -b "$FQBN" --output-dir "$WORK/build" "$WORK/nfc_card" >/dev/null || { echo "ビルドに失敗しました"; exit 1; }
echo "ビルド完了: $(cd "$REPO" && git describe --tags --always --dirty 2>/dev/null)"

PORT=${1:-$(ls /dev/cu.usbserial-* 2>/dev/null | head -1)}
[ -z "$PORT" ] && { echo "UPDI アダプタが見つかりません。USB を挿し直してください"; exit 1; }
echo "アダプタ: $PORT"

ok=0
while true; do
  printf '\n基板をはさんで Enter（q で終了）: '
  read -r a
  [ "$a" = q ] && break
  out=$("$CLI" upload -b "$FQBN" -P "$PROGRAMMER" -p "$PORT" --input-dir "$WORK/build" "$WORK/nfc_card" 2>&1)
  if echo "$out" | grep -q 'Verify successful'; then
    ok=$((ok + 1))
    printf '\a\033[32m✔ 成功（この回 %d 枚目）\033[0m LED が回るのを確かめて外してください\n' "$ok"
  else
    printf '\a\033[31m✘ 失敗\033[0m ピンの当たりを確かめて、もう一度 Enter\n'
    echo "$out" | grep -iE 'error|fail|timeout' | tail -3
  fi
done
echo "成功: ${ok} 枚"
