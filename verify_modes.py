# -*- coding: utf-8 -*-
"""验证三档算法模式 + 主题过滤在 10 张图上的成绩。"""
import sys, os
import numpy as np
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import scan
from scan import imread_unicode, locate_board, classify, load_templates, best_orientation

tpl = load_templates()
ORIG = r"C:\Users\Administrator\Desktop\AI work\棋盘识别\检验图"
SUPP = r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\test_supplement"
tests = {
    "1.jpg": (ORIG, "r1bq1bnr/4k3/p3p1Bp/3pPpp1/Np6/4PN2/1PP2PPP/R2QR1K1"),
    "2.jpg": (ORIG, "2r2rk1/pbq2ppp/2n1p1n1/1p2P3/2N5/P4N2/1BQ1BPPP/3R1RK1"),
    "3.jpg": (ORIG, "5rk1/pr3ppp/3Rp1n1/1p2N3/8/P7/1Bq1BPPP/5RK1"),
    "4.jpg": (ORIG, "r2q1rk1/ppp2ppp/2np1n2/1Bb1p3/4P3/2P2Q1P/PP1P1PP1/RNB1R1K1"),
    "5.jpg": (ORIG, "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"),
    "6.jpg": (ORIG, "6k1/1p1n3p/2p1p1p1/2PpP1qr/3P4/P2P1Q2/5BK1/2R5"),
    "7.jpg": (ORIG, "rnb1kbnr/ppppp1Qp/8/8/2q5/8/P2PPPPP/RNB1KBNR"),
    "a.jpg": (SUPP, "rnbqkbnr/pppp1ppp/8/4p3/3P4/8/PPP1PPPP/RNBQKBNR"),
    "b.jpg": (SUPP, "r1bqkbnr/pppp1ppp/2n5/4P3/8/8/PPP1PPPP/RNBQKBNR"),
    "c.jpg": (SUPP, "r1bqk1nr/ppp2ppp/2n5/2bpP3/5B2/5N2/PPP1PPPP/RN1QKB1R"),
}

def expand(f):
    b = []
    for rank in f.split("/"):
        row = []
        for ch in rank:
            if ch.isdigit(): row += [None] * int(ch)
            else: row.append(ch)
        b.append(row)
    return b

def run(mode, theme):
    ok = 0; per = {}
    for name, (folder, truth) in tests.items():
        img = imread_unicode(os.path.join(folder, name))
        bbox = locate_board(img)
        bx0, by0, bx1, by1 = [int(v) for v in bbox]
        board = img[by0:by1, bx0:bx1]
        CELL = board.shape[1] // 8
        grid = [[None]*8 for _ in range(8)]
        for r in range(8):
            for c in range(8):
                cell = board[r*CELL:(r+1)*CELL, c*CELL:(c+1)*CELL]
                grid[r][c], _, _ = classify(cell, tpl, mode=mode, theme=theme)
        fen, _ = best_orientation(grid)
        g = expand(fen); t = expand(truth)
        same = sum(1 for r in range(8) for c in range(8) if (g[r][c] or ".") == (t[r][c] or "."))
        per[name] = same; ok += same
    return ok, per

for mode in ["standard", "recall", "precision"]:
    ok, per = run(mode, None)
    print(f"[模式={mode:9s} 主题=自动] 合计 {ok}/640 = {ok/640:.2%}  明细: " +
          " ".join(f"{n.split('.')[0]}={v}" for n, v in per.items()))

# 单主题: 只验证若干代表性套件在 10 图上的成绩(功能正确性 + 给用户选择参考)
for theme in ["cburnett", "merida", "staunty", "alpha", "pixel"]:
    ok, per = run("standard", theme)
    print(f"[模式=standard  主题={theme:9s}] 合计 {ok}/640 = {ok/640:.2%}")
