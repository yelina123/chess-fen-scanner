# 项目交接文档 (HANDOFF)

> 交接给下一位开发者/AI。此文档覆盖：项目目标、现状、技术细节、遗留任务、构建与验证方法、踩过的坑。

## 0. 快速结论

项目是一个**把电子棋盘截图（lichess/chess.com 分析界面）离线识别成 FEN** 的工具，有两个形态：
- **安卓 App**（Kotlin + OpenCV 4.10.0），主交付物，APK 在项目根。
- **电脑端命令行** `scan.py`（Python + opencv-python-headless），用于快速验证算法。

当前 7 张基准测试图（1-7.jpg）逐格识别率 **100%（448/448）**。三项优化均已完成（见 §5）。

## 1. 项目目录结构

```
C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\
├── scan.py                    # 电脑端命令行识别（算法参考实现，先在此调算法）
├── verify_all.py              # 7 张基准图自动验证脚本（改算法后必跑）
├── requirements.txt
├── 棋盘FEN识别-v1.4-alpha.apk  # 安卓成品（旧版）
├── README.md                  # 已写好（含开源引用）
├── .gitignore                 # 排除 build-env/、apk、local.properties
├── app-icon.png               # 应用图标源图（用户提供，已重命名）
├── android/                   # 安卓工程（Kotlin + AGP 8.5 + OpenCV maven）
│   ├── local.properties       # 指向 ../build-env/android-sdk（本机路径，勿提交）
│   └── app/src/main/java/com/chessscan/app/
│       ├── MainActivity.kt     # 界面（选图/识别/复制/打开lichess/日志/作者链接）
│       └── ChessRecognizer.kt  # 识别引擎（逻辑与 scan.py 对应，需同步修改）
├── assets/pieces/cburnett/    # lichess cburnett 棋子 SVG + PNG 剪影模板
└── build-env/                 # 本地构建环境：android-sdk、gradle-8.7、sdk 脚本
    └── install_sdk.bat/.ps1   # 一键装 Android SDK（幂等）
```

**重要**：`scan.py` 和 `ChessRecognizer.kt` 是同一算法的两份实现，改算法先改 `scan.py` 用 `verify_all.py` 验证通过后再同步到 Kotlin。

## 2. 已实现功能（当前 APK 版本 v1.8-alpha）

- 相册选图（Android `ACTION_PICK` + MediaStore，华为鸿蒙下可弹相册而非文件浏览器——之前 PickVisualMedia 会弹文件浏览器，已改）。
- OpenCV 离线识别棋盘截图 → FEN 摆放段 + 完整 FEN（默认补 `w - - 0 1`）。
- 自动处理：绿/黄/红走子高亮、玩家条、坐标字母数字列、右侧胜率条、**白方在上或在下自动旋转**（best_orientation 按"白方在底部"打分）。
- 复制 FEN、跳转 lichess 编辑器、界面底部日志区（含"复制日志"按钮，方便用户回传诊断）、作者 GitHub 链接（https://github.com/yelina123）。
- 应用图标：用户提供的深蓝底白马图 → mipmap 各 dpi。

## 3. 识别算法（当前逻辑，scan.py 为准）

流程：定位棋盘正方形 → 均匀 8×8 切格 → 每格分类 → 旋转定向 → 拼 FEN。

**3.1 棋盘定位 `locate_board`**
- 调色板掩膜：像素距 LIGHT=(182,216,239) 或 DARK=(97,137,180)（BGR，PAL_TOL=34）近者为棋盘色。
- 形态学闭合填棋子洞（35×35 核）→ 行投影找棋盘竖直带（阈值 0.4~0.55）→ 带内列投影找水平范围。
- **正方形化**：用行带高度作边长（竖屏截图行投影最可靠），水平以列中点居中；水平裁剪时回落左对齐。
- 已知 bug/风险：极端布局（大量走法列表、棋盘偏下如 4.jpg）可能带偏；1-6.jpg 目前 OK。

**3.2 干扰掩膜 `overlay_mask`（新增于本轮优化）**
- 引擎标注徽章：`(saturation>150)&(value>190)` 的高饱和亮彩色（"?/!!/!" 彩色圆标）。
- 绿/黄/红走子高亮、被将红高亮（HSV 范围）。
- 这些像素一律不算棋子（`fg[omask>0]=0`）。

**3.3 单格分类 `classify`**
- 前景 fg：像素距 LIGHT **且** 距 DARK 都 > PAL_TOL（即既非浅格也非深格色）= 棋子。**不要改用"每格主色/众数"背景**——实测会大退化（78.8%）。
- 形态学开闭 → 保留最大连通域（丢掉角落小徽章/坐标文字残留）。
- 前景占比 frac<0.03 → 空格。
- 判色：剪影像素亮度 >200 的占比 `bright>0.33` → 白，否则黑（**此判据经验证最稳**，勿改回中位数法）。
- 判型：剪影裁剪到 bbox、缩放到 64×64，与 **38 套 lichess 棋子模板**（每套 12 个黑白棋子）取最大 IoU（`assets/pieces/<set>/png/`）。
- **泛化箭头剔除（v1.6 新增）**：匹配分 best_iou < 0.85 **且** 前景占比 frac ≤ 0.22 → 判空（箭头线/箭头头面积小、形状不匹配标准棋子）；frac > 0.22 则保留（被箭头污染的真子，棋子本体占格 20%+）。此规则不依赖箭头颜色/引擎，对 lichess 深/蓝/灰箭头、chess.com 任意颜色箭头均有效。

**3.4 定向 `best_orientation`**
- 4 种旋转，评分 =（白棋在底部两行 + 黑棋在顶部两行）-（反向），白王在底半区 +2，取最高分。

## 4. 验证方法与当前成绩

运行：
```bash
python verify_all.py
```
测试图在 `C:\Users\Administrator\Desktop\AI work\棋盘识别\检验图\1.jpg ~ 7.jpg`，标准答案硬编码在 verify_all.py（7.jpg 已于 2026-09-03 更正，见 §5.3）。

| 图 | 当前状态（v1.6 算法） |
|---|---|
| 1.jpg | **64/64 全对** |
| 2.jpg | **64/64 全对** |
| 3.jpg | **64/64 全对** |
| 4.jpg | **64/64 全对** |
| 5.jpg（初始局面） | **64/64 全对** |
| 6.jpg | **64/64 全对** |
| 7.jpg（后位局面，非 1.d4） | **64/64 全对** |
| 合计 | **448/448 = 100%** |

## 5. 三项优化（2026-09-03 全部完成）

### 5.1 准确率更高 ✅
- **根因（重要）**：1-6 每张错 2 格的"空格误判 r / 后误判 r"不是噪声，而是 **lichess/分析面板的黄色走子高亮（h≈30, s≈182, v≈168）漏掩膜**。旧掩膜只盖绿(h≥35)/红/徽章(s>150&v>190)，黄色高亮整格非棋盘色→被判为前景大块→整格剪影最像车。
- **修复**：`scan.py` 的 `overlay_mask` 与 `ChessRecognizer.kt` 的 `highlightMask` 统一为：徽章 `(s>150)&(v>190)` + 黄绿高亮 `h∈[15,85], s>40, v>60` + 红 `h≤10 或 h≥170`。一处修复后 1-6 全部 64/64。
- 判空 frac<0.03、判色 bright>0.33 等原有结论不变、仍有效。

### 5.2 App 界面优化 + 清除已选图片 ✅
- `activity_main.xml` 卡片化（圆角卡片背景 `drawable/bg_card.xml`、`bg_fen.xml`，跟随主题明暗），主色深蓝 #1565C0。
- 新增 **"清除已选图片"** 按钮（选图按钮旁）：清空预览/FEN/状态，日志保留。
- 日志区默认折叠，点击标题行展开/收起（保留复制/清空，便于用户回传诊断）。
- 按钮改为 MaterialButton（主按钮/Outlined/Tonal/Text 分档）。

### 5.3 7.jpg（引擎标注图）✅ 重要更正
- **核实结论：7.jpg 图上并没有引擎"?"徽章**（棋盘内高饱和亮色像素 = 0），且**实际局面不是 1.d4 初始局面**，而是黑后在 c4、白后在 g7 的后位局面：
  `rnb1kbnr/ppppp1Qp/8/8/2q5/8/P2PPPPP/RNB1KBNR`
- 旧"标准答案" `rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR` 与图像不符（d8/d1/f7/b2/c2 图上均为空，d4 无兵）。三重证据：逐格目视、模板置信度（g7 wQ=0.93 / c4 bQ=0.93）、旧版 `7_scan.png`（同图同批生成的旧可视化同样显示 d8 空 + g7/c4 有后）。
- `verify_all.py` 中 7.jpg 标准答案已更正为上述真实 FEN。**引擎徽章掩膜仍保留**（应对未来真正带徽章的图），但 7.jpg 并非该场景。
- 7.jpg 的 bbox y0=311（≠399）是因为该截图状态栏/标题栏高度不同，棋盘本身定位正确（行列号与格线严格对齐）。

### 5.4 多棋子样式兼容 ✅（v1.6）
- 从 lichess CDN 下载全部 42 套棋子，剔除搞怪套件（disguised/xkcd/letter/shapes）后 **38 套**，用 PyMuPDF 转 90px RGBA 黑白剪影模板存入 `assets/pieces/<set>/png/{w|b}{KQRBNP}_90.png`。
- `scan.py::load_templates` 遍历所有套件子目录；`classify` 对所有套件同色 6 棋子取最大 IoU。Kotlin `loadTemplates`/`classify` 同步同一 Map 结构。
- 踩坑：① PyMuPDF 不渲染 `<switch>` 标签（reillycraig 整套装空模板，须正则剔除）；② width/height 退化的 SVG 须改写为 viewBox 尺寸；③ monarchy 是 12 个 .webp 非 SVG；④ mono 单色剪影 w/b 各存一份。
- 模板下载脚本：`fetch_piece_sets_cdn.py`（CDN 源，写 `fetch_progress.txt` 可续传）；空模板修复：`fix_empty_templates.py`。

### 5.5 引擎箭头泛化剔除 ✅（v1.6）
- **用户要求**：兼容不同引擎/不同颜色箭头，禁止针对特定箭头颜色单独适配。
- **方案（几何+面积，泛化）**：
  1. 匹配分阈值：棋子剪影与标准模板 IoU ≥ 0.85 才直接判定为棋子；
  2. 面积恢复：IoU < 0.85 但前景占比 frac > 0.22 → 仍判定为棋子（被箭头污染的真子，棋子本体占格 20%+）；
  3. IoU < 0.85 且 frac ≤ 0.22 → 判空（箭头线/箭头头面积小、形状不匹配标准棋子）。
- **已否决方案**：① 针对箭头颜色采样 HSV 掩膜（不泛化）；② 距离变换厚块提取（削掉棋子细节，类型误判增多）；③ 格边细带剔除（棋子底座贴格边被误删）；④ 合成测试图（用户否决）。
- **补充图测试**（`test_supplement/a.jpg b.jpg c.jpg`，lichess 手机分析面板，带走子高亮+引擎箭头）：
  | 图 | 成绩 |
  |---|---|
  | a.jpg | 64/64 |
  | b.jpg | 63/64（g2 白兵被粗蓝箭头穿过，判成 wK） |
  | c.jpg | 64/64 |
  | 合计 | **191/192 = 99.5%** |
- **已知限制**：b.jpg g2 是极端个案（粗蓝箭头 g1→f3 斜穿白兵，箭头附加像素使 K 模板 IoU 0.576 仅比 P 0.560 高 0.016）。原 7 张基准图保持 448/448=100%。

### 5.6 安卓端定位 bug 修复 ✅（v1.7）
- **现象**：c.jpg 电脑端 scan.py 64/64，安卓 v1.6 却识别成 `qrrrrrrr/6rr/2r4n/2r5/...`（无王 → lichess 报无效 FEN）。日志 bbox=[12,422,1216,1626]，比电脑端 (1,473,1154,1626) 偏大 50px。
- **根因**：双端"到棋盘色距离"的数学定义不一致（详见 §8 坑 13）。Python 是 L2 欧氏距离；Kotlin locateBoard 是 L∞（三通道差都≤TOL）、classify 是 BGR2GRAY 加权平均，后两者更宽松→棋盘色掩膜外扩→形态学闭合后定位框偏大→切格错位。
- **修复**：新增 `bgrDist()`（absdiff→CV_32F→逐通道平方→split 求和→sqrt = L2），classify 与 locateBoard 共用，与 scan.py 严格对齐。已用 Python 复现：L∞ 度量算出 bbox=(11,420,1217) 与安卓日志 [12,422,1216] 吻合，L2 为 (1,473,1154) 正确。
- **教训**：PC 验证 100% 不等于安卓正确，双端算法移植必须逐行核对数学算子；灰度化/inRange 多通道不是欧氏距离的等价实现。

### 5.7 v1.8：漏兵修复 + 界面增强 + 算法/主题/清洁模式切换 ✅
- **漏兵根因**：Kotlin classify 漏了 Python 有的"只保留最大连通域"步骤（`connectedComponentsWithStats` 取最大面积分量）。箭头残片/坐标文字残留撑大 bbox → IoU 拉低 → 白兵（frac 本就贴近 0.22 判空线）被判 ARROW_EMPTY。PC 复现：b.jpg e2 白兵 keep_largest=wP、nokeep=None。已补上，同时把模板/剪影 resize 统一为 `INTER_AREA`（与 Python 一致，此前 Kotlin 默认 LINEAR）。
- **三档识别算法**（`MODE_PARAMS`，scan.py 与 Kotlin `MODE_TH` 一致，阈值由 `mode_analysis.py` 在 10 图 640 格上标定）：
  - `standard` 0.85/0.22（默认，平衡）
  - `recall` 0.81/0.18（判空保守，少漏子）
  - `precision` 0.90/0.26（判空积极，少误判）
  三档在 10 图上均 639/640（唯一错误为已知 b.jpg g2 粗蓝箭头极端个案）。
- **棋子主题手动选择**：Spinner 选"自动（38 套全匹配）"或指定单套件。`verify_modes.py` 验证单套件会掉分（cburnett 623/640、pixel 500/640），故默认自动。
- **"无箭头/标注"清洁模式**：CheckBox 勾选后 `assumeClean=true`，跳过箭头判空规则直接取最佳匹配（更准确、不漏子）；走子高亮掩膜仍保留。适合纯局面截图、无引擎分析箭头的场景。
- **棋盘识别预览**：`ChessRecognizer.drawPreview` 在原图上画绿色棋盘框、8×8 格线、每格识别字母（白棋绿字、黑棋橙字、黑描边），缩放宽 720 后返回 Bitmap，App 在原图下方显示。用户一眼看出格子/字母是否错位。
- **版本号显示**：标题栏右侧 `tvVersion` 读 `PackageManager.versionName`。
- 所有设置（mode/theme/assumeClean）存 SharedPreferences（`chessscan_prefs`），下次启动恢复。

## 6. 安卓构建 & 安装

```powershell
# 环境：JDK17 已装；SDK 在 build-env\android-sdk；gradle 在 build-env\gradle-8.7
$env:JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
cd "C:\Users\Administrator\Desktop\AI work\chess-fen-scanner\android"
.\gradlew.bat assembleDebug --no-daemon
# APK 输出：android\app\build\outputs\apk\debug\app-debug.apk
# 复制到项目根并命名版本，如：棋盘FEN识别-v1.8-alpha.apk
```
- **每轮改版记得 bump `android/app/build.gradle.kts` 的 versionCode/versionName**（当前 18/1.8-alpha）。
- 用户在鸿蒙 4.2 手机测试，用"复制日志"回传诊断。

## 7. GitHub 发布状态

- 仓库 https://github.com/yelina123/chess-fen-scanner （public, GPL-3.0 LICENSE 已在远程）。
- 已推送过一版 commit。**推送用 token 走 HTTPS**，注意：
  - 别提交：`build-env/`、`*.apk`、`android/local.properties`（.gitignore 已配）。
  - 推送方式见 git remote（origin）。改完代码可 commit+push。
- **安全提醒（已告知用户）**：对话中明文贴过 GitHub token，建议用户吊销重建；如果 token 已失效，push 前需用户给新 token。

## 8. 踩过的坑（避免重复）

1. **不要用"每格主色作背景"提取前景** → 78.8% 大退化，已回退固定调色板法。
2. **判色不要用亮度中位数/均值**（黑白描边干扰）→ 用 `bright>0.33`。
3. **OpenCV Kotlin 的 `Core.split`/集合**要传可变列表否则抛 UnsupportedOperationException（安卓端已避开 split）。
4. **安卓 bitmapToMat** 前需转 ARGB_8888 软位图（华为硬件位图会崩），已处理。
5. **OpenCV 初始化**用 `OpenCVLoader.initDebug()`（initLocal 在鸿蒙易失败），已处理。
6. **相册选择**：PickVisualMedia 在鸿蒙会弹文件浏览器 → 已改 `ACTION_PICK`+MediaStore。
7. **中文路径**：Python `cv2.imread` 不支持中文/非 ASCII 路径，用 `np.fromfile+imdecode`（scan.py 的 imread_unicode）。
8. `.bat` 文件别写中文（GBK 乱码当命令执行）；`.ps1` 中文 OK。
9. APK 大（~135MB）是 OpenCV 全 ABI，属正常；需要小体积可 ABI split。
10. 判空阈值 frac<0.03、IoU 匹配阈值等细节在 scan.py 有注释，改参数后用 verify_all.py 回归。
11. **黄色走子高亮（h≈30, s≈180, v≈170）必须进掩膜**：旧掩膜只盖绿(h≥35)，黄色高亮整格漏判→空格/后被误判成车。这是 95.8%→100% 的关键修复。
12. **7.jpg 的"标准答案"曾被误标为 1.d4 初始局面**：核对测试图真实内容后再定标准答案，别轻信交接里的 FEN；7.jpg 真实局面见 §5.3。
13. **双端距离度量必须一致（v1.7）**：scan.py 用 L2 欧氏距离；Kotlin 早期 locateBoard 用 L∞（absdiff+inRange）、classify 用 BGR2GRAY 加权平均，更宽松导致定位框偏大 50px、全盘误判。已统一为 Kotlin bgrDist()。
14. **最大连通域不能省（v1.8 漏兵）**：scan.py classify 形态学后只保留最大连通域；Kotlin 早期漏这步，箭头残片撑大 bbox 拉低 IoU，白兵被判空。双端必须有，且 resize 统一 INTER_AREA。

## 9. 下一步建议（给接手者）

1. 三项优化已完成，7 图全对 100%（`python verify_all.py`）。
2. 后续可做：真带引擎徽章(?/!!/!)的新测试图（当前 7.jpg 无徽章）；更多棋盘主题配色（当前调色板仅 lichess 默认色）。
3. 有新图先跑 verify_all 回归，再同步 scan.py ↔ ChessRecognizer.kt。
4. 推送 GitHub 时排除 build-env/、*.apk、local.properties。
