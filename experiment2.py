# -*- coding: utf-8 -*-
"""实验: bbox crop vs dist峰值锚定 crop, 全量对比。"""
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import cv2, numpy as np
import scan

CAN = scan.CAN
PIECES = "KQRBNP"

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

def to_can_bbox(m):
    ys, xs = np.where(m > 0)
    if len(xs) == 0:
        return None
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    m = cv2.resize(m, (CAN, CAN), interpolation=cv2.INTER_AREA)
    _, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
    return m

def to_can_anchor(m, frac):
    h, w = m.shape
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    _, _, _, maxLoc = cv2.minMaxLoc(dist)
    cx, cy = maxLoc
    half = int(round(h * frac / 2))
    pad = np.zeros((h + 2 * half, w + 2 * half), np.uint8)
    pad[half:half + h, half:half + w] = m
    x1 = half + cx - half
    y1 = half + cy - half
    sub = pad[y1:y1 + 2 * half, x1:x1 + 2 * half]
    sub = cv2.resize(sub, (CAN, CAN), interpolation=cv2.INTER_AREA)
    _, sub = cv2.threshold(sub, 127, 255, cv2.THRESH_BINARY)
    return sub

def match(cm, tpl, color):
    best = (-1.0, None)
    for tset in tpl.values():
        for pc in PIECES:
            tm = tset[(color, pc)]
            inter = np.count_nonzero((cm > 0) & (tm > 0))
            union = np.count_nonzero((cm > 0) | (tm > 0))
            iou = inter / union if union else 0
            if iou > best[0]:
                best = (iou, pc)
    return best

def classify(cell, tpl, crop_mode, frac, thresh, frac_recover):
    fg = fg_full(cell)
    h, w = cell.shape[:2]
    fracpx = np.count_nonzero(fg) / (h * w)
    if fracpx < 0.03:
        return None
    cm = to_can_anchor(fg, frac) if crop_mode == "anchor" else to_can_bbox(fg)
    if cm is None:
        return None
    px = cell[fg > 0]
    lum = px.reshape(-1, 3).mean(axis=1)
    color = "w" if (lum > 200).mean() > 0.33 else "b"
    score, piece = match(cm, tpl, color)
    keep = score >= thresh or fracpx > frac_recover
    return color + piece if keep else None

def expand(f):
    g = []
    for rank in f.split("/"):
        row = []
        for ch in rank:
            if ch.isdigit():
                row += ["."] * int(ch)
            else:
                row.append(ch)
        g.append(row)
    return g

def run(img, tpl, crop_mode, frac, thresh, frac_recover):
    bbox = scan.locate_board(img)
    if bbox is None:
        return "8/8/8/8/8/8/8/8"
    x0, y0, x1, y1 = [int(v) for v in bbox]
    board = img[y0:y1, x0:x1]
    CELL = board.shape[0] // 8
    grid = [[None] * 8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            cell = board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
            grid[r][c] = classify(cell, tpl, crop_mode, frac, thresh, frac_recover)
    fen, _ = scan.best_orientation(grid)
    return fen

SUPP = {
    "a": "rnbqkbnr/pppp1ppp/8/4p3/3P4/8/PPP1PPPP/RNBQKBNR",
    "b": "r1bqkbnr/pppp1ppp/2n5/4P3/8/8/PPP1PPPP/RNBQKBNR",
    "c": "r1bqk1nr/ppp2ppp/2n5/2bpP3/5B2/5N2/PPP1PPPP/RN1QKB1R",
}
REAL = {
    "1": "r1bq1bnr/4k3/p3p1Bp/3pPpp1/Np6/4PN2/1PP2PPP/R2QR1K1",
    "2": "2r2rk1/pbq2ppp/2n1p1n1/1p2P3/2N5/P4N2/1BQ1BPPP/3R1RK1",
    "3": "5rk1/pr3ppp/3Rp1n1/1p2N3/8/P7/1Bq1BPPP/5RK1",
    "4": "r2q1rk1/ppp2ppp/2np1n2/1Bb1p3/4P3/2P2Q1P/PP1P1PP1/RNB1R1K1",
    "5": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR",
    "6": "6k1/1p1n3p/2p1p1p1/2PpP1qr/3P4/P2P1Q2/5BK1/2R5",
    "7": "rnb1kbnr/ppppp1Qp/8/8/2q5/8/P2PPPPP/RNB1KBNR",
}
DIR_SUPP = r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\test_supplement"
DIR_REAL = r"C:\Users\Administrator\Desktop\AI work\棋盘识别\检验图"

tpl = scan.load_templates()
modes = [("bbox", 0.0), ("anchor", 0.8), ("anchor", 0.85), ("anchor", 0.9), ("anchor", 0.95)]
for crop_mode, frac in modes:
    rows = []
    for name, truth in SUPP.items():
        img = scan.imread_unicode(rf"{DIR_SUPP}\{name}.jpg")
        fen = run(img, tpl, crop_mode, frac, 0.85, 0.22)
        g, t = expand(fen), expand(truth)
        rows.append(sum(1 for r in range(8) for c in range(8) if g[r][c] == t[r][c]))
    real_ok = 0
    for name, truth in REAL.items():
        img = scan.imread_unicode(rf"{DIR_REAL}\{name}.jpg")
        fen = run(img, tpl, crop_mode, frac, 0.85, 0.22)
        g, t = expand(fen), expand(truth)
        real_ok += sum(1 for r in range(8) for c in range(8) if g[r][c] == t[r][c])
    print(f"{crop_mode:6s} frac={frac:<4} 补充={rows[0]}/{rows[1]}/{rows[2]} ({sum(rows)}/192)  真实={real_ok}/448")
