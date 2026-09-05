# -*- coding: utf-8 -*-
"""带旋转对齐的错误格分析: 保存最终方向(FEN方向)下每个错误格的 原图+前景剪影+最大连通域。"""
import sys, os
import cv2
import numpy as np
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import scan
from scan import imread_unicode, locate_board, classify, load_templates, best_orientation, overlay_mask, LIGHT, DARK, PAL_TOL

tpl = load_templates()
base = r"C:\Users\Administrator\Desktop\AI work\棋盘识别\检验图"
outdir = r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out2"
os.makedirs(outdir, exist_ok=True)

tests = {
    "1.jpg": "r1bq1bnr/4k3/p3p1Bp/3pPpp1/Np6/4PN2/1PP2PPP/R2QR1K1",
    "2.jpg": "2r2rk1/pbq2ppp/2n1p1n1/1p2P3/2N5/P4N2/1BQ1BPPP/3R1RK1",
    "3.jpg": "5rk1/pr3ppp/3Rp1n1/1p2N3/8/P7/1Bq1BPPP/5RK1",
    "4.jpg": "r2q1rk1/ppp2ppp/2np1n2/1Bb1p3/4P3/2P2Q1P/PP1P1PP1/RNB1R1K1",
    "5.jpg": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR",
    "6.jpg": "6k1/1p1n3p/2p1p1p1/2PpP1qr/3P4/P2P1Q2/5BK1/2R5",
    "7.jpg": "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR",  # 已知该truth与图不符, 仅参考
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

for name, truth in tests.items():
    img = imread_unicode(os.path.join(base, name))
    bbox = locate_board(img)
    bx0, by0, bx1, by1 = [int(v) for v in bbox]
    board = img[by0:by1, bx0:bx1]
    ch, cw = board.shape[:2]
    CELL = cw // 8
    grid = [[None]*8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            cell = board[r*CELL:(r+1)*CELL, c*CELL:(c+1)*CELL]
            grid[r][c], _, _ = classify(cell, tpl)
    fen, rot = best_orientation(grid)
    board_rot = np.rot90(board, rot).copy()  # 与FEN方向一致
    t = expand(truth)
    g = expand(fen)
    print(f"--- {name} rot={rot} bbox={bbox} ---")
    for r in range(8):
        for c in range(8):
            if (g[r][c] or ".") != (t[r][c] or "."):
                cell = board_rot[r*CELL:(r+1)*CELL, c*CELL:(c+1)*CELL]
                omask = overlay_mask(cell)
                dL = np.linalg.norm(cell.astype(np.float32)-LIGHT, axis=2)
                dD = np.linalg.norm(cell.astype(np.float32)-DARK, axis=2)
                fg = ((dL > PAL_TOL) & (dD > PAL_TOL)).astype(np.uint8)*255
                fg[omask > 0] = 0
                fg_o = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3,3), np.uint8))
                fg_c = cv2.morphologyEx(fg_o, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))
                num, lbl, stats, _ = cv2.connectedComponentsWithStats(fg_c, 8)
                fg_big = fg_c
                if num > 1:
                    idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
                    fg_big = np.where(lbl == idx, 255, 0).astype(np.uint8)
                frac = np.count_nonzero(fg_big)/(cell.shape[0]*cell.shape[1])
                # 单元格上的高亮掩膜叠加显示(红色)
                hl = cv2.cvtColor(cv2.resize(fg_c, (200,200)), cv2.COLOR_GRAY2BGR)
                om_big = cv2.resize(omask, (200,200), interpolation=cv2.INTER_NEAREST)
                hl[om_big > 0] = (0, 0, 255)
                comb = np.hstack([cv2.resize(cell, (200,200)), hl,
                                  cv2.cvtColor(cv2.resize(fg_big, (200,200)), cv2.COLOR_GRAY2BGR)])
                cv2.putText(comb, f"{name} r{r}c{c} got={g[r][c] or '.'} truth={t[r][c] or '.'} frac={frac:.3f}",
                            (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0,0,255), 1)
                fn = os.path.join(outdir, f"{name.replace('.jpg','')}_r{r}c{c}.png")
                cv2.imencode(".png", comb)[1].tofile(fn)
                print(f"  r{r}c{c}: got={g[r][c] or '.'} truth={t[r][c] or '.'} frac={frac:.3f} -> {fn}")
print("done")
