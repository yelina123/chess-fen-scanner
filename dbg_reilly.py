# -*- coding: utf-8 -*-
import pymupdf, numpy as np, re

svg = open(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\assets\pieces\reillycraig\wK.svg", "rb").read()
mm = re.search(rb'viewBox="([-\d.e ]+)"', svg)
x0, y0, w, h = [float(v) for v in mm.group(1).split()]
print("viewBox:", x0, y0, w, h)
doc = pymupdf.open(stream=svg, filetype="svg")
page = doc[0]
print("rect:", page.rect)
s = 90 / max(w, h)
mat = pymupdf.Matrix(s, 0, 0, s, -x0 * s, -y0 * s)
pm = page.get_pixmap(matrix=mat, alpha=True)
print("pixmap:", pm.width, pm.height, "n=", pm.n)
arr = np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width, pm.n)
print("BGR min:", arr[:, :, :3].min(axis=(0, 1)), "max:", arr[:, :, :3].max(axis=(0, 1)))
print("alpha min/max:", arr[:, :, 3].min(), arr[:, :, 3].max())
print("alpha>0:", np.count_nonzero(arr[:, :, 3] > 0), "alpha>128:", np.count_nonzero(arr[:, :, 3] > 128))
pm2 = page.get_pixmap(matrix=mat, alpha=False)
a2 = np.frombuffer(pm2.samples, np.uint8).reshape(pm2.height, pm2.width, pm2.n)
print("RGB 非白像素:", np.count_nonzero(a2.mean(axis=2) < 250))
