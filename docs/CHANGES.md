# 元の設計（WiHarper/nfc_card @752793d）からの変更履歴

CERN-OHL-S v2 の 3.3(b) に基づき、元の設計からの変更点を記録します。

## 2026-09-16

- 元リポジトリ（752793d）から `hardware/`・`software/`・`LICENSE.md` を引き継ぎ。`gallery/`（元の作者の名刺の写真・動画）と KiCad の一時ファイル（`*.kicad_sch-bak`・`*.kicad_prl`）は削除し、README は置き換え
- 基板ファイル（`.kicad_pcb`）を KiCad 10.0.3 で保存し、KiCad 10 形式になった（KiCad 9 では開けない）。回路図（`.kicad_sch`）は KiCad 9 形式のまま
- 外形・アンテナ・部品配置・配線は変更なし
- 表裏のシルクとレジストの図形を差し替え（`scripts/artwork.py`、素材は `artwork/`）
  - 削除: 元の作者の氏名・連絡先・QR コード・ブロック図・"Made by" 表記（基板上の図形。フットプリント内の図形は残す）
  - 残したもの: アンテナの銅箔を見せる F.Mask の抜き、NFC アイコン（QR コードの上へ移動）
  - 意図せず消えたもの: 電源 LED（LED22）横の稲妻マーク。`artwork.py` で残す範囲の判定（中心 x < 123 mm）に対し、図形の中心が x ≒ 123.05 mm で、範囲から外れていた。発注した基板にも入っていない
  - 表に追加: ロゴ、chofu-lab.com、肩書と氏名、キャラクター（ちょふまる）、QR コード（https://chofu-lab.com/）
  - 裏に追加: ロゴ、キャラクター、キャッチコピー、URL、「スマホをかざすと光ります」、出典表記 "Based on WiHarper/nfc_card (CERN-OHL-S v2 / GPL-3.0)"
  - 部品の参照記号（D1、U1 など）はシルクに出さない（`scripts/hide_refs.py`）
- 基板色を白レジスト・黒シルク前提に。QR コードは暗いセルをシルクで塗る（`artwork.py` の `DARK_BOARD = False`）。OpenCV で読み取れることを確認
- 回路図: R4 に LCSC 番号 C25076 を追加（元の設計では空欄で、BOM に抜けが出ていた）
- 製造データ `hardware/fab/` を追加（ガーバー、BOM、部品配置）
  - アンテナ AE1 と UPDI パッド J1 は実装部品ではないので BOM・部品配置から除外（13 品目 37 点）
  - KiCad の CSV は JLCPCB で読み込めなかったため、JLCPCB の書式に合わせた `bom_jlcpcb.csv`・`positions_jlcpcb.csv` を追加

## 2026-09-18

- シルクの文字を、KiCad のストロークフォントからフォントの輪郭（多角形）に変更（`scripts/text2json.py`、`artwork.py` の `place_text()`）
  - 日本語: ヒラギノ角ゴシック W6、英語: Museo Sans 700
  - 最も細い線は約 0.12 mm で、標準シルクの下限（0.15 mm）を下回るため、高精度シルク（下限 0.1 mm）で発注する
- キャラクターとロゴの輪郭を、拡大 → ぼかし → 二値化 → potrace の手順で滑らかに再抽出（`scripts/art2json.py`）
- 検証: 銅箔・レジスト・外形・ドリルのガーバーは変更前と一致。DRC は既知の誤検出 4 件のみ（アンテナ図形とそのパッドの重なり。元の設計でも同じ）

## 2026-09-21

- C1 の LCSC 番号を C1639 から C1552 に変更
  - 元の設計の回路図では、C1 のフットプリントが `C_0402_1005Metric`（0402）なのに、LCSC 番号は C1639（FH 0603CG1R5C500NT、0603）になっていた。JLCPCB の実装審査で「部品がパッドより大きい」と指摘された
  - C1552（FH 0402CG1R5C500NT、1.5pF ±0.25pF、C0G、50V、0402）は同じメーカー・同じシリーズのサイズ違いで、電気的な仕様は同じ
  - 回路図の LCSC 欄と `hardware/fab/bom.csv`・`bom_jlcpcb.csv` を更新。ガーバー・部品配置は変更なし
- BOM の残り 12 品目は、LCSC のパッケージ情報とフットプリントを照合して一致を確認

## 2026-09-30

- 公開に向けて整理
  - `hardware/bom/ibom.html`（元の設計のシルクのまま）と、古い製造データの zip を削除
  - 使っていない素材（`artwork/mark-chip.svg`・`mark.json`・`wordmark-h-en-makinas.svg`）を削除
  - 基板ファイル内の部品情報を回路図に合わせた（C1 の LCSC 欄を C1639 → C1552、R4 に LCSC 欄 C25076 を追加。非表示のフィールドだけで、ガーバーは全層変わらないことを確認）
  - `artwork/`・`docs/`・`scripts/` のライセンス、この設計の置き場所（Source Location）、ロゴ・キャラクターの扱いを `LICENSE.md` に追記
  - README の画像（`docs/images/`、KiCad の 3D ビュー）を追加

## 2026-10-01

- ファームウェア（`software/nfc_card.ino`）: 電源 LED（LED22）が起動の 10 秒後から点滅させるモールス信号の文字列を、元の作者のサイト名 "WILSONHARPER.NET" から "CHOFU-LAB.COM" に変更。変えたのは `morseSequence` の配列だけで、符号の長さ・間隔の決め方（短点 1・長点 3・符号間 1・文字間 3・最後に 7 単位、1 単位 170 ms）は元のまま
- ファームウェア: 電源 LED（黄、LED22）を、電源が入った直後に点けるように変更。元の設計では起動から 0.3 秒待ってから 0.3 秒かけてフェードインしていたため、読み取りが約 0.1 秒で終わる iPhone（待ち受け中の読み取り）では何も光らなかった。赤の LED（外周 20 個）の起動の演出（0.3 秒待ってからフェードイン）と、突入電流対策の待ち時間（0.3 秒後に Q1 をオン）は元のまま。ただし、その 0.3 秒間（C3 を R3 経由で充電している間）も黄色の LED（R8 220Ω）に電流が流れるようになった（元の設計では、この間 LED は消えていた）
- ファームウェア: ビルドに使う megaTinyCore（LGPL 2.1）と AVR-LibC 2.0.0（修正 BSD）のライセンス表示を `software/THIRD_PARTY_NOTICES.md` に、megaTinyCore 2.6.11 の LICENSE.md の写しを `software/LICENSE-megaTinyCore.md` に追加
