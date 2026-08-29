# 棋盘FEN识别 / chess-fen-scanner

把电子棋盘的截图（lichess、chess.com 这类）自动转成 FEN。纯粹在本地跑，不联网、不用云端，识别过程不把图传出去。

目前有两个形态：

- **安卓 App**：从相册选图 → 显示 FEN，可一键复制，也能跳转到 lichess 编辑器打开这个局面。
- **电脑命令行工具**：`scan.py`，对着一张或一批图跑，直接打印 FEN，并生成一张标了识别结果的图方便你核对。

## 它识别什么样的图

电子棋盘截图，不是实体棋盘照片。具体说：

- 格子颜色要用 lichess 默认的米色 / 棕色这套（程序按这两个颜色找棋盘）；
- 棋子样式是 lichess 默认的 cburnett 套件；
- 截图里带点东西没关系：走子标记（绿/黄高亮）、王被将的红高亮、玩家信息条、坐标字母数字、右侧胜率条，程序会把高亮当背景剔掉，自己定位到棋盘本体；
- 横竖方向无所谓，白方在上还是在下都能自动转成标准方向（白方在底部）。

## 安卓 APK 怎么装

成品在项目根目录：`棋盘FEN识别-v1.4-alpha.apk`，约 135MB。

1. 把 APK 传到手机点一下安装；
2. 如果提示"禁止安装未知来源应用"，去 设置 → 安全 → 允许安装外部来源应用，再装一次；
3. 打开 App，点"选择棋盘图片"，从相册选一张棋盘截图；
4. 识别出 FEN 后可以复制，或点"在 lichess 打开"（这步要联网；识别本身不需要）。

体积大是因为 OpenCV 把 4 种 CPU 架构的原生库一起打包了，兼容性最全。想小一点可以用 ABI 拆分只留 arm64，体积能降到三分之一左右。

## 电脑命令行怎么用

```bash
pip install opencv-python-headless numpy

# 单张
python scan.py 截图.png

# 一次多张
python scan.py 1.png 2.png 3.png

# 想多看点信息，比如每格的识别置信度
python scan.py 截图.png --verbose
```

输出会打印 FEN 摆放段和完整 FEN（`摆放段 w - - 0 1`）。默认还会在图片旁边生成一张 `<文件名>_scan.png`，把每个格子识别成了什么都标出来，方便你一眼核对哪里错了。

## 目录结构

```
chess-fen-scanner/
├── scan.py                     # 电脑端命令行识别工具
├── requirements.txt
├── 棋盘FEN识别-v1.4-alpha.apk   # 安卓成品
├── android/                    # 安卓工程（Kotlin + OpenCV）
│   └── app/src/main/java/com/chessscan/app/
│       ├── MainActivity.kt
│       └── ChessRecognizer.kt
├── assets/pieces/cburnett/     # 棋子素材（SVG 源 + 识别用的 PNG 剪影）
└── build-env/                  # 本地构建环境（Android SDK / Gradle 等）
```

## 识别思路

大致四步：

1. **找棋盘**：按棋盘浅色、深色做行列投影，定位到棋盘所在的正方形区域；
2. **切格子**：均匀切成 8×8；
3. **逐格识别**：先把和棋盘底色差别大的像素挑出来当"棋子剪影"（高亮也被当成背景去掉），再和 cburnett 各棋子的剪影模板做 IoU 匹配，判断是车马象后王兵；黑白色用剪影里亮像素占比判断；
4. **转正方向**：从 4 种旋转里挑出"白方在底部"的那个，拼出 FEN。

全程用的是 OpenCV，没训练深度学习模型，所以没有模型文件也不需要网络。

## 已知的短板

实话实说，还没到完美的程度：

- **黑白偶尔会判反**。在自己手头的 6 张测试图上，棋子类型（车马象后王兵）没认错过，颜色对了 98% 左右，错误都集中在个别带白色描边的黑子或带黑色线条的白子上。实际用的时候对着 `_scan.png` 核对一眼最稳；
- 棋盘定位对特别极端的布局（截图里塞满了走法列表、棋盘被挤得偏得很下面）可能会偏；
- 只识别**棋子摆放**部分；轮到谁走、易位权、过路兵、步数这些，得看截图 UI 或自己补。

## 参考的开源项目 / 素材

- **棋子素材**：使用的棋子图形是 [lichess](https://lichess.org) 默认的 **cburnett** 套件，源文件取自 [lichess-org/lila](https://github.com/lichess-org/lila) 仓库的 `public/piece/cburnett`。这套棋子在 lichess 里广泛使用。
- **图像处理**：安卓端用 [OpenCV](https://opencv.org/)（Maven 依赖 `org.opencv:opencv:4.10.0`），电脑端用 `opencv-python-headless`。
- **安卓工程**：基于 AndroidX / Material Components / Kotlin / AGP 构建，OpenCV 绑定来自官方安卓包。
- **App 图标**：用户自行提供的棋子图。

## 许可说明

- 棋子素材 **cburnett 套件的版权归原作者 Colin M.L. Burnett**。Lichess 把这些棋子放在它的仓库里使用，但素材本身的授权以原作者和 lichess 的相关声明为准（参考 [lichess-org/lila 的 COPYING.md](https://github.com/lichess-org/lila/blob/f0d7f5d1ac1cece4b701891890ef2a8c0163ead2/COPYING.md)）。
- 本项目的识别代码未特别声明许可时，以项目作者意愿为准。**如果想商用、上架或对外分发，请先确认真棋子和图标素材的授权**，别默认可以随意用。

项目主要使用DeepSeek V4 Flash 构建。但这句话是我写的：）