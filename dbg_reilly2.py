# -*- coding: utf-8 -*-
import re, pymupdf, numpy as np

svg = open(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\assets\pieces\reillycraig\wK.svg", "rb").read()
print("原始开头:", svg[:120])

def patch_svg(svg):
    m = re.search(rb'viewBox="([-\d.e ]+) ([-\d.e ]+) ([-\d.e ]+) ([-\d.e ]+)"', svg)
    print("viewBox match:", m)
    if not m:
        return svg
    w, h = float(m.group(3)), float(m.group(4))
    print("w,h =", w, h)
    if re.search(rb'width="1(\.0)?" height="1(\.0)?"', svg):
        svg = re.sub(rb'width="[^"]*"\s+height="[^"]*"',
                     ('width="%g" height="%g"' % (w, h)).encode(), svg, count=1)
    return svg

patched = patch_svg(svg)
print("patched开头:", patched[:120])

doc = pymupdf.open(stream=patched, filetype="svg")
page = doc[0]
print("patched rect:", page.rect)
mat = pymupdf.Matrix(90 / page.rect.width, 90 / page.rect.height)
pm = page.get_pixmap(matrix=mat, alpha=True)
arr = np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width, pm.n)
print("pixmap:", pm.width, pm.height, "alpha>128:", np.count_nonzero(arr[:, :, 3] > 128))
