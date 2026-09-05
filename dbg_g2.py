# -*- coding: utf-8 -*-
"""诊断 b.jpg g2 (r6c6): fg 触边、trim 各半径下匹配分。"""
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

def edge_trim(fg, R):
    dist = cv2.distanceTransform(fg, cv2.DIST_L2, 5)
    thin = np.where((fg > 0) & (dist <= R), 255, 0).astype(np.uint8)
    if np.count_nonzero(thin) == 0:
        return fg
    num, lbl = cv2.connectedComponents(thin, 8)
    border_lbls = set(lbl[0, :].tolist() + lbl[-1, :].tolist() + lbl[:, 0].tolist() + lbl[:, -1].tolist())
    border_lbls.discard(0)
    if not border_lbls:
        return fg
    remove = np.zeros_like(fg)
    for L in border_lbls:
        remove[lbl == L] = 255
    return np.where((fg > 0) & (remove == 0), 255, 0).astype(np.uint8)

img = scan.imread_unicode(rf"{BASE}\b.jpg")
bbox = scan.locate_board(img)
x0, y0, x1, y1 = [int(v) for v in bbox]
board = img[y0:y1, x0:x1]
CELL = board.shape[0] // 8
tpl = scan.load_templates()

r, c = 6, 6
cell = board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
fg = fg_full(cell)
print("fg 像素:", np.count_nonzero(fg), "/", fg.size)
# 触边检测
touch = {
    "上": np.count_nonzero(fg[0, :]), "下": np.count_nonzero(fg[-1, :]),
    "左": np.count_nonzero(fg[:, 0]), "右": np.count_nonzero(fg[:, -1]),
}
print("触边像素:", touch)
dist = cv2.distanceTransform(fg, cv2.DIST_L2, 5)
print("最大内接圆半径:", round(float(dist.max()), 1))

def match_all(fg2, tag):
    cm = to_can(fg2)
    px = cell[fg2 > 0]
    lum = px.reshape(-1, 3).mean(axis=1)
    color = "w" if (lum > 200).mean() > 0.33 else "b"
    print(f"--- {tag} (color={color}, fg={np.count_nonzero(fg2)}) ---")
    for pc in PIECES:
        bi = 0.0
        for tset in tpl.values():
            tm = tset[(color, pc)]
            inter = np.count_nonzero((cm > 0) & (tm > 0))
            union = np.count_nonzero((cm > 0) | (tm > 0))
            bi = max(bi, inter / union if union else 0)
        print(f"   {pc}: {bi:.3f}")

match_all(fg, "原始")
for R in [8, 10, 12, 15, 18, 20]:
    fg2 = edge_trim(fg, R)
    match_all(fg2, f"trim R={R}")

# 保存图
cv2.imwrite(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out2\g2_raw.png", cell)
cv2.imwrite(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out2\g2_fg.png", fg)
cv2.imwrite(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out2\g2_trim15.png", edge_trim(fg, 15))
