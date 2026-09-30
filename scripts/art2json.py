"""ちょふまる等のラスター画像（PNG）をシルク用の多角形（geojson）にする。
元画像が 200px 程度と小さいので、そのまま potrace にかけると輪郭がガタつき、色模様が細かい穴になる。
ここでは 拡大 → ぼかし → 二値化 → potrace（平滑化強め） の順で滑らかな輪郭を得る（2026-09-18）。

使い方（Pillow が入った Python で、リポジトリ直下で）:
  python3 scripts/art2json.py artwork/pose-thumbs-up.png artwork/labomaru.json --blur 4 --keep-blue --cheeks     # 表（案7、2026-09-18）
  python3 scripts/art2json.py artwork/pose-idea.png artwork/labomaru-idea.json --blur 4 --keep-blue --cheeks \
      --cheek-pos "62,150;133,139" --cheek-len 5 --cheek-thick 2.6 --cheek-angle 70 --cheek-gap 5.5          # 裏（案E: 元絵の位置に短め 2 本、間隔 0.27 mm）
    --keep-blue: 青い印を残す（ほっぺ・反射は白抜き、左耳の IC は塗り）  --cheeks: ほっぺを左右 2 本ずつ同じ斜線に描き直す
    --ic-erode/--ic-shift/--ic-hollow/--ic-synth は左耳 IC の見せ方の実験用（不採用）
  python3 scripts/art2json.py artwork/wordmark-h-en-4000.png artwork/wordmark.json --mode nonwhite --scale 1 --blur 0 --alphamax 0.6 --turd 30   # ワードマーク（HP と同じ brand/final/wordmark-h-en.svg を 4000px に描画したもの）
出力座標は拡大後の画素。artwork.py の place_art は高さで正規化するので倍率は問わない。
"""
import argparse, subprocess, sys, tempfile, os
from PIL import Image, ImageFilter

SCALE = 8          # 拡大倍率
BLUR = 8.0         # ガウスぼかし半径 [拡大後 px]（輪郭の段差・耳の切り欠きをならす。大きすぎると細部が丸まる）
THRESH = 140       # 輝度しきい値（これより暗い画素をインクにする）
ALPHA = 128        # 透明部分の判定

def components(mask):
    """2 値 L 画像の白い連結領域 → [(面積, x0, y0, x1, y1), ...]"""
    from collections import deque
    w, h = mask.size; p = mask.load(); seen = bytearray(w * h); res = []
    for y0 in range(h):
        for x0 in range(w):
            if not p[x0, y0] or seen[y0 * w + x0]: continue
            q = deque([(x0, y0)]); seen[y0 * w + x0] = 1; n = 0; xs = [x0, x0]; ys = [y0, y0]
            while q:
                x, y = q.popleft(); n += 1
                xs[0] = min(xs[0], x); xs[1] = max(xs[1], x); ys[0] = min(ys[0], y); ys[1] = max(ys[1], y)
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and p[nx, ny] and not seen[ny * w + nx]:
                        seen[ny * w + nx] = 1; q.append((nx, ny))
            res.append((n, xs[0], ys[0], xs[1], ys[1]))
    return res

def to_bitmap(src, scale, blur, mode, hollow_red=0, hollow_red_below=0.35, keep_blue=False, cheeks=False, cheek_len=4.5, cheek_thick=1.6, cheek_angle=60, ic_box=(0.0, 0.3, 0.32, 0.75), ic_sat=0.0, ic_erode=0, ic_hollow=0, ic_shift=(0, 0), ic_synth=None, cheek_mirror=None, cheek_from_eyes=None, cheek_pos=None, cheek_gap=3.0):
    """mode='lum': 暗い画素をインク（ちょふまる等の線画）。mode='nonwhite': 白以外を全部インク（ワードマーク等、色付き要素も塗る。背景が白で焼き込まれた PNG 向け）"""
    im = Image.open(src).convert('RGBA')
    w, h = im.size
    big = im.resize((w * scale, h * scale), Image.LANCZOS) if scale != 1 else im
    a = big.getchannel('A')
    bg = Image.new('RGBA', big.size, (255, 255, 255, 255))
    comp = Image.alpha_composite(bg, big)
    rgb = comp.convert('L')
    if blur > 0:
        a = a.filter(ImageFilter.GaussianBlur(blur)); rgb = rgb.filter(ImageFilter.GaussianBlur(blur))
    if mode == 'nonwhite':
        # 白（RGB すべて 235 以上）以外をインク。色付き要素（青いチップ・赤い磁石・黄色の稲妻）も塗る
        px = comp.convert('RGB').load(); ink = Image.new('1', big.size, 1); out = ink.load()
        for y in range(big.size[1]):
            for x in range(big.size[0]):
                rr, gg, bb = px[x, y]
                out[x, y] = 1 if (rr >= 235 and gg >= 235 and bb >= 235) else 0
        return ink
    ink = Image.new('1', big.size, 1)
    px_rgb = rgb.load(); px_a = a.load(); out = ink.load()
    for y in range(big.size[1]):
        for x in range(big.size[0]):
            out[x, y] = 0 if (px_a[x, y] >= ALPHA and px_rgb[x, y] < THRESH) else 1
    cheek_marks = []
    if keep_blue:
        # 明るい青の印（ほっぺの斜線、球や車輪の反射）は白抜きで残す。ぼかして角を丸め、細かすぎる点は捨てる
        import colorsys
        rgbimg = comp.convert('RGB'); pr = rgbimg.load()
        blue = Image.new('L', big.size, 0); pb = blue.load()
        for y in range(big.size[1]):
            for x in range(big.size[0]):
                r_, g_, b_ = pr[x, y]
                h_, s_, v_ = colorsys.rgb_to_hsv(r_ / 255, g_ / 255, b_ / 255)
                if s_ > 0.5 and v_ > 0.55 and 0.52 < h_ < 0.72: pb[x, y] = 255
        blue = blue.filter(ImageFilter.GaussianBlur(max(blur, 3))).point(lambda v: 255 if v >= 110 else 0)
        if cheeks:
            # 顔（暗い塗りの最大領域）の中にある青い印＝ほっぺの斜線。元絵は本数が左右で違うので、
            # 位置だけ拾って左右 2 本ずつ同じ形の斜線に描き直す（反射など顔の外の青い印はそのまま）
            from PIL import ImageDraw
            face = Image.new('L', big.size, 0); pf = face.load(); prgb = rgb.load(); pa = a.load()
            for y in range(big.size[1]):
                for x in range(big.size[0]):
                    if pa[x, y] >= ALPHA and prgb[x, y] < 60: pf[x, y] = 255
            comps = components(face); comps.sort(key=lambda c: -c[0])
            fn, fx0, fy0, fx1, fy1 = comps[0]                       # 顔の bbox
            fcx = (fx0 + fx1) / 2
            bl = [c for c in components(blue) if fx0 <= (c[1] + c[3]) / 2 <= fx1 and fy0 <= (c[2] + c[4]) / 2 <= fy1]
            pb = blue.load()
            for c in bl:                                             # 顔の中の青は一旦消す
                for y in range(c[2], c[4] + 1):
                    for x in range(c[1], c[3] + 1):
                        pb[x, y] = 0
            left = sorted([c for c in bl if (c[1] + c[3]) / 2 < fcx], key=lambda c: -c[0])[:2]
            right = sorted([c for c in bl if (c[1] + c[3]) / 2 >= fcx], key=lambda c: -c[0])[:2]
            def centers(cs): return [((c[1] + c[3]) / 2, (c[2] + c[4]) / 2) for c in cs]
            L, R = centers(left), centers(right)
            if len(L) < 2 and len(R) == 2: L = [(2 * fcx - x, y) for x, y in R]   # 片側しか無ければ鏡映
            if len(R) < 2 and len(L) == 2: R = [(2 * fcx - x, y) for x, y in L]
            if cheek_mirror == 'left': R = [(2 * fcx - x, y) for x, y in L]       # 左右対称にしたいとき: 片側を基準に鏡映
            if cheek_mirror == 'right': L = [(2 * fcx - x, y) for x, y in R]
            if cheek_pos:
                # 元画像の座標で直接指定: [(cx,cy),(cx,cy)]。各中心に gap 間隔で 2 本置く
                gap = cheek_gap * scale
                marks = [[(cx * scale - gap / 2, cy * scale), (cx * scale + gap / 2, cy * scale)] for cx, cy in cheek_pos]
                L, R = marks[0], marks[1]
            if cheek_from_eyes:
                # 目（顔の中の白い領域、大きい順に 2 つ）を基準に、各目の外側下に 2 本ずつ置く。dx,dy,gap は元画像 px
                white = Image.new('L', big.size, 0); pw = white.load()
                for y in range(fy0, fy1 + 1):
                    for x in range(fx0, fx1 + 1):
                        if pf[x, y] == 0 and prgb[x, y] > 200 and pa[x, y] >= ALPHA: pw[x, y] = 255
                eyes = sorted([c for c in components(white) if c[0] > 50 * scale * scale], key=lambda c: -c[0])[:2]
                eyes = sorted(eyes, key=lambda c: c[1])
                dx, dy, gap = [v * scale for v in cheek_from_eyes]
                marks = []
                for i, (n_, ex0, ey0, ex1, ey1) in enumerate(eyes):
                    ecx, ecy = (ex0 + ex1) / 2, (ey0 + ey1) / 2
                    sgn = -1 if i == 0 else 1
                    marks.append([(ecx + sgn * dx - gap / 2, ecy + dy), (ecx + sgn * dx + gap / 2, ecy + dy)])
                L, R = marks[0], marks[1]
                print('eyes at', [((c[1] + c[3]) // 2 // scale, (c[2] + c[4]) // 2 // scale) for c in eyes])
            cheek_marks = L + R   # 青い印の分類（IC 判定）に巻き込まれないよう、最後に out へ直接白で描く
            print('cheeks: left %d right %d (face bbox %s)' % (len(L), len(R), (fx0, fy0, fx1, fy1)))
        # 青い印の扱い: 左耳の IC（画像の左寄り・中段）は塗り、それ以外（球・車輪の反射、ほっぺ）は白抜き
        pb = blue.load(); W, H = big.size
        bx0, by0, bx1, by1 = ic_box
        for (n, x0, y0, x1, y1) in components(blue):
            cx, cy = (x0 + x1) / 2 / W, (y0 + y1) / 2 / H
            fill = 0 if (bx0 <= cx <= bx1 and by0 <= cy <= by1) else 1   # 0=インク, 1=白
            if fill == 0 and ic_sat <= 0:
                # ic_sat=0: 青い領域を全部塗る（案7 の見た目。2026-09-18 に確定）
                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        if pb[x, y]: out[x, y] = 0
                print('blue mark at (%d,%d) size %d -> ink (full)' % ((x0 + x1) // 2 // scale, (y0 + y1) // 2 // scale, n))
                continue
            if fill == 0:
                # IC は塗りにするが、元絵の明るい部分（ピンや反射）は白で少し残す: 彩度の高い青だけインク
                import colorsys
                pr = comp.convert('RGB').load()
                sat = Image.new('L', big.size, 0); ps = sat.load()
                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        if not pb[x, y]: continue
                        r_, g_, b_ = pr[x, y]; h_, s_, v_ = colorsys.rgb_to_hsv(r_ / 255, g_ / 255, b_ / 255)
                        ps[x, y] = 255 if (s_ > ic_sat and v_ < 0.93) else 0
                sat = sat.filter(ImageFilter.GaussianBlur(max(blur, 3) * 0.6)).point(lambda v: 255 if v >= 128 else 0)
                if ic_erode > 0: sat = sat.filter(ImageFilter.MinFilter(2 * ic_erode + 1))   # 少し痩せさせて耳の輪郭との間に白い縁を出す
                if ic_hollow > 0:  # 塗りではなく輪郭線だけ（うっすら IC の形が見える程度）
                    inner = sat.filter(ImageFilter.MinFilter(2 * ic_hollow + 1)); pi = inner.load(); ps0 = sat.load()
                    for y in range(y0, y1 + 1):
                        for x in range(x0, x1 + 1):
                            if pi[x, y]: ps0[x, y] = 0
                if ic_synth:  # 元絵の細部が潰れている場合: IC の位置に、幅・高さ比 ic_synth の角丸長方形を描き直す（周りに白い余白ができる）
                    from PIL import ImageDraw
                    for y in range(y0, y1 + 1):
                        for x in range(x0, x1 + 1):
                            if pb[x, y]: out[x, y] = 1
                    bw, bh = x1 - x0, y1 - y0; cx_, cy_ = (x0 + x1) / 2 + ic_shift[0] * scale, (y0 + y1) / 2 + ic_shift[1] * scale
                    rw, rh = bw * ic_synth[0] / 2, bh * ic_synth[1] / 2
                    ImageDraw.Draw(ink).rounded_rectangle([cx_ - rw, cy_ - rh, cx_ + rw, cy_ + rh], radius=min(rw, rh) * 0.4, fill=0)
                    print('IC synth rect %.1fx%.1f src px at (%.0f,%.0f)' % (2 * rw / scale, 2 * rh / scale, cx_ / scale, cy_ / scale))
                    continue
                if ic_shift != (0, 0):  # IC を少しずらす（耳の内側に寄せる）。元の位置は白に戻し、ずらした先を塗る
                    from PIL import ImageChops
                    sx, sy = int(ic_shift[0] * scale), int(ic_shift[1] * scale)
                    for y in range(y0, y1 + 1):
                        for x in range(x0, x1 + 1):
                            if pb[x, y]: out[x, y] = 1
                    sat = ImageChops.offset(sat, sx, sy); ps = sat.load()
                    for y in range(max(0, y0 + sy), min(H, y1 + sy + 1)):
                        for x in range(max(0, x0 + sx), min(W, x1 + sx + 1)):
                            if ps[x, y]: out[x, y] = 0
                    continue
                ps = sat.load()
                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        if pb[x, y]: out[x, y] = 0 if ps[x, y] else 1
                continue
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    if pb[x, y]: out[x, y] = fill
            print('blue mark at (%d,%d) size %d -> %s' % ((x0 + x1) // 2 // scale, (y0 + y1) // 2 // scale, n, 'ink' if fill == 0 else 'white'))
        if cheeks and cheek_marks:
            from PIL import ImageDraw
            import math
            d = ImageDraw.Draw(ink)
            ln, th = cheek_len * scale, cheek_thick * scale
            dx, dy = ln / 2 * math.cos(math.radians(cheek_angle)), ln / 2 * math.sin(math.radians(cheek_angle))
            for (cx, cy) in cheek_marks:
                d.line([(cx - dx, cy + dy), (cx + dx, cy - dy)], fill=1, width=int(th))
                for (ex, ey) in ((cx - dx, cy + dy), (cx + dx, cy - dy)): d.ellipse([ex - th / 2, ey - th / 2, ex + th / 2, ey + th / 2], fill=1)
    if hollow_red:
        # 赤い塗り（歯車・アンテナ球など、明るめの有彩色）は塗りつぶさず輪郭線だけ残す（白黒シルクで「塗り」に見えないように）
        import colorsys
        from PIL import ImageOps
        rgbimg = comp.convert('RGB'); pr = rgbimg.load()
        red = Image.new('L', big.size, 0); prd = red.load()
        for y in range(big.size[1]):
            for x in range(big.size[0]):
                r_, g_, b_ = pr[x, y]
                h_, s_, v_ = colorsys.rgb_to_hsv(r_ / 255, g_ / 255, b_ / 255)
                if s_ > 0.45 and v_ > 0.35 and (h_ < 0.06 or h_ > 0.93): prd[x, y] = 255
        red = red.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: 255 if v >= 128 else 0)
        # 画像上部（アンテナの球）は塗りのまま残し、それより下の赤（耳の歯車）だけ中抜きにする
        prd = red.load(); ylim = int(big.size[1] * hollow_red_below)
        for y in range(0, ylim):
            for x in range(big.size[0]): prd[x, y] = 0
        inner = red.filter(ImageFilter.MinFilter(2 * hollow_red + 1))   # 収縮 → 内側
        pin = inner.load(); prd = red.load()
        for y in range(big.size[1]):
            for x in range(big.size[0]):
                if prd[x, y] and pin[x, y]: out[x, y] = 1   # 赤の内側は白抜き、縁 hollow_red px だけ残る
    return ink

def main(src, dst, scale=SCALE, blur=BLUR, mode='lum', alphamax=1.2, turd=None, hollow_red=0, hollow_red_below=0.35, keep_blue=False, cheeks=False, cheek_len=4.5, cheek_thick=1.6, cheek_angle=60, ic_box=(0.0, 0.3, 0.32, 0.75), ic_sat=0.0, ic_erode=0, ic_hollow=0, ic_shift=(0, 0), ic_synth=None, cheek_mirror=None, cheek_from_eyes=None, cheek_pos=None, cheek_gap=3.0):
    ink = to_bitmap(src, scale, blur, mode, hollow_red, hollow_red_below, keep_blue, cheeks, cheek_len, cheek_thick, cheek_angle, ic_box, ic_sat, ic_erode, ic_hollow, ic_shift, ic_synth, cheek_mirror, cheek_from_eyes, cheek_pos, cheek_gap)
    if turd is None: turd = scale * scale * 3
    with tempfile.NamedTemporaryFile(suffix='.pbm', delete=False) as t:
        ink.save(t.name)
        # -t: これより小さい島（拡大後 px^2）を捨てる  -a: 角の丸め（最大 1.334、角を残すなら小さく）  -O: 曲線最適化の許容
        subprocess.run(['potrace', '-b', 'geojson', '-t', str(turd), '-a', str(alphamax), '-O', '0.4', '-o', dst, t.name], check=True)
        os.unlink(t.name)
    print('wrote', dst, 'from', src, 'size', ink.size, 'mode', mode)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--scale', type=int, default=SCALE); ap.add_argument('--blur', type=float, default=BLUR)
    ap.add_argument('--mode', choices=['lum', 'nonwhite'], default='lum'); ap.add_argument('--alphamax', type=float, default=1.2)
    ap.add_argument('--turd', type=int, default=None)
    ap.add_argument('--hollow-red', type=int, default=0, help='赤い塗りを輪郭線（この幅 px）だけにする')
    ap.add_argument('--hollow-red-below', type=float, default=0.35, help='画像高さのこの割合より下にある赤だけ中抜き（上のアンテナ球は塗りのまま）')
    ap.add_argument('--keep-blue', action='store_true', help='明るい青の印（ほっぺ・反射）を白抜きで残す')
    ap.add_argument('--cheeks', action='store_true', help='顔の中の青い印を、左右 2 本ずつ同じ形の斜線（白抜き）に描き直す')
    ap.add_argument('--cheek-len', type=float, default=4.5); ap.add_argument('--cheek-thick', type=float, default=1.6); ap.add_argument('--cheek-angle', type=float, default=60, help='元画像 px 単位の長さ・太さと角度')
    ap.add_argument('--ic-sat', type=float, default=0.0, help='IC の塗りに使う彩度しきい値（0=全部塗る。案7 の採用値）')
    ap.add_argument('--ic-erode', type=int, default=0, help='IC の塗りを痩せさせる量 [拡大後 px]（耳の輪郭との間に白い縁を出す）')
    ap.add_argument('--ic-hollow', type=int, default=0, help='IC を塗らず輪郭線（この幅 px）だけにする')
    ap.add_argument('--ic-shift', default='0,0', help='IC の塗りをずらす量 [元画像 px] dx,dy（負で左・上）')
    ap.add_argument('--ic-synth', default=None, help='IC を角丸長方形で描き直す: 元の青い領域に対する幅比,高さ比（例 0.45,0.7）')
    ap.add_argument('--cheek-mirror', choices=['left', 'right'], default=None, help='ほっぺの位置を片側基準で左右対称にする')
    ap.add_argument('--cheek-from-eyes', default=None, help='目を基準にほっぺを置く: dx,dy,gap（元画像 px。dx は外側へ、dy は下へ、gap は 2 本の間隔）')
    ap.add_argument('--cheek-pos', default=None, help='ほっぺの中心を元画像 px で直接指定 "x1,y1;x2,y2"')
    ap.add_argument('--cheek-gap', type=float, default=3.0, help='2 本の間隔 [元画像 px]')
    ap.add_argument('--ic-box', default='0,0.3,0.32,0.75', help='この範囲（画像幅・高さに対する割合 x0,y0,x1,y1）にある青い印は塗り＝左耳の IC')
    a = ap.parse_args(); main(a.src, a.dst, a.scale, a.blur, a.mode, a.alphamax, a.turd, a.hollow_red, a.hollow_red_below, a.keep_blue, a.cheeks, a.cheek_len, a.cheek_thick, a.cheek_angle, tuple(float(v) for v in a.ic_box.split(',')), a.ic_sat, a.ic_erode, a.ic_hollow, tuple(float(v) for v in a.ic_shift.split(',')), tuple(float(v) for v in a.ic_synth.split(',')) if a.ic_synth else None, a.cheek_mirror, tuple(float(v) for v in a.cheek_from_eyes.split(',')) if a.cheek_from_eyes else None, [tuple(float(v) for v in q.split(',')) for q in a.cheek_pos.split(';')] if a.cheek_pos else None, a.cheek_gap)
