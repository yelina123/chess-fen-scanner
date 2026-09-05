# -*- coding: utf-8 -*-
"""从 lichess CDN 批量下载棋子套件 SVG 并转成 90px 剪影模板 PNG (断点续传)。
输出到 assets/pieces/<set>/png/{color}{piece}_90.png。进度写入 fetch_progress.txt。
"""
import os, time, urllib.request
import numpy as np

ROOT = r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner"
ASSET_DIR = os.path.join(ROOT, "assets", "pieces")
CDN = "https://lichess1.org/assets/piece"
PIECES = ["K", "Q", "R", "B", "N", "P"]
COLORS = ["w", "b"]
SKIP = {"disguised", "xkcd", "letter", "shapes"}
PROG = os.path.join(ROOT, "fetch_progress.txt")

# 全部 42 套(lichess 官方)
ALL_SETS = ["alpha", "anarcandy", "caliente", "california", "cardinal", "cburnett",
            "celtic", "chess7", "chessnut", "companion", "cooke", "disguised",
            "dubrovny", "fantasy", "firi", "fresca", "gioco", "governor", "horsey",
            "icpieces", "kiwen-suwi", "kosal", "leipzig", "letter", "maestro",
            "merida", "monarchy", "mono", "mpchess", "papercut", "pirouetti",
            "pixel", "reillycraig", "rhosgfx", "riohacha", "shahi-ivory-brown",
            "shapes", "spatial", "staunty", "tatiana", "totoy", "xkcd"]

def log(msg):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")

def render_svg_png(svg_bytes, size=90):
    import pymupdf
    doc = pymupdf.open(stream=svg_bytes, filetype="svg")
    page = doc[0]
    mat = pymupdf.Matrix(size / page.rect.width, size / page.rect.height)
    pm = page.get_pixmap(matrix=mat, alpha=True)
    return pm.tobytes("png")

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=15).read()

def set_done(s):
    pdir = os.path.join(ASSET_DIR, s, "png")
    if not os.path.isdir(pdir):
        return False
    for color in COLORS:
        for pc in PIECES:
            if not os.path.exists(os.path.join(pdir, f"{color}{pc}_90.png")):
                return False
    return True

def main():
    sets = [s for s in ALL_SETS if s not in SKIP and not set_done(s)]
    log(f"待处理 {len(sets)} 套: {sets}")
    ok, fail = 0, []
    for s in sets:
        sdir = os.path.join(ASSET_DIR, s)
        pdir = os.path.join(sdir, "png")
        os.makedirs(pdir, exist_ok=True)
        s_ok = True
        for color in COLORS:
            for pc in PIECES:
                fname = f"{color}{pc}.svg"
                out_png = os.path.join(pdir, f"{color}{pc}_90.png")
                if os.path.exists(out_png):
                    continue
                try:
                    svg = fetch(f"{CDN}/{s}/{fname}")
                    with open(os.path.join(sdir, fname), "wb") as f:
                        f.write(svg)
                    with open(out_png, "wb") as f:
                        f.write(render_svg_png(svg))
                except Exception as e:
                    s_ok = False
                    fail.append(f"{s}/{fname}: {e}")
                    log(f"FAIL {s}/{fname}: {e}")
                    time.sleep(0.5)
        if s_ok:
            ok += 1
            log(f"OK {s}")
        else:
            log(f"PARTIAL {s}")
    log(f"完成: {ok}/{len(sets)}, 失败 {len(fail)}")
    if fail:
        log("失败明细: " + " | ".join(fail[:15]))

if __name__ == "__main__":
    main()
