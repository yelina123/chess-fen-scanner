# -*- coding: utf-8 -*-
"""批量下载 lichess 棋子套件 SVG 并转成 90px 剪影模板 PNG。
输出到 assets/pieces/<set>/png/{color}{piece}_90.png (与现有 cburnett 格式一致)。
跳过纯搞怪/非棋子形状套件: disguised(伪装成动物), xkcd(火柴人), letter(字母), shapes(几何形)。
"""
import os, sys, io, time, urllib.request
import cv2
import numpy as np

ROOT = r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner"
ASSET_DIR = os.path.join(ROOT, "assets", "pieces")
RAW = "https://raw.githubusercontent.com/lichess-org/lila/master/public/piece"
PIECES = ["K", "Q", "R", "B", "N", "P"]
COLORS = ["w", "b"]
SKIP = {"disguised", "xkcd", "letter", "shapes"}

def render_svg_png(svg_bytes, size=90):
    """用 PyMuPDF 渲染 SVG 为 size×size RGBA PNG bytes"""
    import pymupdf
    doc = pymupdf.open(stream=svg_bytes, filetype="svg")
    page = doc[0]
    mat = pymupdf.Matrix(size / page.rect.width, size / page.rect.height)
    pm = page.get_pixmap(matrix=mat, alpha=True)
    return pm.tobytes("png")

def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return urllib.request.urlopen(req, timeout=30).read()
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))

def main():
    # 1) 拉取套件列表
    req = urllib.request.Request(
        "https://api.github.com/repos/lichess-org/lila/contents/public/piece",
        headers={"User-Agent": "Mozilla/5.0"})
    import json
    sets = sorted(d["name"] for d in json.load(urllib.request.urlopen(req, timeout=30))
                  if d["type"] == "dir" and d["name"] not in SKIP)
    print(f"套件数: {len(sets)} -> {sets}")

    # 2) 逐套下载 + 转换
    ok, fail = [], []
    for s in sets:
        sdir = os.path.join(ASSET_DIR, s)
        pdir = os.path.join(sdir, "png")
        os.makedirs(pdir, exist_ok=True)
        # 保留 SVG 源(许可证/后续复用), 下载失败不中断
        for color in COLORS:
            for pc in PIECES:
                fname = f"{color}{pc}.svg"
                try:
                    svg = fetch(f"{RAW}/{s}/{fname}")
                    with open(os.path.join(sdir, fname), "wb") as f:
                        f.write(svg)
                    png = render_svg_png(svg)
                    with open(os.path.join(pdir, f"{color}{pc}_90.png"), "wb") as f:
                        f.write(png)
                except Exception as e:
                    fail.append(f"{s}/{fname}: {e}")
        ok.append(s)
        print(f"  {s}: done")
        time.sleep(0.2)

    print(f"\n完成 {len(ok)}/{len(sets)} 套")
    if fail:
        print("失败项:")
        for f in fail[:20]:
            print("  ", f)

if __name__ == "__main__":
    main()
