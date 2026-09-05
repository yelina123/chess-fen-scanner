# -*- coding: utf-8 -*-
"""实验: 多种"细线剔除 + 匹配得分"方案, 在补充图 a/b/c 与真实图 1-7 上对比。"""
import sys, os
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
    return fg

def thick(fg, R):
    dist = cv2.distanceTransform(fg, cv2.DIST_L2, 5)
    return np.where(dist > R, 255, 0).astype(np.uint8)

def to_can(m):
    ys, xs = np.where(m > 0)
    if len(xs) == 0:
        return None
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    m = cv2.resize(m, (CAN, CAN), interpolation=cv2.INTER_AREA)
    _, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
    return m

def match(cm, tpl, color, scname, tm_thick=0):
    best = (-1.0, None)
    for tset in tpl.values():
        for pc in PIECES:
            tm = tset[(color, pc)]
            if tm_thick > 0:
                dist = cv2.distanceTransform((tm > 0).astype(np.uint8), cv2.DIST_L2, 5)
                tm = np.where(dist > tm_thick, 255, 0).astype(np.uint8)
            inter = np.count_nonzero((cm > 0) & (tm > 0))
            union = np.count_nonzero((cm > 0) | (tm > 0))
            tarea = np.count_nonzero(tm > 0)
            iou = inter / union if union else 0
            rec = inter / tarea if tarea else 0
            if scname == "iou":
                score = iou
            elif scname == "rec":
                score = rec
            elif scname == "min":
                score = min(iou, rec)
            elif scname == "geomean":
                score = (iou * rec) ** 0.5
            if score > best[0]:
                best = (score, pc)
    return best

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

def classify_variant(cell, tpl, variant, R, scname, trim=0):
    fg = fg_full(cell)
    ch, cw = cell.shape[:2]
    if variant.startswith("thick"):
        dist = cv2.distanceTransform(fg, cv2.DIST_L2, 5)
        Rc = int(round(R * scan.CAN / 144.0))
        fg = np.where(dist > Rc, 255, 0).astype(np.uint8)
    else:
        num, lbl, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
        if num > 1:
            idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            fg = np.where(lbl == idx, 255, 0).astype(np.uint8)
    frac = np.count_nonzero(fg) / (ch * cw)
    if frac < 0.03:
        return None
    cm = to_can(fg)
    if cm is None:
        return None
    px = cell[fg > 0]
    lum = px.reshape(-1, 3).mean(axis=1)
    color = "w" if (lum > 200).mean() > 0.33 else "b"
    score, piece = match(cm, tpl, color, scname)
    # 低分恢复格: 格边细带剔除后重新匹配类型
    if trim > 0 and score < 0.9:
        fg2 = edge_trim(fg, trim)
        if np.count_nonzero(fg2) > 0.05 * ch * cw:
            cm2 = to_can(fg2)
            if cm2 is not None:
                score2, piece2 = match(cm2, tpl, color, scname)
                if score2 > score + 0.02:
                    score, piece = score2, piece2
    return color + piece, score, frac

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

def run(img, tpl, variant, R, thresh, scname, frac_recover=0.0, trim=0):
    bbox = scan.locate_board(img)
    if bbox is None:
        return "8/8/8/8/8/8/8/8", None
    x0, y0, x1, y1 = [int(v) for v in bbox]
    board = img[y0:y1, x0:x1]
    CELL = board.shape[0] // 8
    grid = [[None] * 8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            cell = board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
            res = classify_variant(cell, tpl, variant, R, scname, trim)
            if res is None:
                grid[r][c] = None
            else:
                piece, score, frac = res
                keep = score >= thresh or (frac_recover > 0 and frac > frac_recover)
                grid[r][c] = piece if keep else None
    fen, rot = scan.best_orientation(grid)
    return fen, rot

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
variants = ["base"]
scnames = ["iou", "min"]
threshs = [0.85]
frac_recovers = [0.22]
trims = [0, 10, 12, 15]

for variant in variants:
    R = int(variant.replace("thickR", "")) if variant.startswith("thickR") else 0
    for scname in scnames:
        for th in threshs:
            for fr in frac_recovers:
                for tr in trims:
                    rows = []
                    for name, truth in SUPP.items():
                        img = scan.imread_unicode(rf"{DIR_SUPP}\{name}.jpg")
                        fen, rot = run(img, tpl, variant, R, th, scname, fr, tr)
                        g, t = expand(fen), expand(truth)
                        rows.append(sum(1 for r in range(8) for c in range(8) if g[r][c] == t[r][c]))
                    real_ok = 0
                    for name, truth in REAL.items():
                        img = scan.imread_unicode(rf"{DIR_REAL}\{name}.jpg")
                        fen, rot = run(img, tpl, variant, R, th, scname, fr, tr)
                        g, t = expand(fen), expand(truth)
                        real_ok += sum(1 for r in range(8) for c in range(8) if g[r][c] == t[r][c])
                    print(f"{variant:9s} {scname:7s} th={th:<4} fracR={fr:<4} trim={tr:<3} 补充={rows[0]}/{rows[1]}/{rows[2]} ({sum(rows)}/192)  真实={real_ok}/448")
