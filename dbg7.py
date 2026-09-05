# -*- coding: utf-8 -*-
"""画 7.jpg 棋盘定位 + 均匀格线叠加, 确认格子切分。"""
import sys, os
import cv2
import numpy as np
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import scan
from scan import imread_unicode, locate_board

img = imread_unicode(r"C:\Users\Administrator\Desktop\AI work\棋盘识别\检验图\7.jpg")
bbox = locate_board(img)
print("bbox:", bbox)
bx0, by0, bx1, by1 = [int(v) for v in bbox]
board = img[by0:by1, bx0:bx1].copy()
ch, cw = board.shape[:2]
for i in range(9):
    cv2.line(board, (i*cw//8, 0), (i*cw//8, ch), (0,0,255), 2)
    cv2.line(board, (0, i*ch//8), (cw, i*ch//8), (0,0,255), 2)
# 标注 d4 位置 (rank4=row4, col3=d) 的格子
cv2.rectangle(board, (3*cw//8, 4*ch//8), (4*cw//8, 5*ch//8), (0,255,0), 3)
cv2.putText(board, "d4?", (3*cw//8+4, 4*ch//8+20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
cv2.imencode(".png", board)[1].tofile(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg7_grid.png")
print("saved dbg7_grid.png", board.shape)
