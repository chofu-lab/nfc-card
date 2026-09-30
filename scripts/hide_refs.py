"""部品の参照記号（D1, U1 …）をシルクに出さない。artwork.py の後に別プロセスで実行する。"""
import pcbnew
import sys
FN = sys.argv[1] if len(sys.argv) > 1 else 'Business Card v2.kicad_pcb'
b = pcbnew.LoadBoard(FN)
n = 0
for f in b.GetFootprints():
    f.Reference().SetVisible(False); n += 1
b.Save(FN); print('refs hidden:', n)
