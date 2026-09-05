# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import cv2, numpy as np
import scan

def cell_at(img, r, c):
    bbox = scan.locate_board(img)
    x0, y0, x1, y1 = [int(v) for v in bbox]
    board = img[y0:y1, x0:x1]
    CELL = board.shape[0] // 8
    return board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL], CELL

# a.jpg: e3 = r5 c4 (深色箭头)
img = scan.imread_unicode(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\test_supplement\a.jpg")
cell, CELL = cell_at(img, 5, 4)
# 该格是空格, 非棋盘色的像素即箭头
dL = np.linalg.norm(cell.astype(np.float32) - scan.LIGHT, axis=2)
dD = np.linalg.norm(cell.astype(np.float32) - scan.DARK, axis=2)
fg = (dL > scan.PAL_TOL) & (dD > scan.PAL_TOL)
arrow_px = cell[fg]
print("a.jpg e3 箭头像素数:", len(arrow_px), "BGR均值:", arrow_px.mean(axis=0).round(0).astype(int).tolist() if len(arrow_px) else None)
hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)[fg]
if len(hsv):
    print("  HSV 均值:", hsv.mean(axis=0).round(0).astype(int).tolist(), "中位:", np.median(hsv, axis=0).astype(int).tolist())

# b.jpg: f4=r4 c5 深色长箭头; f3=r5 c5 蓝箭头
img = scan.imread_unicode(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\test_supplement\b.jpg")
for r, c, tag in [(4, 5, "f4深色"), (5, 5, "f3蓝色"), (5, 4, "e3深色")]:
    cell, _ = cell_at(img, r, c)
    dL = np.linalg.norm(cell.astype(np.float32) - scan.LIGHT, axis=2)
    dD = np.linalg.norm(cell.astype(np.float32) - scan.DARK, axis=2)
    fg = (dL > scan.PAL_TOL) & (dD > scan.PAL_TOL)
    px = cell[fg]
    print(f"b.jpg {tag}: 像素 {len(px)}", "BGR均值:", px.mean(axis=0).round(0).astype(int).tolist() if len(px) else None)
    if len(px):
        hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)[fg]
        print("   HSV 中位:", np.median(hsv, axis=0).astype(int).tolist())

# c.jpg: e3=r5 c4 灰蓝箭头
img = scan.imread_unicode(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\test_supplement\c.jpg")
cell, _ = cell_at(img, 5, 4)
dL = np.linalg.norm(cell.astype(np.float32) - scan.LIGHT, axis=2)
dD = np.linalg.norm(cell.astype(np.float32) - scan.DARK, axis=2)
fg = (dL > scan.PAL_TOL) & (dD > scan.PAL_TOL)
px = cell[fg]
print("c.jpg e3: 像素", len(px), "BGR均值:", px.mean(axis=0).round(0).astype(int).tolist() if len(px) else None)
if len(px):
    hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)[fg]
    print("   HSV 中位:", np.median(hsv, axis=0).astype(int).tolist())
