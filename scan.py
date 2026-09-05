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

# 识别算法档位: (best_iou 阈值, frac 面积阈值)。
# 判空规则: best_iou < IOU_TH 且 frac <= FRAC_TH -> 判空(箭头/干扰);
#   iou 低但 frac 大 -> 被污染的真子, 保留。
# 阈值由 mode_analysis.py 在 10 张图 640 格上标定(空格最高 iou=0.802/frac=0.177,
# 真子最低 iou=0.576 但 frac>=0.265):
#   standard  居中(已验证 448/448 + 191/192);
#   recall    判空更保守, 倾向保留棋子(截图模糊/棋子小容易漏子时用);
#   precision 判空更积极, 倾向判空(箭头/标注多容易误判时用)。
MODE_PARAMS = {
    "standard":  (0.85, 0.22),
    "recall":    (0.81, 0.18),
    "precision": (0.90, 0.26),
}

# 模板 PNG 目录 (cburnett 棋子剪影)
TDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "pieces", "cburnett", "png")


def imread_unicode(path):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


# ---------------- 模板剪影 ----------------
def load_templates(tdir_root=None):
    """加载 assets/pieces/<set>/png/ 下全部棋子套件的剪影模板。
    返回 {set_name: {(color, piece): mat}}。识别时遍历所有套件取最佳 IoU,
    从而兼容 lichess/chess.com 上多种棋子样式。"""
    root = tdir_root or os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "pieces")
    tpl = {}
    if not os.path.isdir(root):
        print(f"[warn] 模板根目录不存在: {root}")
        return tpl
    for sname in sorted(os.listdir(root)):
        pdir = os.path.join(root, sname, "png")
        if not os.path.isdir(pdir):
            continue
        stpl = {}
        for color in "wb":
            for piece in PIECES:
                f = os.path.join(pdir, f"{color}{piece}_90.png")
                im = cv2.imread(f, cv2.IMREAD_UNCHANGED)
                if im is None:
                    continue
                a = (im[:, :, 3] > 128).astype(np.uint8) * 255
                ys, xs = np.where(a > 0)
                if len(xs):
                    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
                a = cv2.resize(a, (CAN, CAN), interpolation=cv2.INTER_AREA)
                _, a = cv2.threshold(a, 127, 255, cv2.THRESH_BINARY)
                stpl[(color, piece)] = a
        if len(stpl) == 12:
            tpl[sname] = stpl
    return tpl


# ---------------- 干扰掩膜: 走子高亮 + 引擎标注徽章 (?, !!, ! 等) ----------------
def overlay_mask(cell):
    hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0].astype(np.int32)
    s = hsv[:, :, 1].astype(np.int32)
    v = hsv[:, :, 2].astype(np.int32)
    # 引擎标注徽章(?,!!,! 等): 高饱和+高亮度的彩色小圆, 偏离棋盘色
    badge = (s > 150) & (v > 190)
    # 走子高亮: 黄(h≈30)/绿(h 35-85) 半透明覆盖, 偏色; 红色为被将/红方高亮
    # 注意: 黄色高亮(如 lichess 上一步高亮 h≈30)曾漏掩膜导致整格被判为前景大块→误判成车, 现并入
    highlight = (h >= 15) & (h <= 85) & (s > 40) & (v > 60)
    red = ((h <= 10) | (h >= 170)) & (s > 40) & (v > 60)
    return (badge | highlight | red).astype(np.uint8) * 255


# ---------------- 单格分类 ----------------
def classify(cell, tpl, mode="standard", theme=None, assume_clean=False):
    """tpl: load_templates() 返回的全部套件; theme=None 时遍历全部套件,
    否则只用指定套件名(用户在 App 内手动指定棋子主题)。mode 见 MODE_PARAMS。
    assume_clean=True 表示用户确认图中无引擎箭头/?/! 等标注, 跳过箭头判空,
    直接取最佳匹配(更准确, 不会把真子误判空)。走子高亮掩膜仍保留。"""
    iou_th, frac_th = MODE_PARAMS.get(mode, MODE_PARAMS["standard"])
    ch, cw = cell.shape[:2]
    omask = overlay_mask(cell)
    # 前景 = 与两种棋盘底色(LIGHT/DARK)距离都大的像素(棋子既非浅格也非深格色)。
    dL = np.linalg.norm(cell.astype(np.float32) - LIGHT, axis=2)
    dD = np.linalg.norm(cell.astype(np.float32) - DARK, axis=2)
    fg = ((dL > PAL_TOL) & (dD > PAL_TOL)).astype(np.uint8) * 255
    fg[omask > 0] = 0   # 走子高亮/引擎标注徽章不是棋子
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
    # 颜色: 亮像素占比为主
    color = "w" if bright > 0.33 else "b"
    ys, xs = np.where(fg > 0)
    cm = fg[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    cm = cv2.resize(cm, (CAN, CAN), interpolation=cv2.INTER_AREA)
    _, cm = cv2.threshold(cm, 127, 255, cv2.THRESH_BINARY)
    best_iou = -1; best_piece = None
    sets = [tpl[theme]] if theme and theme in tpl else list(tpl.values())
    for tset in sets:                # 选定主题(单套)或遍历所有棋子套件
        for piece in PIECES:
            tm = tset[(color, piece)]
            inter = np.count_nonzero((cm > 0) & (tm > 0))
            union = np.count_nonzero((cm > 0) | (tm > 0))
            iou = inter / union if union else 0
            if iou > best_iou:
                best_iou = iou; best_piece = piece
    # 泛化箭头剔除(不依赖箭头颜色/引擎):
    #   匹配分低 + 面积小 → 箭头线/箭头头, 判空;
    #   匹配分低 + 面积大 → 被箭头污染的真子(棋子本体占格20%+), 保留.
    # assume_clean=True 时用户确认无箭头/标注, 跳过此判空, 直接取最佳匹配。
    if not assume_clean and best_iou < iou_th and frac <= frac_th:
        return None, best_iou, frac
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
def recognize(img, tpl, verbose=False, mode="standard", theme=None, assume_clean=False):
    bbox = locate_board(img)
    if bbox is None:
        return None, None
    bx0, by0, bx1, by1 = [int(v) for v in bbox]
    board = img[by0:by1, bx0:bx1]
    ch, cw = board.shape[:2]
    CELL = cw // 8
    grid = [[None] * 8 for _ in range(8)]
    conf = [[0.0] * 8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            cell = board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
            grid[r][c], iou, frac = classify(cell, tpl, mode=mode, theme=theme, assume_clean=assume_clean)
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
