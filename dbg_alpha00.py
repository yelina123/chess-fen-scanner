# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import cv2, numpy as np
from scan import imread_unicode, locate_board
import scan

def expand(fen):
    grid = []
    for rank in fen.split("/"):
        row = []
        for ch in rank:
            if ch.isdigit():
                row += ["."] * int(ch)
            else:
                row.append(ch)
        grid.append(row)
    return grid

def cell_silhouette(cell):
    omask = scan.overlay_mask(cell)
    dL = np.linalg.norm(cell.astype(np.float32) - scan.LIGHT, axis=2)
    dD = np.linalg.norm(cell.astype(np.float32) - scan.DARK, axis=2)
    fg = ((dL > scan.PAL_TOL) & (dD > scan.PAL_TOL)).astype(np.uint8) * 255
    fg[omask > 0] = 0
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    num, lbl, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
    if num > 1:
        idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fg = np.where(lbl == idx, 255, 0).astype(np.uint8)
    frac = np.count_nonzero(fg) / fg.size
    return fg, frac

def ious(sil, color, tpl):
    res = []
    for piece in "KQRBNP":
        tm = tpl["alpha"][(color, piece)]
        inter = np.count_nonzero((sil > 0) & (tm > 0))
        union = np.count_nonzero((sil > 0) | (tm > 0))
        res.append((piece, inter / union if union else 0))
    return res

name = "alpha_00"
img = imread_unicode(rf"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\synth_imgs\{name}.jpg")
x0, y0, x1, y1 = [int(v) for v in locate_board(img)]
board = img[y0:y1, x0:x1]
CELL = board.shape[0] // 8
truth = expand(open(rf"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\synth_imgs\{name}.txt").read().strip())
tpl = scan.load_templates()

for r in range(8):
    for c in range(8):
        ch = truth[r][c]
        if ch in "nN":
            cell = board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
            sil, frac = cell_silhouette(cell)
            print(f"马格 r{r}c{c} truth={ch}: frac={frac:.3f}")
            # 缩放剪影到 CAN 再算 IoU
            ys, xs = np.where(sil > 0)
            if len(xs):
                cm = sil[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
                cm = cv2.resize(cm, (scan.CAN, scan.CAN), interpolation=cv2.INTER_AREA)
                _, cm = cv2.threshold(cm, 127, 255, cv2.THRESH_BINARY)
                col = "w" if ch.isupper() else "b"
                print("  IoU:", {p: round(v, 2) for p, v in ious(cm, col, tpl)})
            break
    else:
        continue
    break

for r in range(8):
    for c in range(8):
        if truth[r][c] == ".":
            cell = board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
            sil, frac = cell_silhouette(cell)
            print(f"空格 r{r}c{c}: frac={frac:.4f}")
            if frac > 0.01:
                px = cell[sil > 0]
                print("  空格 fg BGR 均值:", px.mean(axis=0).round(0).astype(int).tolist(), "n=", len(px))
                # 该 fg 最佳匹配
                cm = sil.copy()
                ys, xs = np.where(cm > 0)
                cm = cm[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
                cm = cv2.resize(cm, (scan.CAN, scan.CAN), interpolation=cv2.INTER_AREA)
                _, cm = cv2.threshold(cm, 127, 255, cv2.THRESH_BINARY)
                print("  IoU:", {p: round(v, 2) for p, v in ious(cm, "b", tpl)})
            break
    else:
        continue
    break
