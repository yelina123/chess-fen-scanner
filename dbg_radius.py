# -*- coding: utf-8 -*-
"""验证: 距离变换最大内接圆半径能否区分 棋子块 / 箭头线 / 空格。"""
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

def max_radius(fg):
    dist = cv2.distanceTransform(fg, cv2.DIST_L2, 5)
    return dist.max()

def board_cells(img):
    bbox = scan.locate_board(img)
    x0, y0, x1, y1 = [int(v) for v in bbox]
    board = img[y0:y1, x0:x1]
    CELL = board.shape[0] // 8
    return board, CELL

def expand(fen):
    g = []
    for rank in fen.split("/"):
        row = []
        for ch in rank:
            if ch.isdigit():
                row += ["."] * int(ch)
            else:
                row.append(ch)
        g.append(row)
    return g

TRUTHS = {
    "a": "rnbqkbnr/pppp1ppp/8/4p3/3P4/8/PPP1PPPP/RNBQKBNR",
    "b": "r1bqkbnr/pppp1ppp/2n5/4P3/8/8/PPP1PPPP/RNBQKBNR",
    "c": "r1bqk1nr/ppp2ppp/2n5/2bpP3/5B2/5N2/PPP1PPPP/RN1QKB1R",
}
BASE = r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\test_supplement"

for name, truth in TRUTHS.items():
    img = scan.imread_unicode(rf"{BASE}\{name}.jpg")
    board, CELL = board_cells(img)
    g = expand(truth)
    stats = {"子": [], "空格": []}
    for r in range(8):
        for c in range(8):
            cell = board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
            fg = fg_mask(cell)
            mr = max_radius(fg)
            kind = "子" if g[r][c] != "." else "空格"
            stats[kind].append((mr, f"r{r}c{c}"))
    for kind in ["子", "空格"]:
        vals = sorted(stats[kind])
        mrs = [v[0] for v in vals]
        print(f"{name}.jpg {kind}: 最小半径 {mrs[0]:.1f} (格 {vals[0][1]}), 中位 {np.median(mrs):.1f}, 最大 {mrs[-1]:.1f} (格 {vals[-1][1]})")
        # 打印半径 < CELL*0.06 的空格(会被误判为箭头)
        th = CELL * 0.06
        small = [v for v in vals if v[0] < th]
        if small:
            print(f"   半径<{th:.1f} 的格子: {small}")
