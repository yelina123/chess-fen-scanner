# -*- coding: utf-8 -*-
import pymupdf, cv2, numpy as np, re

def render(svg_bytes, size=160):
    doc = pymupdf.open(stream=svg_bytes, filetype="svg")
    page = doc[0]
    mat = pymupdf.Matrix(size / page.rect.width, size / page.rect.height)
    pm = page.get_pixmap(matrix=mat, alpha=True)
    arr = np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width, pm.n)
    return arr

for s, pc in [("merida", "wK"), ("merida", "bK"), ("alpha", "wK"), ("alpha", "bK")]:
    svg = open(rf"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\assets\pieces\{s}\{pc}.svg", "rb").read()
    arr = render(svg)
    bgr = arr[:, :, :3][arr[:, :, 3] > 128]
    lum = bgr.mean(axis=1)
    print(f"{s}/{pc}: 亮>200 占比 {np.count_nonzero(lum>200)/len(lum):.2f}, BGR均值 {bgr.mean(axis=0).round(0).astype(int).tolist()}")
    # 存图
    cv2.imwrite(rf"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\dbg_out2\{s}_{pc}_160.png", arr)
