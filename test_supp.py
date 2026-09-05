# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import scan

TRUTHS = {
    "a": "rnbqkbnr/pppp1ppp/8/4p3/3P4/8/PPP1PPPP/RNBQKBNR",
    "b": "r1bqkbnr/pppp1ppp/2n5/4P3/8/8/PPP1PPPP/RNBQKBNR",
    "c": "r1bqk1nr/ppp2ppp/2n5/2bpP3/5B2/5N2/PPP1PPPP/RN1QKB1R",
}

def expand(f):
    g = []
    for rank in f.split("/"):
        row = []
        for ch in rank:
            if ch.isdigit():
                row += ["."] * int(ch)
            else:
                row.append(ch)
        g.append(row)
    return g

tpl = scan.load_templates()
for name, truth in TRUTHS.items():
    img = scan.imread_unicode(rf"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\test_supplement\{name}.jpg")
    print(f"===== {name}.jpg shape={img.shape}")
    bbox = scan.locate_board(img)
    print("  bbox:", bbox)
    if bbox is None:
        continue
    fen, rot = scan.recognize(img, tpl)
    g, t = expand(fen), expand(truth)
    same = sum(1 for r in range(8) for c in range(8) if (g[r][c]) == (t[r][c]))
    print("  识别:", fen)
    print("  答案:", truth)
    print(f"  正确: {same}/64 rot={rot}")
