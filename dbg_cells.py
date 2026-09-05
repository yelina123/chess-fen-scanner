# -*- coding: utf-8 -*-
"""调试: 把每张测试图的错误格 + 7.jpg 全部格子裁出来核对。"""
import sys, os
import cv2
import numpy as np
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import scan
from scan import imread_unicode, locate_board, classify, load_templates, best_orientation, overlay_mask, LIGHT, DARK, PAL_TOL

tpl = load_templates()
base = r"C:\Users\Administrator\Desktop\AI work\棋盘识别\检验图"
outdir = r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out"
os.makedirs(outdir, exist_ok=True)

tests = {
    "1.jpg": "r1bq1bnr/4k3/p3p1Bp/3pPpp1/Np6/4PN2/1PP2PPP/R2QR1K1",
    "2.jpg": "2r2rk1/pbq2ppp/2n1p1n1/1p2P3/2N5/P4N2/1BQ1BPPP/3R1RK1",
    "3.jpg": "5rk1/pr3ppp/3Rp1n1/1p2N3/8/P7/1Bq1BPPP/5RK1",
    "4.jpg": "r2q1rk1/ppp2ppp/2np1n2/1Bb1p3/4P3/2P2Q1P/PP1P1PP1/RNB1R1K1",
    "5.jpg": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR",
    "6.jpg": "6k1/1p1n3p/2p1p1p1/2PpP1qr/3P4/P2P1Q2/5BK1/2R5",
    "7.jpg": "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR",
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
    t = expand(truth)
    # 拼一张 8x8 放大格子图(每格 160px)
    scale = 160
    mont = np.full((8*scale, 8*scale, 3), 128, np.uint8)
    errs = []
    for r in range(8):
        for c in range(8):
            cell = board[r*CELL:(r+1)*CELL, c*CELL:(c+1)*CELL]
            cell_big = cv2.resize(cell, (scale, scale), interpolation=cv2.INTER_AREA)
            mont[r*scale:(r+1)*scale, c*scale:(c+1)*scale] = cell_big
            got_pc = None
            # 手动分类一遍拿结果
            pc, iou, frac = classify(cell, tpl)
            truth_pc = t[r][c]
            if (pc or ".") != (truth_pc or "."):
                errs.append((r, c, pc, truth_pc, frac))
                cv2.rectangle(mont, (c*scale, r*scale), ((c+1)*scale, (r+1)*scale), (0, 0, 255), 4)
    # 标注行列字母
    for i in range(8):
        cv2.putText(mont, f"c{i}", (i*scale+6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        cv2.putText(mont, f"r{i}", (6, i*scale+18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
    fn = os.path.join(outdir, name.replace(".jpg", "_cells.png"))
    cv2.imencode(".png", mont)[1].tofile(fn)
    print(f"{name}: bbox={bbox} 错误格: {[(r,c,pc,truth_pc,round(frac,3)) for r,c,pc,truth_pc,frac in errs]}  -> {fn}")

    # 每张图把错误格的原图+前景剪影 单独存
    for r, c, pc, truth_pc, frac in errs:
        cell = board[r*CELL:(r+1)*CELL, c*CELL:(c+1)*CELL]
        omask = overlay_mask(cell)
        dL = np.linalg.norm(cell.astype(np.float32) - LIGHT, axis=2)
        dD = np.linalg.norm(cell.astype(np.float32) - DARK, axis=2)
        fg = ((dL > PAL_TOL) & (dD > PAL_TOL)).astype(np.uint8) * 255
        fg[omask > 0] = 0
        fg_open = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3,3), np.uint8))
        fg_close = cv2.morphologyEx(fg_open, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))
        num, lbl, stats, _ = cv2.connectedComponentsWithStats(fg_close, 8)
        fg_big = fg_close.copy()
        if num > 1:
            idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            fg_big = np.where(lbl == idx, 255, 0).astype(np.uint8)
        comb = np.hstack([cv2.resize(cell, (160,160)), cv2.cvtColor(cv2.resize(fg_close, (160,160)), cv2.COLOR_GRAY2BGR),
                          cv2.cvtColor(cv2.resize(fg_big, (160,160)), cv2.COLOR_GRAY2BGR)])
        cv2.putText(comb, f"{name} r{r}c{c} got={pc} truth={truth_pc} frac={frac:.3f}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,0,255), 1)
        fn2 = os.path.join(outdir, f"err_{name.replace('.jpg','')}_r{r}c{c}.png")
        cv2.imencode(".png", comb)[1].tofile(fn2)
print("done")
