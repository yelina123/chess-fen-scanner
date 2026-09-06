# 棋盘截图 → FEN 识别器

把 lichess / chess.com 等电子棋盘截图**离线**识别成 FEN。两个形态：Android App（Kotlin + OpenCV 4.10）+ 电脑端命令行 `scan.py`。

## 功能

- 相册选图 → 自动定位棋盘 → 8×8 切格 → 剪影匹配 → 输出 FEN（默认补 `w - - 0 1`）
- **38 套 lichess 棋子样式兼容**（自动遍历全部套件取最佳匹配，也可手动指定主题）
- **引擎箭头/标注泛化剔除**：不针对特定箭头颜色适配，用形状匹配分 + 前景面积双判据排除箭头线/箭头头干扰
- 自动处理走子高亮（绿/黄/红）、引擎徽章（? / !! / !）、白方在上或在下自动旋转
- **识别棋盘预览**：棋盘框 + 格线 + 每格识别字母叠加，一眼看出识别是否成功
- **三档识别算法**：标准（平衡）/ 高召回（少漏子）/ 高精确（少误判）
- **清洁模式**：确认图中无引擎箭头/标注时勾选，跳过箭头判空，更准确不漏子
- 复制 FEN、一键在 lichess 编辑器打开、运行日志（便于诊断回传）
- 纯离线，无网络请求、无 ML 模型依赖

## 下载安装

从 [Releases](https://github.com/yelina123/chess-fen-scanner/releases) 下载最新 APK，安装到 Android 手机（Android 7.0+，鸿蒙兼容）。

## 电脑端用法

```bash
# 依赖: opencv-python-headless, numpy
pip install -r requirements.txt

# 识别单张或多张图
python scan.py 棋盘截图.jpg
python scan.py 1.jpg 2.jpg --verbose   # 输出每格置信度
```

输出 FEN 摆放段 + 完整 FEN，并在同目录生成 `*_scan.png` 可视化标注图。

## 验证

```bash
python verify_all.py     # 7 张基准图, 期望 448/448 = 100%
python verify_modes.py   # 三档算法 + 主题过滤在 10 张图上的成绩
```

当前成绩：7 张基准图 **448/448 = 100%**；3 张带引擎箭头的补充图 **191/192**（唯一错误为粗蓝箭头斜穿白兵的极端个案）。

## 算法要点

1. **棋盘定位**：像素到固定棋盘双色（LIGHT/DARK）的 L2 欧氏距离 < 阈值 = 棋盘色；形态学闭合 → 行/列投影找棋盘带 → 正方形化。
2. **前景提取**：与两种底色距离都大的像素 = 棋子（固定双色法，勿改用"每格主色"，实测倒退到 78.8%）。
3. **最大连通域**：形态学开闭后只保留面积最大分量，丢掉箭头残片/坐标文字。
4. **判色**：剪影像素亮度 >200 占比 >0.33 = 白（勿用中位数/均值）。
5. **判型**：剪影 crop bbox → resize 64×64（INTER_AREA）→ 与 38 套模板 IoU 取最大。
6. **箭头剔除**：`best_iou < 0.85 且 frac ≤ 0.22 → 判空`；frac 大则保留为被污染真子。阈值由 10 图 640 格标定。

> `scan.py` 与 `ChessRecognizer.kt` 是**同一算法的两份实现**，改了必须同步。双端距离度量、连通域、插值等算子必须严格一致，否则 PC 验证通过不代表安卓正确。

## 安卓构建

```powershell
# JDK 17 + Android SDK (build-tools 34, platform 34)
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
cd android
.\gradlew.bat assembleDebug --no-daemon
# APK: android\app\build\outputs\apk\debug\app-debug.apk
```

本仓库不含 SDK，需自行安装；`build-env/` 为本地构建环境（已 gitignore）。

## 目录结构

```
scan.py                  # 算法参考实现（先在这改、验证，再同步安卓）
verify_all.py            # 7 张基准图自动验证
verify_modes.py          # 三档算法 + 主题过滤验证
mode_analysis.py         # 阈值标定分析
android/                 # 安卓工程
  app/src/main/java/com/chessscan/app/
    ChessRecognizer.kt   # 识别引擎（与 scan.py 同算法）
    MainActivity.kt      # 界面
  app/src/main/res/      # 布局/主题/图标
assets/pieces/<set>/     # 38 套棋子模板（SVG 源 + PNG 剪影）
test_supplement/         # 带引擎箭头的补充测试图
HANDOFF.md               # 完整交接文档（算法细节、踩坑、版本历史）
```

## 许可证

GPL-3.0
