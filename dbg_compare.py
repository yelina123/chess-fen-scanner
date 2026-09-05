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
    return fg

name = "alpha_00"
img = imread_unicode(rf"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\synth_imgs\{name}.jpg")
x0, y0, x1, y1 = [int(v) for v in locate_board(img)]
board = img[y0:y1, x0:x1]
CELL = board.shape[0] // 8
truth = expand(open(rf"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\synth_imgs\{name}.txt").read().strip())

# 找出 r0c4 的骑士格, 存剪影 + 原格 + 模板
cell = board[0 * CELL:1 * CELL, 4 * CELL:5 * CELL]
sil = cell_silhouette(cell)
cv2.imwrite(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out2\cell_r0c4.png", cell)
cv2.imwrite(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out2\sil_r0c4.png", sil)
tpl = scan.load_templates()
tm = tpl["alpha"][("b", "N")]
cv2.imwrite(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out2\tpl_bN.png", tm)
# 套件里的 bN 彩色原图
bN = cv2.imread(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\assets\pieces\alpha\png\bN_90.png", cv2.IMREAD_UNCHANGED)
cv2.imwrite(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out2\alpha_bN.png", bN)
# 拼接对比图: 原格 | 剪影 | 模板
h1 = cv2.resize(cell, (160, 160))
h2 = cv2.cvtColor(cv2.resize(sil, (160, 160)), cv2.COLOR_GRAY2BGR)
h3 = cv2.cvtColor(cv2.resize(tm, (160, 160)), cv2.COLOR_GRAY2BGR)
stack = np.hstack([h1, h2, h3])
for i, t in enumerate(["原格", "提取剪影", "alpha bN 模板"]):
    cv2.putText(stack, t, (i * 160 + 5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
cv2.imwrite(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out2\compare_r0c4.png", stack)
print("saved. sil bbox size:", np.where(sil>0)[0].max()-np.where(sil>0)[0].min()+1, "x", np.where(sil>0)[1].max()-np.where(sil>0)[1].min()+1)
print("tpl bbox size:", np.where(tm>0)[0].max()-np.where(tm>0)[0].min()+1, "x", np.where(tm>0)[1].max()-np.where(tm>0)[1].min()+1)
