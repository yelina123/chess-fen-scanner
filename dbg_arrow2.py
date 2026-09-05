# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import cv2, numpy as np
import scan

def fg_mask(cell):
    omask = scan.overlay_mask(cell)
    dL = np.linalg.norm(cell.astype(np.float32) - scan.LIGHT, axis=2)
    dD = np.linalg.norm(cell.astype(np.float32) - scan.DARK, axis=2)
    fg = ((dL > scan.PAL_TOL) & (dD > scan.PAL_TOL)).astype(np.uint8) * 255
    fg[omask > 0] = 0
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return fg

BASE = r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\test_supplement"

def cell_at(img, r, c):
    bbox = scan.locate_board(img)
    x0, y0, x1, y1 = [int(v) for v in bbox]
    board = img[y0:y1, x0:x1]
    CELL = board.shape[0] // 8
    return board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL], CELL

# b.jpg: f3 蓝箭头格 r5c5, f4 深箭头格 r4c5, 以及真子格 f6? b.jpg 黑马在 c6=r2c2
img = scan.imread_unicode(rf"{BASE}\b.jpg")
for r, c, tag in [(5, 5, "f3蓝箭头"), (4, 5, "f4深箭头"), (2, 2, "c6真马"), (0, 0, "a8真车")]:
    cell, CELL = cell_at(img, r, c)
    fg = fg_mask(cell)
    dist = cv2.distanceTransform(fg, cv2.DIST_L2, 5)
    print(f"{tag}: fg面积 {np.count_nonzero(fg)}/{fg.size} ({np.count_nonzero(fg)/fg.size:.1%}), 最大半径 {dist.max():.1f}")
    # 半径直方图
    hist = np.histogram(dist[fg > 0], bins=[0, 5, 10, 15, 20, 25, 30, 50])[0]
    print("   半径分布(0-5,5-10,10-15,15-20,20-25,25-30,30+):", hist.tolist())
    # 保存图
    vis = np.zeros((CELL, CELL * 2, 3), np.uint8)
    vis[:, :CELL] = cell
    vis[:, CELL:] = cv2.cvtColor(dist, cv2.COLOR_GRAY2BGR)
    cv2.imwrite(rf"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out2\arrow_{tag}.png", vis)
