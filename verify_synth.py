# -*- coding: utf-8 -*-
"""合成测试集批量验证: 对 synth_imgs/ 每张图跑识别, 与 .txt 标准答案比对, 按套件汇总准确率。
用法: python verify_synth.py
"""
import sys, os, glob
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import scan
from scan import imread_unicode, locate_board, classify, load_templates, best_orientation

tpl = load_templates()
print(f"已加载模板套件: {len(tpl)} 个: {sorted(tpl.keys())}")

OUT_DIR = r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\synth_imgs"

def expand(f):
    b = []
    for rank in f.split("/"):
        row = []
        for ch in rank:
            if ch.isdigit():
                row += [None] * int(ch)
            else:
                row.append(ch)
        b.append(row)
    return b

files = sorted(glob.glob(os.path.join(OUT_DIR, "*.jpg")))
per_set = {}
total_ok = total_n = 0
for fp in files:
    name = os.path.basename(fp)[:-4]
    setname = name.rsplit("_", 1)[0]
    with open(fp[:-4] + ".txt", encoding="utf-8") as f:
        truth = f.read().strip()
    img = imread_unicode(fp)
    bbox = locate_board(img)
    if bbox is None:
        per_set.setdefault(setname, [0, 64])
        total_n += 64
        print(f"{name}: 定位失败")
        continue
    bx0, by0, bx1, by1 = [int(v) for v in bbox]
    board = img[by0:by1, bx0:bx1]
    ch, cw = board.shape[:2]
    CELL = cw // 8
    grid = [[None] * 8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            cell = board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
            grid[r][c], _, _ = classify(cell, tpl)
    fen, rot = best_orientation(grid)
    g = expand(fen); t = expand(truth)
    same = sum(1 for r in range(8) for c in range(8) if (g[r][c] or ".") == (t[r][c] or "."))
    a, b = per_set.setdefault(setname, [0, 0])
    per_set[setname] = [a + same, b + 64]
    total_ok += same; total_n += 64
    if same < 64:
        print(f"{name}: {same}/64  识别={fen}")

print("\n按套件汇总:")
print(f"{'套件':<20}{'正确':>8}{'总数':>6}{'准确率':>8}")
for s in sorted(per_set):
    ok, n = per_set[s]
    print(f"{s:<20}{ok:>8}{n:>6}{ok / n:>8.1%}")
print(f"\n总计: {total_ok}/{total_n} = {total_ok / total_n:.2%}")
