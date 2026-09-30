"""シルクの文字列を本物のフォント（アウトライン）で描くための前処理。
Pillow で文字を高解像度 PBM に描画 → potrace で geojson 化 → artwork/text/<key>.json に保存。
artwork.py の place_text() がこの json を読んで多角形として基板に置く（KiCad のストロークフォントは使わない）。

使い方（Pillow が入った Python で）:
  python3 scripts/text2json.py            # 全テキストを生成
  python3 scripts/text2json.py --jp <font.ttc> --en <font.otf> [--out <dir>]   # フォント差し替え・出力先変更

h_mm の意味: 日本語行は漢字・かなの字面高さ、英語行はキャップハイト（KiCad の文字高さと同じ感覚で指定できるようにする）。
"""
import argparse, json, os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'artwork', 'text')
PX = 100  # px / mm
JP_FONT = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'
EN_FONT = '/Library/Fonts/exljbris - MuseoSans-700.ttf'
REF = {'jp': '国', 'en': 'H'}  # 高さの基準字: 日本語は漢字の字面、英語はキャップハイト（フォントごとに実測するので比率の手入力は不要）

# key: (text, lang, h_mm)  h_mm は artwork.py 側の従来の文字高さと同じ値
TEXTS = {
    'f-url':   ('chofu-lab.com', 'en', 2.4),
    'f-title': ('代表', 'jp', 1.7),
    'f-name':  ('山本 雄斗', 'jp', 3.4),
    'b-catch': ('あなたのチームの、組込み担当。', 'jp', 2.6),
    'b-list':  ('回路 ・ 基板 ・ ファームウェア ・ 装置の見える化', 'jp', 1.5),
    'b-url':   ('chofu-lab.com', 'en', 2.0),
    'b-nfc':   ('スマホをかざすと光ります ・ 連絡先も入ります', 'jp', 1.3),
    'b-lic':   ('Based on WiHarper/nfc_card (CERN-OHL-S v2 / GPL-3.0)', 'en', 0.95),
}

def render(key, text, lang, h_mm, jp_font, en_font):
    path = jp_font if lang == 'jp' else en_font
    f1k = ImageFont.truetype(path, 1000); bx = f1k.getbbox(REF[lang], anchor='ls')  # 基準字の字面（y は下向き、baseline=0）
    ratio = (bx[3] - bx[1]) / 1000.0                 # 字面高さ / em
    center_off = -(bx[1] + bx[3]) / 2 / 1000.0       # baseline から字面中心までの高さ [em]（上向き正）
    size = h_mm * PX / ratio                         # em サイズ [px]
    font = ImageFont.truetype(path, int(round(size)))
    asc, desc = font.getmetrics()
    margin = int(size * 0.3)
    width = int(font.getlength(text)) + 2 * margin
    height = asc + desc + 2 * margin
    img = Image.new('1', (width, height), 1)
    d = ImageDraw.Draw(img)
    baseline = margin + asc
    d.text((margin, baseline), text, font=font, fill=0, anchor='ls')
    center_from_top = baseline - center_off * size   # artwork.py の y（字面中心）に合わせる
    with tempfile.NamedTemporaryFile(suffix='.pbm', delete=False) as t:
        img.save(t.name)
        out = os.path.join(OUT, key + '.json')
        subprocess.run(['potrace', '-b', 'geojson', '-t', '2', '-a', '1.0', '-O', '0.2', '-o', out, t.name], check=True)
        os.unlink(t.name)
    g = json.load(open(out))
    g['meta'] = {'text': text, 'font': os.path.basename(path), 'px_per_mm': PX, 'img_h': height, 'left_px': margin,
                 'center_from_top_px': center_from_top, 'h_mm': h_mm}
    json.dump(g, open(out, 'w'), ensure_ascii=False)
    print('%-8s %-14s h=%.2f em=%.0fpx width=%.1fmm polys=%d' % (key, os.path.basename(path)[:14], h_mm, size, (width - 2 * margin) / PX, len(g['features'])))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--jp', default=JP_FONT); ap.add_argument('--en', default=EN_FONT)
    ap.add_argument('--out', default=OUT)
    a = ap.parse_args(); OUT = a.out
    os.makedirs(OUT, exist_ok=True)
    for key, (text, lang, h) in TEXTS.items():
        render(key, text, lang, h, a.jp, a.en)
