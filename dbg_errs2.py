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

def scores_vs(cell, tpl, color):
    fg = fg_full(cell)
    cm = to_can(fg)
    if cm is None:
        return None
    out = {}
    for tset in tpl.values():
        for pc in PIECES:
            tm = tset[(color, pc)]
            inter = np.count_nonzero((cm > 0) & (tm > 0))
            union = np.count_nonzero((cm > 0) | (tm > 0))
            tarea = np.count_nonzero(tm > 0)
            out[pc] = (inter / union if union else 0, inter / tarea if tarea else 0)
    return out

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
for name, truth in SUPP.items():
    img = scan.imread_unicode(rf"{BASE}\{name}.jpg")
    bbox = scan.locate_board(img)
    x0, y0, x1, y1 = [int(v) for v in bbox]
    board = img[y0:y1, x0:x1]
    CELL = board.shape[0] // 8
    t = expand(truth)
    print(f"===== {name}.jpg =====")
    for r in range(8):
        for c in range(8):
            ch = t[r][c]
            cell = board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
            fg = fg_full(cell)
            frac = np.count_nonzero(fg) / fg.size
            color = "w" if ch.isupper() else "b"
            sc = scores_vs(cell, tpl, color)
            if sc is None or ch == ".":
                # 空格: 看 fg 是否有东西(箭头)
                if frac > 0.02:
                    # 计算该格与两色模板的最佳 iou/rec
                    best = (0, 0, None)
                    for col2 in "wb":
                        sc2 = scores_vs(cell, tpl, col2) or {}
                        for pc, (iou, rec) in sc2.items():
                            if iou > best[0]:
                                best = (iou, rec, col2 + pc)
                    print(f"r{r}c{c} 空格但fg={frac:.2f}: 最佳 {best[2]} iou={best[0]:.2f} rec={best[1]:.2f}")
                continue
            iou_t, rec_t = sc.get(ch.upper(), (0, 0))
            # 该格最佳
            best = max(sc.items(), key=lambda kv: kv[1][0])
            flag = ""
            if iou_t < 0.85:
                flag = "  <-- 本尊得分低!"
            print(f"r{r}c{c} 真子{ch}: 本尊 iou={iou_t:.2f} rec={rec_t:.2f} | 最佳 {best[0]} iou={best[1][0]:.2f}{flag}")
