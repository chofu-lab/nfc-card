"""表裏のシルク／レジスト図形を差し替える（調布組込みラボ版）。
使い方: hardware/ で、元設計の基板ファイル（WiHarper/nfc_card @752793d、KiCad 9 形式、外形 85.45×54.08）を取得してから KiCad 同梱 Python で実行し、続けて hide_refs.py を実行
  curl -L -o "Business Card v2.kicad_pcb" "https://raw.githubusercontent.com/WiHarper/nfc_card/752793dcc3164dadf245cb0bc9e7e368e9c0e78e/hardware/Business%20Card%20v2.kicad_pcb"
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 ../scripts/artwork.py
前提: artwork/*.json は potrace -b geojson の出力（画素座標、y 上向き）。
"""
import json, os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, '..', 'artwork')
FN = sys.argv[1] if len(sys.argv) > 1 else 'Business Card v2.kicad_pcb'
TEXT_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ART, 'text')  # text2json.py の出力（本物のフォントで描いた文字）
DARK_BOARD = False  # True: 黒レジスト＋白シルク（QR は明セルをシルクで塗る）／False: 白レジスト＋黒シルク（QR は暗セルをシルクで塗る）
mm = pcbnew.FromMM

b = pcbnew.LoadBoard(FN)
bb = b.GetBoardEdgesBoundingBox()
CX = (bb.GetX() + bb.GetWidth() / 2) / 1e6  # 基板中心 X（裏面ミラー用）

# 1. 既存の基板図形（作者のアート）を F.SilkS / B.SilkS / F.Mask / B.Mask から削除（フットプリント内の図形は残す）
#    ただし残すもの: F.Mask（アンテナ銅箔を露出させるレジスト抜き。元設計の意匠）、電源 LED 横の稲妻マーク。
#    NFC アイコンは一度消して、artwork/nfc-icon.json の座標で描き直す
kill = {b.GetLayerID(n) for n in ('F.SilkS', 'B.SilkS', 'B.Mask')}
def center(d):
    bb = d.GetBoundingBox(); return (bb.GetX() + bb.GetWidth() / 2) / 1e6, (bb.GetY() + bb.GetHeight() / 2) / 1e6
def in_box(d, x0, y0, x1, y1):
    cx, cy = center(d); return x0 < cx < x1 and y0 < cy < y1
removed = 0
for d in list(b.GetDrawings()):
    if d.GetLayer() not in kill: continue
    if d.GetLayer() == b.GetLayerID('F.SilkS') and type(d).__name__ == 'PCB_SHAPE' and in_box(d, 118, 106, 123, 111): continue  # 稲妻マーク（注意: 稲妻の中心は x≒123.05 でこの範囲から外れ、実際には消える。発注した基板もこの状態）
    b.Remove(d); removed += 1
# NFC アイコン（元データ表シルクの 7 多角形）は artwork/nfc-icon.json（座標 mm、元位置 x 146..158 y 110..118）から読む。同一プロセスで 2 つ目の基板を開くと swig が壊れるため
icon_rings = json.load(open(os.path.join(ART, 'nfc-icon.json')))
print('removed drawings:', removed, '/ nfc icon polygons:', len(icon_rings))

def add_poly(rings_mm, layer):
    """rings_mm: [[(x,y),...] outer, holes...] を塗り多角形として追加"""
    poly = pcbnew.SHAPE_POLY_SET()
    for i, ring in enumerate(rings_mm):
        chain = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in ring:
            chain.Append(pcbnew.VECTOR2I(mm(x), mm(y)))
        chain.SetClosed(True)
        if i == 0: idx = poly.AddOutline(chain)
        else: poly.AddHole(chain, idx)
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_POLY); s.SetLayer(b.GetLayerID(layer))
    s.SetPolyShape(poly); s.SetFilled(True); s.SetWidth(0); b.Add(s)

def place_art(name, layer, x0, y0, height, back=False, min_area=0, min_island_mm2=0.0, min_hole_mm2=0.0):
    """geojson の図形を、左上 (x0,y0) から高さ height[mm] で配置。back=True で X ミラー（裏から正しく読める向き）
    min_area: 破片除去のしきい値（元画像の画素^2、旧仕様）。min_island_mm2 / min_hole_mm2: 配置後の mm^2 で、それより小さい島・穴を捨てる
    （小さい元画像の模様が 0.1mm 角の穴や点になり、シルクではゴミ・掠れに見えるため。2026-09-18）"""
    fs = json.load(open(os.path.join(ART, name + '.json')))['features']
    pts = [p for f in fs for r in f['geometry']['coordinates'] for p in r]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    sc = height / (max(ys) - min(ys)); width = (max(xs) - min(xs)) * sc
    def ring_area(r): return abs(sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r)))) / 2
    dropped = [0, 0]
    for f in fs:
        if ring_area(f['geometry']['coordinates'][0]) < min_area: continue  # 二値化の破片（元画像の動線など）を捨てる
        if ring_area(f['geometry']['coordinates'][0]) * sc * sc < min_island_mm2: dropped[0] += 1; continue
        rings = []
        for r in f['geometry']['coordinates']:
            if r is not f['geometry']['coordinates'][0] and ring_area(r) * sc * sc < min_hole_mm2: dropped[1] += 1; continue
            ring = []
            for px, py in r:
                x = x0 + (px - min(xs)) * sc
                y = y0 + (max(ys) - py) * sc  # 画像は y 上向き → 基板は y 下向き
                if back: x = 2 * CX - x
                ring.append((x, y))
            rings.append(ring)
        add_poly(rings, layer)
    if dropped[0] or dropped[1]: print('%s: dropped islands %d, holes %d' % (name, dropped[0], dropped[1]))
    return width

def add_text(text, layer, x, y, h, thick, back=False, bold=False, halign='left'):
    t = pcbnew.PCB_TEXT(b); t.SetText(text); t.SetLayer(b.GetLayerID(layer))
    t.SetTextSize(pcbnew.VECTOR2I(mm(h), mm(h))); t.SetTextThickness(mm(thick)); t.SetBold(bold)
    if back: x = 2 * CX - x
    t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    t.SetHorizJustify({'left': pcbnew.GR_TEXT_H_ALIGN_LEFT, 'center': pcbnew.GR_TEXT_H_ALIGN_CENTER, 'right': pcbnew.GR_TEXT_H_ALIGN_RIGHT}[halign])
    t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    t.SetMirrored(back)
    b.Add(t)

def place_text(key, layer, x0, yc, back=False):
    """text2json.py が作った文字の多角形を、左端 x0・字面中心 yc [mm] に置く（ストロークフォントの add_text と同じ座標感覚）"""
    g = json.load(open(os.path.join(TEXT_DIR, key + '.json'))); m = g['meta']; px = m['px_per_mm']
    for f in g['features']:
        rings = []
        for r in f['geometry']['coordinates']:
            ring = []
            for X, Y in r:
                x = x0 + (X - m['left_px']) / px
                y = yc + ((m['img_h'] - Y) - m['center_from_top_px']) / px  # geojson は y 上向き → 画像 y 下向き → 基板
                if back: x = 2 * CX - x
                ring.append((x, y))
            rings.append(ring)
        add_poly(rings, layer)
    return len(g['features'])

def add_qr(url, layer, x0, y0, size, back=False):
    """QR を配置。暗い基板＋白シルク前提で「明るいセル＋余白」をシルクで塗り、暗モジュールを基板色で残す"""
    sys.path.insert(0, '/Applications/KiCad/KiCad.app/Contents/SharedSupport/scripting/plugins')
    import kicad_qrcode
    qr = kicad_qrcode.QRCode(); qr.setTypeNumber(2); qr.setErrorCorrectLevel(kicad_qrcode.ErrorCorrectLevel.M)
    qr.addData(url); qr.make(); n = qr.getModuleCount(); quiet = 2
    cell = size / (n + 2 * quiet)
    def rect(cx0, cy0, cx1, cy1):
        if back: cx0, cx1 = 2 * CX - cx1, 2 * CX - cx0
        add_poly([[(cx0, cy0), (cx1, cy0), (cx1, cy1), (cx0, cy1)]], layer)
    e = 0.005  # セル間の髪の毛隙間を防ぐ重ね
    if DARK_BOARD:  # 余白 4 辺（黒基板では余白もシルクで白くする。白基板では基板色のままで良い）
        rect(x0, y0, x0 + size, y0 + quiet * cell + e); rect(x0, y0 + size - quiet * cell - e, x0 + size, y0 + size)
        rect(x0, y0, x0 + quiet * cell + e, y0 + size); rect(x0 + size - quiet * cell - e, y0, x0 + size, y0 + size)
    for r in range(n):
        c = 0
        while c < n:  # 明るいセルの連続を 1 矩形にまとめる
            if qr.isDark(r, c) == DARK_BOARD: c += 1; continue   # 塗らないセルを飛ばす
            c0 = c
            while c < n and qr.isDark(r, c) != DARK_BOARD: c += 1
            rect(x0 + (quiet + c0) * cell - e, y0 + (quiet + r) * cell - e, x0 + (quiet + c) * cell + e, y0 + (quiet + r + 1) * cell + e)
    print('QR modules', n, 'cell %.3f mm' % cell)

# ---- 表（F.SilkS）: LED の内側 x 130.5..183.5, y 81.5..113.5 ----
w = place_art('wordmark', 'F.SilkS', 131.0, 82.5, 8.0); print('wordmark width %.1f' % w)
place_text('f-url', 'F.SilkS', 131.2, 94.2)
place_text('f-title', 'F.SilkS', 131.2, 102.4)
place_text('f-name', 'F.SilkS', 131.2, 106.6)  # 高さ 3.4・幅 約 16.5mm → 右端 148（ちょふまる 152 の手前）。左列を右列（QR 下端 112.5）と釣り合う位置まで下げた
# チップマークは載せない（判断 2026-09-16）
w = place_art('labomaru', 'F.SilkS', 152.0, 98.5, 14.0, min_area=2000, min_island_mm2=0.05, min_hole_mm2=0.02)  # QR と上下端を揃える（96.5..112.5）; print('labomaru width %.1f' % w)  # 名前「山本 雄斗」と重ならないよう少し下へ
add_qr('https://chofu-lab.com/', 'F.SilkS', 167.0, 96.5, 16.0)
if icon_rings:
    pts = [p for rings in icon_rings for r in rings for p in r]
    icx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2; icy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    print('nfc icon size %.1f x %.1f mm' % (max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts)))
    for rings in icon_rings:
        add_poly([[(x - icx + 173.0, y - icy + 92.6) for x, y in r] for r in rings], 'F.SilkS')
# ---- 裏（B.SilkS）: 裏から見た座標 u で指定し X ミラー。使える範囲 u 122..176（周囲のリング配線は u≈118〜120、176 以降は MCU 裏の配線）。ブロック幅 約 46mm を中央（152）に置く。
#      普通の名刺の裏面らしく「ロゴ＋宣伝」。社名は文字ではなくワードマークで（判断 2026-09-16）。
#      文字は text2json.py で本物のフォント（ヒラギノ角ゴ W6 / Museo Sans 700）を多角形化したものを置く（2026-09-18、ストロークフォントは不採用）。1 行 ≦ 約 46mm ----
w = place_art('wordmark', 'B.SilkS', 129.0, 83.5, 6.8, back=True); print('back wordmark width %.1f' % w)
w = place_art('labomaru-idea', 'B.SilkS', 167.5, 82.3, 9.5, back=True, min_island_mm2=0.05, min_hole_mm2=0.02); print('back labomaru width %.1f' % w)  # 右上（UPDI パッドの下、キャッチコピーの右上）
place_text('b-catch', 'B.SilkS', 129.2, 95.0, back=True)
place_text('b-list', 'B.SilkS', 129.2, 99.6, back=True)
place_text('b-url', 'B.SilkS', 129.2, 103.9, back=True)
place_text('b-nfc', 'B.SilkS', 129.2, 107.6, back=True)  # メールは NFC の飛び先ページ（vCard）で渡す
place_text('b-lic', 'B.SilkS', 129.2, 110.8, back=True); print('back texts ok')

# 参照記号の非表示は別プロセス（scripts/hide_refs.py）で行う。同一プロセス内だと多角形追加後に segfault する（KiCad 10.0.3 swig）

b.Save(FN); print('saved', FN)
