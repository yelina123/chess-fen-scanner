# -*- coding: utf-8 -*-
"""7.jpg 全 64 格数值分析: frac/bright + 每格模板匹配 top3, 判断真实局面。"""
import sys, os
import cv2
import numpy as np
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import scan
from scan import imread_unicode, locate_board, classify, load_templates, overlay_mask, LIGHT, DARK, PAL_TOL, CAN, PIECES

tpl = load_templates()
img = imread_unicode(r"C:\Users\Administrator\Desktop\AI work\棋盘识别\检验图\7.jpg")
bbox = locate_board(img)
bx0, by0, bx1, by1 = [int(v) for v in bbox]
board = img[by0:by1, bx0:bx1]
ch, cw = board.shape[:2]
CELL = cw // 8
print("bbox", bbox, "CELL", CELL)

def analyze(cell):
    omask = overlay_mask(cell)
    dL = np.linalg.norm(cell.astype(np.float32) - LIGHT, axis=2)
    dD = np.linalg.norm(cell.astype(np.float32) - DARK, axis=2)
    fg = ((dL > PAL_TOL) & (dD > PAL_TOL)).astype(np.uint8) * 255
    fg[omask > 0] = 0
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3,3), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))
    num, lbl, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
    fg_big = fg
    if num > 1:
        idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fg_big = np.where(lbl == idx, 255, 0).astype(np.uint8)
    frac = np.count_nonzero(fg_big) / (cell.shape[0]*cell.shape[1])
    px = cell[fg_big > 0]
    bright = 0.0
    if len(px):
        lum = px.reshape(-1,3).mean(axis=1)
        bright = (lum > 200).mean()
    # 模板匹配 top3
    ys, xs = np.where(fg_big > 0)
    if len(xs) < 20 or frac < 0.03:
        return None, frac, bright, []
    cm = fg_big[ys.min():ys.max()+1, xs.min():xs.max()+1]
    cm = cv2.resize(cm, (CAN, CAN), interpolation=cv2.INTER_AREA)
    _, cm = cv2.threshold(cm, 127, 255, cv2.THRESH_BINARY)
    res = []
    for color in "wb":
        for piece in PIECES:
            tm = tpl[(color, piece)]
            inter = np.count_nonzero((cm>0)&(tm>0))
            union = np.count_nonzero((cm>0)|(tm>0))
            iou = inter/union if union else 0
            res.append((iou, color+piece))
    res.sort(reverse=True)
    return res[0][1], frac, bright, res[:3]

rank_names = ["8","7","6","5","4","3","2","1"]
file_names = ["a","b","c","d","e","f","g","h"]
print(f"{'格':>6} {'判别':>4} {'frac':>6} {'bright':>6}   top3")
for r in range(8):
    for c in range(8):
        cell = board[r*CELL:(r+1)*CELL, c*CELL:(c+1)*CELL]
        pc, frac, bright, top3 = analyze(cell)
        sq = file_names[c] + rank_names[r]
        if pc is None:
            print(f"{sq:>6} {'空':>4} {frac:6.3f} {bright:6.3f}")
        else:
            t3 = " ".join(f"{n}({v:.2f})" for v,n in top3)
            print(f"{sq:>6} {pc:>4} {frac:6.3f} {bright:6.3f}   {t3}")
