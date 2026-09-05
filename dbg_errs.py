# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner")
import cv2, numpy as np
import scan

CAN = scan.CAN
PIECES = "KQRBNP"
BASE = r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\test_supplement"
SUPP = {
    "a": "rnbqkbnr/pppp1ppp/8/4p3/3P4/8/PPP1PPPP/RNBQKBNR",
    "b": "r1bqkbnr/pppp1ppp/2n5/4P3/8/8/PPP1PPPP/RNBQKBNR",
    "c": "r1bqk1nr/ppp2ppp/2n5/2bpP3/5B2/5N2/PPP1PPPP/RN1QKB1R",
}

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

def analyze(cell, tpl, scname="iou"):
    fg = fg_full(cell)
    ch, cw = cell.shape[:2]
    frac = np.count_nonzero(fg) / (ch * cw)
    if frac < 0.03:
        return None, 0, None, frac
    cm = to_can(fg)
    px = cell[fg > 0]
    lum = px.reshape(-1, 3).mean(axis=1)
    color = "w" if (lum > 200).mean() > 0.33 else "b"
    best = (-1.0, None)
    for tset in tpl.values():
        for pc in PIECES:
            tm = tset[(color, pc)]
            inter = np.count_nonzero((cm > 0) & (tm > 0))
            union = np.count_nonzero((cm > 0) | (tm > 0))
            tarea = np.count_nonzero(tm > 0)
            iou = inter / union if union else 0
            rec = inter / tarea if tarea else 0
            score = iou if scname == "iou" else min(iou, rec)
            if score > best[0]:
                best = (score, pc)
    return color + best[1], best[0], None, frac

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

tpl = scan.load_templates()
for scname, th in [("iou", 0.85), ("min", 0.85)]:
    print(f"===== 得分={scname} 阈值={th} =====")
    for name, truth in SUPP.items():
        img = scan.imread_unicode(rf"{BASE}\{name}.jpg")
        bbox = scan.locate_board(img)
        x0, y0, x1, y1 = [int(v) for v in bbox]
        board = img[y0:y1, x0:x1]
        CELL = board.shape[0] // 8
        t = expand(truth)
        errs = []
        for r in range(8):
            for c in range(8):
                cell = board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
                res, score, _, frac = analyze(cell, tpl, scname)
                pred = res if res and score >= th else "."
                if pred != t[r][c]:
                    errs.append((f"r{r}c{c}", f"答案={t[r][c]}", f"识别={pred}", f"score={score:.2f}", f"frac={frac:.3f}"))
        print(f"{name}.jpg: {64-len(errs)}/64", errs if errs else "")
