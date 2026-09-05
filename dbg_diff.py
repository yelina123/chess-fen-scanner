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

cell = board[0 * CELL:1 * CELL, 4 * CELL:5 * CELL]
sil = cell_silhouette(cell)
tpl = scan.load_templates()
tm = tpl["alpha"][("b", "N")]

# 剪影与模板各自 bbox 归一化后 diff
def norm(m):
    ys, xs = np.where(m > 0)
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    m = cv2.resize(m, (scan.CAN, scan.CAN), interpolation=cv2.INTER_AREA)
    _, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
    return m

sn = norm(sil); tn = norm(tm)
both = np.count_nonzero((sn > 0) & (tn > 0))
only_s = np.count_nonzero((sn > 0) & (tn == 0))
only_t = np.count_nonzero((sn == 0) & (tn > 0))
print(f"交集={both} 仅剪影={only_s} 仅模板={only_t}  剪影{only_s}+交集={both+only_s} 模板{only_t}+交集={both+only_t}")

diff = np.zeros((scan.CAN, scan.CAN, 3), np.uint8)
diff[(sn > 0) & (tn > 0)] = (0, 200, 0)      # 绿=两者
diff[(sn > 0) & (tn == 0)] = (255, 0, 0)     # 蓝=仅剪影
diff[(sn == 0) & (tn > 0)] = (0, 0, 255)     # 红=仅模板
cv2.imwrite(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out2\diff_r0c4.png", diff)
# 原格放大
cv2.imwrite(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out2\cell_zoom.png", cv2.resize(cell, (308, 308)))
print("saved diff")
