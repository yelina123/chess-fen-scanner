# -*- coding: utf-8 -*-
"""精确测量三类格的 iou/rec（全套件取最大）。"""
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import cv2, numpy as np
import scan

CAN = scan.CAN
PIECES = "KQRBNP"
BASE = r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\test_supplement"

def fg_full(cell):
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
    return fg

def to_can(m):
    ys, xs = np.where(m > 0)
    if len(xs) == 0:
        return None
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    m = cv2.resize(m, (CAN, CAN), interpolation=cv2.INTER_AREA)
    _, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
    return m

def best_scores(cell, tpl):
    fg = fg_full(cell)
    cm = to_can(fg)
    if cm is None:
        return None, None, np.count_nonzero(fg) / fg.size
    px = cell[fg > 0]
    lum = px.reshape(-1, 3).mean(axis=1)
    color = "w" if (lum > 200).mean() > 0.33 else "b"
    best = {}
    for pc in PIECES:
        bi = br = 0.0
        for tset in tpl.values():
            tm = tset[(color, pc)]
            inter = np.count_nonzero((cm > 0) & (tm > 0))
            union = np.count_nonzero((cm > 0) | (tm > 0))
            tarea = np.count_nonzero(tm > 0)
            bi = max(bi, inter / union if union else 0)
            br = max(br, inter / tarea if tarea else 0)
        best[pc] = (bi, br)
    return best, color, np.count_nonzero(fg) / fg.size

tpl = scan.load_templates()

def show(imgname, r, c, label):
    img = scan.imread_unicode(rf"{BASE}\{imgname}.jpg")
    bbox = scan.locate_board(img)
    x0, y0, x1, y1 = [int(v) for v in bbox]
    board = img[y0:y1, x0:x1]
    CELL = board.shape[0] // 8
    cell = board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
    best, color, frac = best_scores(cell, tpl)
    if best is None:
        print(f"{imgname} r{r}c{c} {label}: 空 (frac={frac:.2f})")
        return
    top = sorted(best.items(), key=lambda kv: -kv[1][0])
    s = " ".join(f"{pc}:i{bi:.2f}/r{br:.2f}" for pc, (bi, br) in top[:3])
    print(f"{imgname} r{r}c{c} {label} [{color}] frac={frac:.2f} | {s}")

print("== 纯箭头格(应判空) ==")
show("a", 5, 4, "a.e3箭头")
show("b", 4, 5, "b.f4箭头")
show("b", 5, 4, "b.e3箭头")
show("b", 5, 5, "b.f3蓝箭头")
show("c", 5, 4, "c.e3箭头")
print("== 污染真子格(应保留) ==")
show("b", 6, 6, "b.g2白兵+箭头")
show("c", 6, 1, "c.b2白兵+箭头")
show("c", 6, 4, "c.e2白兵+箭头")
print("== 干净真子格(对照) ==")
show("b", 6, 0, "b.a2白兵")
show("b", 2, 2, "b.c6黑马")
show("a", 0, 4, "a.e8黑王")
show("a", 7, 0, "a.a1白车")
