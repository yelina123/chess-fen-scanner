# -*- coding: utf-8 -*-
"""合成测试图生成器: 随机局面 × 随机棋子套件 × 随机旋转/高亮 → 渲染逼真棋盘截图。
解决"测试图太少": 一套脚本即可生成几百张带标准答案的测试图。
输出到 synth_imgs/<set>_<n>.jpg + 同名 .txt(标准答案, 白方在底)。

用法: python gen_synth.py [每套张数] [随机种子]
"""
import os, sys, random
import cv2
import numpy as np

ROOT = r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner"
PIECE_DIR = os.path.join(ROOT, "assets", "pieces")
OUT_DIR = os.path.join(ROOT, "synth_imgs")

LIGHT = np.array([182, 216, 239], np.uint8)   # BGR 浅格
DARK = np.array([97, 137, 180], np.uint8)     # BGR 深格
CELL = 154                                    # 每格像素(与真实截图接近)

def expand(fen_placement):
    """FEN 摆放段 -> 8x8 list, 元素为 'wK'/'bp'/None"""
    rows = []
    for rank in fen_placement.split("/"):
        row = []
        for ch in rank:
            if ch.isdigit():
                row += [None] * int(ch)
            else:
                color = "w" if ch.isupper() else "b"
                row.append(color + ch.upper())
        rows.append(row)
    return rows

def compress(grid):
    """8x8 -> FEN 摆放段 (白方在底方向)"""
    ranks = []
    for r in range(8):
        s = ""; e = 0
        for c in range(8):
            pc = grid[r][c]
            if pc is None:
                e += 1
            else:
                if e: s += str(e); e = 0
                s += pc[1].upper() if pc[0] == "w" else pc[1].lower()
        if e: s += str(e)
        ranks.append(s)
    return "/".join(ranks)

def random_position(rng):
    """生成随机局面(不要求合法, 用于识别测试): 双王在盘, 棋子随机分布, 兵不进1/8行"""
    pieces_pool = []
    # 常规配子(参考初始局面, 随机取舍)
    back = ["R", "N", "B", "Q", "K", "B", "N", "R"]
    for i, pc in enumerate(back):
        if rng.random() < 0.85:
            pieces_pool.append("w" + pc)
        if rng.random() < 0.85:
            pieces_pool.append("b" + pc)
    for f in range(8):
        if rng.random() < 0.75:
            pieces_pool.append("wP")
        if rng.random() < 0.75:
            pieces_pool.append("bP")
    # 保证双王
    if "wK" not in pieces_pool: pieces_pool.append("wK")
    if "bK" not in pieces_pool: pieces_pool.append("bK")
    rng.shuffle(pieces_pool)
    # 填盘: 兵放 2-7 行, 其他任意
    grid = [[None] * 8 for _ in range(8)]
    cells = [(r, c) for r in range(8) for c in range(8)]
    rng.shuffle(cells)
    for pc in pieces_pool:
        for (r, c) in cells:
            if grid[r][c] is not None:
                continue
            if pc[1] == "P" and r in (0, 7):
                continue
            grid[r][c] = pc
            cells.remove((r, c))
            break
    # 双王必须存在
    if not any(grid[r][c] == "wK" for r in range(8) for c in range(8)):
        r, c = rng.randrange(8), rng.randrange(8)
        while grid[r][c] is not None: r, c = rng.randrange(8), rng.randrange(8)
        grid[r][c] = "wK"
    if not any(grid[r][c] == "bK" for r in range(8) for c in range(8)):
        r, c = rng.randrange(8), rng.randrange(8)
        while grid[r][c] is not None: r, c = rng.randrange(8), rng.randrange(8)
        grid[r][c] = "bK"
    return grid

def load_piece_images(setname):
    """加载套件 12 个彩色棋子 PNG (RGBA)"""
    pdir = os.path.join(PIECE_DIR, setname, "png")
    imgs = {}
    for color in "wb":
        for pc in "KQRBNP":
            f = os.path.join(pdir, f"{color}{pc}_90.png")
            im = cv2.imread(f, cv2.IMREAD_UNCHANGED)
            if im is not None:
                imgs[color + pc] = im
    return imgs

def render_board(grid, setname, piece_imgs, rng, rotate180=False, highlight=None):
    """渲染一张棋盘截图。grid 为白方在底方向的 8x8。"""
    S = CELL * 8
    board = np.zeros((S, S, 3), np.uint8)
    for r in range(8):
        for c in range(8):
            color = LIGHT if (r + c) % 2 == 0 else DARK
            board[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] = color
    # 高亮覆盖(模拟走子高亮: 黄/绿/红 半透明)
    if highlight:
        for (hr, hc, kind) in highlight:
            if kind == "yellow":
                ov = np.full((CELL, CELL, 3), (48, 168, 168), np.uint8)
            elif kind == "green":
                ov = np.full((CELL, CELL, 3), (70, 160, 70), np.uint8)
            elif kind == "red":
                ov = np.full((CELL, CELL, 3), (60, 60, 170), np.uint8)
            else:
                continue
            y0, y1 = hr * CELL, (hr + 1) * CELL
            x0, x1 = hc * CELL, (hc + 1) * CELL
            board[y0:y1, x0:x1] = cv2.addWeighted(board[y0:y1, x0:x1], 0.45, ov, 0.55, 0)
    # 摆棋子(先放大4x再缩小做抗锯齿)
    big = CELL * 4
    for r in range(8):
        for c in range(8):
            pc = grid[r][c]
            if pc is None:
                continue
            img = piece_imgs.get(pc)
            if img is None:
                continue
            # 目标尺寸: 格子的 52%~62%, 中心带小偏移(模拟截图)
            target = int(CELL * rng.uniform(0.52, 0.62))
            scale = target / max(img.shape[0], img.shape[1])
            im4 = cv2.resize(img, None, fx=scale * 4, fy=scale * 4, interpolation=cv2.INTER_CUBIC)
            # 羽化边缘一点点
            im4 = cv2.GaussianBlur(im4, (3, 3), 0.5)
            # 合成
            oh, ow = im4.shape[:2]
            cx = c * big + big // 2 + int(rng.uniform(-big * 0.02, big * 0.02))
            cy = r * big + big // 2 + int(rng.uniform(-big * 0.02, big * 0.02))
            x0 = cx - ow // 2; y0 = cy - oh // 2
            x0 = max(0, min(x0, S * 4 - ow)); y0 = max(0, min(y0, S * 4 - oh))
            b4 = cv2.resize(board, (S * 4, S * 4), interpolation=cv2.INTER_NEAREST)
            alpha = im4[:, :, 3:4].astype(np.float32) / 255.0
            fg = im4[:, :, :3].astype(np.float32)
            b4[y0:y0 + oh, x0:x0 + ow] = (fg * alpha + b4[y0:y0 + oh, x0:x0 + ow].astype(np.float32) * (1 - alpha)).astype(np.uint8)
            board = cv2.resize(b4, (S, S), interpolation=cv2.INTER_AREA)
    # 旋转 180°(白方在上)
    if rotate180:
        board = cv2.rotate(board, cv2.ROTATE_180)
        grid = [[grid[7 - r][7 - c] for c in range(8)] for r in range(8)]
    return board, grid

def main():
    per_set = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 20260904
    rng = random.Random(seed)
    os.makedirs(OUT_DIR, exist_ok=True)
    sets = sorted(d for d in os.listdir(PIECE_DIR)
                  if os.path.isdir(os.path.join(PIECE_DIR, d, "png")))
    # 收集模板
    piece_cache = {}
    for s in sets:
        imgs = load_piece_images(s)
        if len(imgs) == 12:
            piece_cache[s] = imgs
    print(f"可用套件 {len(piece_cache)} 个")
    n = 0; fails = []
    for s in sorted(piece_cache):
        for i in range(per_set):
            grid = random_position(rng)
            rotate180 = rng.random() < 0.4
            # 随机 0~3 个高亮格
            hl = []
            for _ in range(rng.randint(0, 3)):
                hr, hc = rng.randrange(8), rng.randrange(8)
                kind = rng.choice(["yellow", "yellow", "green", "red"])
                hl.append((hr, hc, kind))
            board, grid_final = render_board(grid, s, piece_cache[s], rng,
                                             rotate180=rotate180, highlight=hl or None)
            fen = compress(grid_final)
            name = f"{s}_{i:02d}"
            cv2.imencode(".jpg", board, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(
                os.path.join(OUT_DIR, name + ".jpg"))
            with open(os.path.join(OUT_DIR, name + ".txt"), "w", encoding="utf-8") as f:
                f.write(fen)
            n += 1
    print(f"生成 {n} 张测试图 -> {OUT_DIR}")
    if fails:
        print("失败:", fails[:10])

if __name__ == "__main__":
    main()
