# -*- coding: utf-8 -*-
"""验证 scan.py 在全部 7 张检验图上的逐格准确率(含 7.jpg 引擎标注情形)。"""
import sys, os
import numpy as np
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import scan
from scan import imread_unicode, locate_board, classify, load_templates, best_orientation

tpl = load_templates()
base = r"C:\Users\Administrator\Desktop\AI work\棋盘识别\检验图"
tests = {
    "1.jpg": "r1bq1bnr/4k3/p3p1Bp/3pPpp1/Np6/4PN2/1PP2PPP/R2QR1K1",
    "2.jpg": "2r2rk1/pbq2ppp/2n1p1n1/1p2P3/2N5/P4N2/1BQ1BPPP/3R1RK1",
    "3.jpg": "5rk1/pr3ppp/3Rp1n1/1p2N3/8/P7/1Bq1BPPP/5RK1",
    "4.jpg": "r2q1rk1/ppp2ppp/2np1n2/1Bb1p3/4P3/2P2Q1P/PP1P1PP1/RNB1R1K1",
    "5.jpg": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR",
    "6.jpg": "6k1/1p1n3p/2p1p1p1/2PpP1qr/3P4/P2P1Q2/5BK1/2R5",
    # 7.jpg 真实局面(2026-09-03 经逐格目视+模板置信度+旧版 7_scan.png 三重核对):
    # 图上黑后在 c4、白后在 g7, d8/d1/f7/b2/c2 均空, 无引擎徽章(棋盘内高饱和亮色像素=0)。
    # 注意: 旧交接文档写的是 1.d4 初始局面(rnbqkbnr/.../3P4/.../PPP1PPPP/...), 与图像不符, 已更正。
    "7.jpg": "rnb1kbnr/ppppp1Qp/8/8/2q5/8/P2PPPPP/RNB1KBNR",
}

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

total_ok = 0; total_n = 0
for name, truth in tests.items():
    img = imread_unicode(os.path.join(base, name))
    bbox = locate_board(img)
    if bbox is None:
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
    total_ok += same; total_n += 64
    status = "✓全对" if same == 64 else f"错{64-same}格"
    print(f"{name}: {fen}")
    print(f"   truth: {truth}   [{same}/64 {status}]")
    if same < 64:
        for r in range(8):
            for c in range(8):
                if (g[r][c] or ".") != (t[r][c] or "."):
                    print(f"     diff r{r}c{c}: got={g[r][c] or '.'} truth={t[r][c] or '.'}")
print(f"\n总计: {total_ok}/{total_n} = {total_ok/total_n:.1%}")
