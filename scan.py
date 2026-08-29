# -*- coding: utf-8 -*-
"""
ChessScan 初版命令行工具
用法:
    python scan.py <棋盘图片路径...>
    python scan.py 图片1.jpg 图片2.jpg
输出: 识别出的 FEN 摆放段 + 每格识别详情(可选 --verbose)

核心: 基于 OpenCV 的纯剪影识别, 离线运行, 无第三方 ML 依赖。
"""
import sys
import os
import cv2
import numpy as np
import argparse

# ---------------- 常量 ----------------
LIGHT = np.array([182, 216, 239], np.float32)   # 浅格 (BGR)
DARK = np.array([97, 137, 180], np.float32)     # 深格 (BGR)
PAL_TOL = 34
CAN = 64
PIECES = "KQRBNP"

# 模板 PNG 目录 (cburnett 棋子剪影)
TDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "pieces", "cburnett", "png")


def imread_unicode(path):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


# ---------------- 模板剪影 ----------------
def load_templates(tdir=TDIR):
    tpl = {}
    if not os.path.isdir(tdir):
        print(f"[warn] 模板目录不存在: {tdir}")
        return tpl
    for color in "wb":
        for piece in PIECES:
            f = os.path.join(tdir, f"{color}{piece}_90.png")
            im = cv2.imread(f, cv2.IMREAD_UNCHANGED)
            if im is None:
                continue
            a = (im[:, :, 3] > 128).astype(np.uint8) * 255
            ys, xs = np.where(a > 0)
            if len(xs):
                a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            a = cv2.resize(a, (CAN, CAN), interpolation=cv2.INTER_AREA)
            _, a = cv2.threshold(a, 127, 255, cv2.THRESH_BINARY)
            tpl[(color, piece)] = a
    return tpl


# ---------------- 高亮掩膜 (绿色/黄色/红色 -> 背景) ----------------
def highlight_mask(cell):
    hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0].astype(np.int32)
    s = hsv[:, :, 1].astype(np.int32)
    v = hsv[:, :, 2].astype(np.int32)
    green = (h >= 35) & (h <= 85) & (s > 40) & (v > 60)
    yellow = (h >= 12) & (h < 35) & (s > 50) & (v > 100)
    red = (((h <= 10) | (h >= 170)) & (s > 40) & (v > 60))
    return (green | yellow | red).astype(np.uint8) * 255


# ---------------- 单格分类 ----------------
def classify(cell, tpl):
    ch, cw = cell.shape[:2]
    hmask = highlight_mask(cell)
    # 前景 = 与两种棋盘底色(LIGHT/DARK)距离都大的像素(棋子既非浅格也非深格色)。
    # 相比"格子内均值"背景(会被深色格上的黑棋子拉暗导致黑子漏检), 此法对黑白棋子都稳定。
    dL = np.linalg.norm(cell.astype(np.float32) - LIGHT, axis=2)
    dD = np.linalg.norm(cell.astype(np.float32) - DARK, axis=2)
    fg = ((dL > PAL_TOL) & (dD > PAL_TOL)).astype(np.uint8) * 255
    fg[hmask > 0] = 0
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    num, lbl, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
    if num > 1:
        idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fg = np.where(lbl == idx, 255, 0).astype(np.uint8)
    frac = np.count_nonzero(fg) / (ch * cw)
    if frac < 0.03:
        return None, 0.0, frac
    px = cell[fg > 0]
    lum_arr = px.reshape(-1, 3).mean(axis=1)
    lum = lum_arr.mean()
    med = np.median(lum_arr)
    bright = (lum_arr > 200).mean()
    dark = (lum_arr < 80).mean()
    # 白棋主体有大量亮像素(≥0.35); 黑棋主体暗, 亮像素少(≤0.27)。用亮像素占比判色。
    color = "w" if bright > 0.33 else "b"
    ys, xs = np.where(fg > 0)
    cm = fg[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    cm = cv2.resize(cm, (CAN, CAN), interpolation=cv2.INTER_AREA)
    _, cm = cv2.threshold(cm, 127, 255, cv2.THRESH_BINARY)
    best_iou = -1; best_piece = None
    for piece in PIECES:
        tm = tpl[(color, piece)]
        inter = np.count_nonzero((cm > 0) & (tm > 0))
        union = np.count_nonzero((cm > 0) | (tm > 0))
        iou = inter / union if union else 0
        if iou > best_iou:
            best_iou = iou; best_piece = piece
    return color + best_piece, best_iou, frac


# ---------------- 棋盘定位 ----------------
def locate_board(img):
    h, w = img.shape[:2]
    rgb = img.astype(np.float32)
    bm = ((np.linalg.norm(rgb - LIGHT, axis=2) < PAL_TOL) |
          (np.linalg.norm(rgb - DARK, axis=2) < PAL_TOL)).astype(np.uint8) * 255
    filled = cv2.morphologyEx(bm, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (35, 35)))
    filled = cv2.morphologyEx(filled, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)))
    row = filled.mean(axis=1) / 255.0

    def span(f, thr):
        on = f > thr; best = (0, 0); s = None
        for i, v in enumerate(on):
            if v and s is None: s = i
            elif not v and s is not None:
                if i - s > best[1] - best[0]: best = (s, i)
                s = None
        if s is not None and len(on) - s > best[1] - best[0]: best = (s, len(on))
        return best

    y0, y1 = span(row, 0.4)
    if y1 - y0 < 0.2 * h:
        return None
    band = filled[y0:y1]
    col = band.mean(axis=0) / 255.0
    x0, x1 = span(col, 0.35)
    if x1 - x0 < 0.2 * w:
        return None
    # 棋盘为正方形: 边长取行带高度(竖屏截图行投影最可靠),
    # 水平方向以列中点为中心取同样边长。
    side = int(y1 - y0)
    cx = (x0 + x1) // 2
    bx0 = max(0, cx - side // 2); by0 = y0
    bx1 = min(w, bx0 + side); by1 = min(h, by0 + side)
    # 若水平被裁剪, 回落为以左边缘对齐 (lichess 截图棋盘常紧贴左缘)
    if bx1 - bx0 < side:
        bx0 = max(0, x0)
        bx1 = min(w, bx0 + side)
        by1 = min(h, by0 + side)
    return (bx0, by0, bx1, by1)


# ---------------- FEN 拼装 + 自动旋转 ----------------
def grid_to_fen(grid):
    ranks = []
    for r in range(8):
        s = ""; e = 0
        for c in range(8):
            pc = grid[r][c]
            if pc is None or pc == ".":
                e += 1
            else:
                if e: s += str(e); e = 0
                s += pc[1].upper() if pc[0] == "w" else pc[1].lower()
        if e: s += str(e)
        ranks.append(s)
    return "/".join(ranks)


def best_orientation(grid):
    arr = np.array([[grid[r][c] if grid[r][c] else "." for c in range(8)] for r in range(8)])
    best = None
    for rot in range(4):
        g = np.rot90(arr, rot)
        g = [[g[r][c] for c in range(8)] for r in range(8)]
        f = grid_to_fen(g)
        wb = sum(1 for r in (6, 7) for c in range(8) if g[r][c] and g[r][c][0] == "w")
        wt = sum(1 for r in (0, 1) for c in range(8) if g[r][c] and g[r][c][0] == "w")
        bb = sum(1 for r in (6, 7) for c in range(8) if g[r][c] and g[r][c][0] == "b")
        bt = sum(1 for r in (0, 1) for c in range(8) if g[r][c] and g[r][c][0] == "b")
        score = (wb + bt) - (wt + bb)
        if any(g[r][c] and g[r][c] == "wK" for r in (4, 5, 6, 7) for c in range(8)):
            score += 2
        if best is None or score > best[0]:
            best = (score, f, rot)
    if best:
        return best[1], best[2]
    return grid_to_fen(arr), 0


# ---------------- 主识别 ----------------
def recognize(img, tpl, verbose=False):
    bbox = locate_board(img)
    if bbox is None:
        return None, None, None
    bx0, by0, bx1, by1 = [int(v) for v in bbox]
    board = img[by0:by1, bx0:bx1]
    ch, cw = board.shape[:2]
    CELL = cw // 8
    grid = [[None] * 8 for _ in range(8)]
    conf = [[0.0] * 8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            cell = board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
            grid[r][c], iou, frac = classify(cell, tpl)
            conf[r][c] = iou
    fen, rot = best_orientation(grid)
    return fen, (bx0, by0, bbox[2], bbox[3], rot, board, grid, conf)


def draw_result(img, board, grid, bx0, by0, rot):
    """画识别结果到原图副本, 便于人工核验。"""
    ov = img.copy()
    # 棋盘框
    bx1, by1 = bx0 + board.shape[1], by0 + board.shape[0]
    cv2.rectangle(ov, (bx0, by0), (bx1, by1), (0, 255, 0), 3)
    ch, cw = board.shape[:2]
    CELL = cw // 8
    # 标注每个格子的识别结果 (按最终方向的排布直接叠在棋盘格上)
    annot = np.rot90(np.array([[grid[r][c] if grid[r][c] else "." for c in range(8)] for r in range(8)]), rot)
    for r in range(8):
        for c in range(8):
            pc = annot[r][c]
            txt = pc if pc != "." else "."
            col = (0, 255, 0) if pc != "." else (255, 255, 255)
            cv2.putText(ov, txt, (bx0 + c * CELL + 4, by0 + r * CELL + CELL - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
    return ov


def main():
    ap = argparse.ArgumentParser(description="ChessScan 棋盘识别 -> FEN")
    ap.add_argument("images", nargs="+", help="棋盘图片路径")
    ap.add_argument("--verbose", action="store_true", help="输出每格置信度")
    ap.add_argument("--no-vis", action="store_true", help="不保存可视化结果图")
    args = ap.parse_args()

    tpl = load_templates()
    if not tpl:
        print("错误: 未找到棋子模板, 请确认 assets/pieces/cburnett/png 存在")
        sys.exit(1)

    print(f"模板数量: {len(tpl)}")
    for img_path in args.images:
        img = imread_unicode(img_path)
        if img is None:
            print(f"[错误] 无法读取 {img_path}")
            continue
        fen, info = recognize(img, tpl, args.verbose)
        if fen is None:
            print(f"{os.path.basename(img_path)}: 定位不到棋盘")
            continue
        bx0, by0, bx1, by1, rot, board, grid, conf = info
        print(f"\n{os.path.basename(img_path)}")
        print(f"  定位: ({bx0},{by0})-({bx1},{by1}), 旋转={rot}")
        print(f"  摆放段: {fen}")
        print(f"  完整FEN: {fen} w - - 0 1")
        if args.verbose:
            print("  8x8识别(rank8 top, 未旋转):")
            for r in range(8):
                row = "  ".join(f"{grid[r][c] or '..':>2}" for c in range(8))
                print(f"    {row}")
        if not args.no_vis:
            vis = draw_result(img, board, grid, bx0, by0, rot)
            out = os.path.splitext(img_path)[0] + "_scan.png"
            cv2.imencode(".png", vis)[1].tofile(out)
            print(f"  可视化已保存: {out}")


if __name__ == "__main__":
    main()
