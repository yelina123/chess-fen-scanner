# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import cv2, numpy as np
import scan

img = scan.imread_unicode(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\test_supplement\a.jpg")
bbox = scan.locate_board(img)
x0, y0, x1, y1 = [int(v) for v in bbox]
board = img[y0:y1, x0:x1]
CELL = board.shape[0] // 8
tpl = scan.load_templates()

r, c = 0, 1
cell = board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
print("cell shape:", cell.shape)

# 复刻 scan.classify 的 fg
def fg_scan(cell):
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

fg = fg_scan(cell)
print("fg 非零:", np.count_nonzero(fg))
# 与 cburnett bN 的 iou (按 scan.classify 流程)
cm = fg.copy()
ys, xs = np.where(cm > 0)
cm = cm[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
cm = cv2.resize(cm, (scan.CAN, scan.CAN), interpolation=cv2.INTER_AREA)
_, cm = cv2.threshold(cm, 127, 255, cv2.THRESH_BINARY)
tm = tpl["cburnett"][("b", "N")]
inter = np.count_nonzero((cm > 0) & (tm > 0))
union = np.count_nonzero((cm > 0) | (tm > 0))
print("复刻流程 vs cburnett bN: iou =", round(inter / union, 3), "inter=", inter, "union=", union)
print("cm 非零:", np.count_nonzero(cm > 0), "tm 非零:", np.count_nonzero(tm > 0))
