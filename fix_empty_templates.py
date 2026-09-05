# -*- coding: utf-8 -*-
"""修复空模板: (1) width/height 退化->改写为 viewBox; (2) 去掉 MuPDF 不支持的 <switch> 包装。"""
import pymupdf, cv2, numpy as np, os, re

root = r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\assets\pieces"

def render_svg(svg_bytes, size=90):
    doc = pymupdf.open(stream=svg_bytes, filetype="svg")
    page = doc[0]
    mat = pymupdf.Matrix(size / page.rect.width, size / page.rect.height)
    pm = page.get_pixmap(matrix=mat, alpha=True)
    return pm.tobytes("png")

def clean_svg(svg):
    m = re.search(rb'viewBox="([-\d.e ]+) ([-\d.e ]+) ([-\d.e ]+) ([-\d.e ]+)"', svg)
    if m:
        w, h = float(m.group(3)), float(m.group(4))
        svg = re.sub(rb'width="[^"]*"\s+height="[^"]*"',
                     ('width="%g" height="%g"' % (w, h)).encode(), svg, count=1)
    svg = re.sub(rb'</?switch>', b'', svg)
    return svg

for s in os.listdir(root):
    sdir = os.path.join(root, s)
    pdir = os.path.join(sdir, "png")
    if not os.path.isdir(pdir):
        continue
    for f in os.listdir(pdir):
        if not f.endswith("_90.png"):
            continue
        im = cv2.imread(os.path.join(pdir, f), cv2.IMREAD_UNCHANGED)
        if im is None or im.shape[2] != 4 or np.count_nonzero(im[:, :, 3] > 128) == 0:
            svg_name = f.replace("_90.png", ".svg")
            if not os.path.exists(os.path.join(sdir, svg_name)):
                svg_name = f[1:].replace("_90.png", ".svg")  # mono: bK->K
            with open(os.path.join(sdir, svg_name), "rb") as fh:
                svg = fh.read()
            svg = clean_svg(svg)
            png = render_svg(svg)
            with open(os.path.join(pdir, f), "wb") as fh:
                fh.write(png)
            im2 = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
            print(s, f, "重渲染 alpha像素:", np.count_nonzero(im2[:, :, 3] > 128))
