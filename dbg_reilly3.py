# -*- coding: utf-8 -*-
import re, pymupdf, numpy as np

svg = open(r"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\assets\pieces\reillycraig\wK.svg", "rb").read()
svg = re.sub(rb'width="[^"]*"\s+height="[^"]*"', b'width="220" height="220"', svg, count=1)

def test(name, data):
    doc = pymupdf.open(stream=data, filetype="svg")
    page = doc[0]
    pm = page.get_pixmap(matrix=pymupdf.Matrix(90 / page.rect.width, 90 / page.rect.height), alpha=True)
    arr = np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width, pm.n)
    print(name, "rect:", page.rect, "alpha>128:", np.count_nonzero(arr[:, :, 3] > 128))

test("原样(带switch)", svg)
test("去switch", re.sub(rb'</?switch>', b'', svg))
test("去switch+去g", re.sub(rb'</?switch>|</?g>', b'', svg))
