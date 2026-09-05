# -*- coding: utf-8 -*-
import cv2, numpy as np

LIGHT = np.array([182, 216, 239], np.float32)
DARK = np.array([97, 137, 180], np.float32)
PAL_TOL = 34

for s, pc in [("alpha", "bN"), ("alpha", "bK"), ("cburnett", "bN"), ("merida", "bN"), ("alpha", "wK")]:
    im = cv2.imread(rf"C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\assets\pieces\{s}\png\{pc}_90.png", cv2.IMREAD_UNCHANGED)
    a = im[:, :, 3]
    rgb_bgr = im[:, :, :3].astype(np.float32)
    px = rgb_bgr[a > 128]
    dL = np.linalg.norm(px - LIGHT, axis=1)
    dD = np.linalg.norm(px - DARK, axis=1)
    n = len(px)
    print(f"{s}/{pc}: 棋子像素 {n}, 距LIGHT<34 占比 {(dL<34).mean():.2f}, 距DARK<34 占比 {(dD<34).mean():.2f}, 两者都>34(能判前景) {( (dL>34)&(dD>34) ).mean():.2f}")
    print("   BGR 均值:", px.mean(axis=0).round(0).astype(int).tolist(), " 亮(>200):", (px.mean(axis=1) > 200).mean().round(2))
