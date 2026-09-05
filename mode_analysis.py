# -*- coding: utf-8 -*-
"""导出 10 张图(7 基准 + 3 补充)每格 (真值, best_iou, frac, 未旋转grid判定),
用于设计 标准/高召回/高精确 三档识别算法的判空阈值。"""
import sys, os
import numpy as np
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import scan
from scan import imread_unicode, locate_board, overlay_mask, load_templates, best_orientation, PIECES, LIGHT, DARK, PAL_TOL, CAN
import cv2

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
            else:
                wb = "w" if ch.isupper() else "b"
                row.append(wb + ch.upper())
        b.append(row)
    return np.array(b, dtype=object)

def raw_scores(cell):
    """复刻 scan.classify 内部, 返回 (color_piece, iou, frac) 不做箭头判空。"""
    ch, cw = cell.shape[:2]
    omask = overlay_mask(cell)
    dL = np.linalg.norm(cell.astype(np.float32) - LIGHT, axis=2)
    dD = np.linalg.norm(cell.astype(np.float32) - DARK, axis=2)
    fg = ((dL > PAL_TOL) & (dD > PAL_TOL)).astype(np.uint8) * 255
    fg[omask > 0] = 0
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
    if n > 1:
        idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fg = np.where(lbl == idx, 255, 0).astype(np.uint8)
    frac = np.count_nonzero(fg) / (ch * cw)
    if frac < 0.03:
        return None, 0.0, frac
    px = cell[fg > 0]
    lum = px.reshape(-1, 3).mean(axis=1)
    color = "w" if (lum > 200).mean() > 0.33 else "b"
    ys, xs = np.where(fg > 0)
    cm = fg[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    cm = cv2.resize(cm, (CAN, CAN), interpolation=cv2.INTER_AREA)
    _, cm = cv2.threshold(cm, 127, 255, cv2.THRESH_BINARY)
    bi, bp = -1, None
    for ts in tpl.values():
        for p in PIECES:
            tm = ts[(color, p)]
            v = np.count_nonzero((cm > 0) & (tm > 0)) / max(1, np.count_nonzero((cm > 0) | (tm > 0)))
            if v > bi: bi, bp = v, p
    return color + bp, bi, frac

# 收集: 真子格 vs 真空格 的 (iou, frac)
real_pieces = []   # (iou, frac, name, r, c, got)
empty_cells = []
for name, (folder, truth) in tests.items():
    img = imread_unicode(os.path.join(folder, name))
    bbox = locate_board(img)
    bx0, by0, bx1, by1 = [int(v) for v in bbox]
    board = img[by0:by1, bx0:bx1]
    CELL = board.shape[1] // 8
    grid = [[None]*8 for _ in range(8)]
    scores = [[None]*8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            cell = board[r*CELL:(r+1)*CELL, c*CELL:(c+1)*CELL]
            got, iou, frac = raw_scores(cell)
            grid[r][c] = got
            scores[r][c] = (iou, frac)
    _, rot = best_orientation(grid)
    # 真值反向旋转到未旋转坐标
    t = expand(truth)
    t_unrot = np.rot90(t, -rot) if rot else t
    for r in range(8):
        for c in range(8):
            iou, frac = scores[r][c]
            truthv = t_unrot[r][c]
            if truthv is None:
                empty_cells.append((iou, frac, name, r, c, grid[r][c]))
            else:
                real_pieces.append((iou, frac, name, r, c, grid[r][c], truthv))

print("===== 真空格(箭头/干净空格) iou/frac 分布 =====")
es = sorted(empty_cells, key=lambda x: -x[0])
for iou, frac, name, r, c, got in es[:15]:
    print(f"  iou={iou:.3f} frac={frac:.3f} {name} r{r}c{c} got={got}")
print(f"  空格数={len(empty_cells)}; iou max={max(x[0] for x in empty_cells):.3f}; frac max among iou>=0.5:")
hi = [x for x in empty_cells if x[0] >= 0.5]
for x in sorted(hi, key=lambda y:-y[1])[:8]:
    print(f"     iou={x[0]:.3f} frac={x[1]:.3f} {x[2]} r{x[3]}c{x[4]} got={x[5]}")

print("\n===== 真子格 iou/frac 分布(按 iou 升序, 看最危险的) =====")
ps = sorted(real_pieces, key=lambda x: x[0])
for iou, frac, name, r, c, got, tv in ps[:20]:
    flag = "" if got == tv else "  <<< 棋种误判"
    print(f"  iou={iou:.3f} frac={frac:.3f} {name} r{r}c{c} got={got} truth={tv}{flag}")
print(f"  真子数={len(real_pieces)}")

print("\n===== 不同阈值组合下的判空错误统计 =====")
for iou_th, frac_th in [(0.85,0.22),(0.70,0.12),(0.92,0.32)]:
    lost_real = 0; kept_empty = 0; details=[]
    for iou, frac, name, r, c, got, tv in real_pieces:
        if iou < iou_th and frac <= frac_th:
            lost_real += 1; details.append(f"漏真子 {name} r{r}c{c} iou={iou:.3f} frac={frac:.3f} {tv}")
    for iou, frac, name, r, c, got in empty_cells:
        if not (iou < iou_th and frac <= frac_th) and got is not None:
            kept_empty += 1; details.append(f"留空格 {name} r{r}c{c} iou={iou:.3f} frac={frac:.3f} got={got}")
    print(f"  iou<{iou_th} & frac<={frac_th}: 漏真子={lost_real} 留空格={kept_empty}")
    for d in details[:6]: print("     ", d)
