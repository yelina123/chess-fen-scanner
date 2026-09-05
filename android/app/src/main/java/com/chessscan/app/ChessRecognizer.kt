package com.chessscan.app

import android.content.Context
import android.graphics.Bitmap
import org.opencv.android.OpenCVLoader
import org.opencv.android.Utils
import org.opencv.core.*
import org.opencv.imgproc.Imgproc
import kotlin.math.max

/**
 * 把电子棋盘截图识别成 FEN。
 * 纯 OpenCV 剪影识别，离线运行。
 */
class ChessRecognizer(context: Context) {

    companion object {
        // lichess 默认棋盘色 (BGR)
        private val LIGHT = doubleArrayOf(182.0, 216.0, 239.0)
        private val DARK = doubleArrayOf(97.0, 137.0, 180.0)
        private const val PAL_TOL = 34.0
        private const val CAN = 64
        private val PIECES = arrayOf("K", "Q", "R", "B", "N", "P")
        // 识别算法档位 (best_iou 阈值, frac 面积阈值), 与 scan.py MODE_PARAMS 严格一致。
        // standard 居中; recall 判空保守(少漏子); precision 判空积极(少误判)。
        val MODE_TH = mapOf(
            "standard"  to doubleArrayOf(0.85, 0.22),
            "recall"    to doubleArrayOf(0.81, 0.18),
            "precision" to doubleArrayOf(0.90, 0.26),
        )
        // 逐格诊断缓冲
        val diag = StringBuilder()
        fun clearDiag() { synchronized(diag) { diag.setLength(0) } }
    }

    // 识别结果: fen 摆放段(已含 w - - 0 1 由调用方拼), preview 棋盘标注预览, rot 旋转次数
    class RecogResult(val fen: String?, val preview: Bitmap?, val rot: Int)

    private val appContext = context.applicationContext
    private var opencvReady = false
    // 多套件模板: set 名 -> (颜色+棋子 -> 64x64 剪影)
    private val templates: MutableMap<String, MutableMap<String, Mat>> = HashMap()
    // 用户选择: 算法档位 + 棋子主题(null=自动,遍历全部套件)
    @Volatile var mode: String = "standard"
    @Volatile var theme: String? = null
    // 用户确认图中无引擎箭头/?/! 等标注: true 时跳过箭头判空, 直接取最佳匹配(更准确)。
    // 走子高亮(黄绿红)掩膜不受影响。
    @Volatile var assumeClean: Boolean = false
    fun pieceSetNames(): List<String> = templates.keys.sorted()

    // 供 UI 展示初始化状态/错误
    val ready: Boolean get() = opencvReady
    var initMsg: String = ""

    init {
        try {
            // initDebug 会从 apk 内提取并加载原生库, 比 initLocal 兼容性更好
            opencvReady = OpenCVLoader.initDebug()
            if (!opencvReady) {
                opencvReady = OpenCVLoader.initLocal()
            }
            initMsg = if (opencvReady) "OpenCV 加载成功 (v${org.opencv.core.Core.VERSION})" else "OpenCV 加载失败"
        } catch (e: Throwable) {
            initMsg = "OpenCV 初始化异常: ${e.javaClass.simpleName}: ${e.message}"
            opencvReady = false
        }
        if (opencvReady) {
            try { loadTemplates() } catch (e: Throwable) {
                initMsg += "; 模板加载异常: ${e.javaClass.simpleName}"
                opencvReady = false
            }
        }
    }

    // ---------------- 模板剪影 ----------------
    private fun loadTemplates() {
        val setNames = appContext.assets.list("pieces") ?: return
        for (sname in setNames) {
            val stpl = HashMap<String, Mat>()
            for (color in arrayOf("w", "b")) {
                for (piece in PIECES) {
                    try {
                        val name = "${color}${piece}_90.png"
                        val `is` = appContext.assets.open("pieces/$sname/png/$name")
                        val bmp = BitmapFactory2.decodeStream(`is`)
                        val mat = Mat()
                        Utils.bitmapToMat(bmp, mat)
                        // 提取 alpha 通道
                        val rgba = Mat()
                        Imgproc.cvtColor(mat, rgba, Imgproc.COLOR_RGBA2BGRA)
                        val alpha = Mat()
                        Core.extractChannel(mat, alpha, 3) // mat is RGBA from Bitmap
                        // bbox crop
                        val bbox = bboxOf(alpha)
                        val a = alpha.submat(bbox).clone()
                        // resize to CAN (INTER_AREA 与 scan.py 一致)
                        val out = Mat()
                        Imgproc.resize(a, out, Size(CAN.toDouble(), CAN.toDouble()), 0.0, 0.0, Imgproc.INTER_AREA)
                        Imgproc.threshold(out, out, 127.0, 255.0, Imgproc.THRESH_BINARY)
                        stpl["$color$piece"] = out
                    } catch (e: Exception) {
                        // template missing; skip
                    }
                }
            }
            if (stpl.size == 12) templates[sname] = stpl
        }
    }

    private fun bboxOf(binary: Mat): Rect {
        var minX = Int.MAX_VALUE; var minY = Int.MAX_VALUE
        var maxX = -1; var maxY = -1
        val rows = binary.rows(); val cols = binary.cols()
        for (y in 0 until rows) {
            for (x in 0 until cols) {
                if (binary.get(y, x)[0] > 128.0) {
                    if (x < minX) minX = x
                    if (x > maxX) maxX = x
                    if (y < minY) minY = y
                    if (y > maxY) maxY = y
                }
            }
        }
        if (maxX < 0) return Rect(0, 0, cols, rows)
        return Rect(minX, minY, maxX - minX + 1, maxY - minY + 1)
    }

    // ---------------- 入口 ----------------
    fun recognize(bitmap: Bitmap): RecogResult {
        if (!opencvReady) return RecogResult("OpenCV 初始化失败", null, 0)
        // 兼容性: 硬件位图/非ARGB无法直接转Mat, 统一复制成 ARGB_8888 软件位图
        val safe = if (bitmap.config == Bitmap.Config.HARDWARE ||
            bitmap.config != Bitmap.Config.ARGB_8888) {
            bitmap.copy(Bitmap.Config.ARGB_8888, false)
        } else bitmap
        val bgr = Mat()
        Utils.bitmapToMat(safe, bgr)
        Imgproc.cvtColor(bgr, bgr, Imgproc.COLOR_RGBA2BGR)

        val boardRect = locateBoard(bgr) ?: return RecogResult("定位不到棋盘", null, 0)
        val bx0 = boardRect[0]; val by0 = boardRect[1]
        val bx1 = boardRect[2]; val by1 = boardRect[3]
        val board = Mat(bgr, Rect(bx0, by0, bx1 - bx0, by1 - by0))
        val cellCount = 8
        val cw = board.cols(); val ch = board.rows()
        val cellW = cw / cellCount; val cellH = ch / cellCount
        clearDiag()
        diag.append("board=${boardRect.contentToString()} size=${cw}x${ch} cell=${cellW}x${cellH} mode=$mode theme=${theme ?: "auto"}\n")
        val grid: Array<Array<String?>> = Array(8) { arrayOfNulls<String>(8) }

        for (r in 0 until 8) {
            for (c in 0 until 8) {
                val cell = Mat(board, Rect(c * cellW, r * cellH, cellW, cellH))
                grid[r][c] = classify(cell)
            }
        }
        val (fen, rot) = bestOrientation(grid)
        val preview = drawPreview(bgr, bx0, by0, cellW, cellH, grid, rot)
        return RecogResult("$fen w - - 0 1", preview, rot)
    }

    /** 在原图副本上画棋盘框、8x8 格线和每格识别结果(旋转到最终方向), 缩放到宽 720 供 UI 显示。 */
    private fun drawPreview(bgr: Mat, bx0: Int, by0: Int, cellW: Int, cellH: Int,
                            grid: Array<Array<String?>>, rot: Int): Bitmap {
        val ov = Mat()
        bgr.copyTo(ov)
        // 棋盘外框(绿)
        Imgproc.rectangle(ov, Point(bx0.toDouble(), by0.toDouble()),
            Point((bx0 + cellW * 8).toDouble(), (by0 + cellH * 8).toDouble()),
            Scalar(0.0, 220.0, 0.0), 4)
        val shown = rotGrid(grid, rot)
        val font = Imgproc.FONT_HERSHEY_SIMPLEX
        val scale = cellW / 72.0
        for (r in 0 until 8) {
            for (c in 0 until 8) {
                val x = bx0 + c * cellW; val y = by0 + r * cellH
                // 格线
                Imgproc.rectangle(ov, Point(x.toDouble(), y.toDouble()),
                    Point((x + cellW).toDouble(), (y + cellH).toDouble()),
                    Scalar(60.0, 60.0, 60.0), 1)
                val pc = shown[r][c] ?: continue
                val txt = if (pc[0] == 'w') pc[1].uppercase() else pc[1].lowercase()
                val pos = Point((x + cellW * 0.18), (y + cellH * 0.78))
                // 黑字描边 + 白字填充, 任何底色上都清晰
                Imgproc.putText(ov, txt, pos, font, scale, Scalar(0.0, 0.0, 0.0), 6)
                val isWhite = pc[0] == 'w'
                val fill = if (isWhite) Scalar(0.0, 230.0, 0.0) else Scalar(0.0, 120.0, 255.0)
                Imgproc.putText(ov, txt, pos, font, scale, fill, 2)
            }
        }
        // 缩放到宽 720 省内存
        val W = 720
        val H = ov.rows() * W / ov.cols()
        val small = Mat()
        Imgproc.resize(ov, small, Size(W.toDouble(), H.toDouble()), 0.0, 0.0, Imgproc.INTER_AREA)
        val rgba = Mat()
        Imgproc.cvtColor(small, rgba, Imgproc.COLOR_BGR2RGBA)
        val bmp = Bitmap.createBitmap(rgba.cols(), rgba.rows(), Bitmap.Config.ARGB_8888)
        Utils.matToBitmap(rgba, bmp)
        return bmp
    }

    // ---------------- 单格分类 ----------------
    private fun classify(cell: Mat): String? {
        val ch = cell.rows(); val cw = cell.cols()
        val hmask = highlightMask(cell)

        // 前景 = 与两种棋盘底色(LIGHT/DARK)的 L2 欧氏距离都大的像素。
        // 这样黑白棋子都能从任何颜色(浅格/深格)上提取, 不依赖"格子内均值"背景(后者会被
        // 深色格上的黑棋子拉暗, 导致黑子前景提取失败 -> 误判为空)。
        // 注意: 必须用 L2(与 scan.py 一致), 不能用 BGR2GRAY 加权平均。
        val dL = bgrDist(cell, LIGHT)
        val dD = bgrDist(cell, DARK)
        // 与任一棋盘色接近则不是棋子; 与两者都远才是棋子
        val nearL = Mat(); val nearD = Mat()
        Core.inRange(dL, Scalar(0.0), Scalar(PAL_TOL), nearL)
        Core.inRange(dD, Scalar(0.0), Scalar(PAL_TOL), nearD)
        val isBoard = Mat()
        Core.bitwise_or(nearL, nearD, isBoard)
        val fg = Mat()
        Core.bitwise_not(isBoard, fg)
        fg.setTo(Scalar(0.0), hmask) // 高亮不是棋子
        Imgproc.morphologyEx(fg, fg, Imgproc.MORPH_OPEN, Imgproc.getStructuringElement(Imgproc.MORPH_RECT, Size(3.0, 3.0)))
        Imgproc.morphologyEx(fg, fg, Imgproc.MORPH_CLOSE, Imgproc.getStructuringElement(Imgproc.MORPH_RECT, Size(5.0, 5.0)))

        // 只保留最大连通域(与 scan.py 一致): 丢掉箭头残片/角落徽章/坐标文字残留。
        // 早期安卓端漏这一步, 残片撑大 bbox 拉低 IoU, 导致白兵被判空(漏兵)。
        val lbl = Mat(); val stats = Mat(); val cent = Mat()
        val nComp = Imgproc.connectedComponentsWithStats(fg, lbl, stats, cent, 8)
        if (nComp > 1) {
            var bestArea = 0; var bestIdx = 1
            for (i in 1 until nComp) {
                val a = stats.get(i, Imgproc.CC_STAT_AREA)[0].toInt()
                if (a > bestArea) { bestArea = a; bestIdx = i }
            }
            val keepMask = Mat()
            Core.compare(lbl, Scalar(bestIdx.toDouble()), keepMask, Core.CMP_EQ)
            fg.setTo(Scalar(0.0))
            fg.setTo(Scalar(255.0), keepMask)
        }

        val frac = Core.countNonZero(fg).toDouble() / (ch * cw)
        diag.append("frac=$frac ")
        if (frac < 0.03) { diag.append("->EMPTY\n"); return null }

        // 判色：剪影像素亮度中位数
        val color = pieceColor(fg, cell)
        // bbox 归一化 + IoU
        val bb = bboxOf(fg)
        val cm = Mat()
        val cropped = fg.submat(bb)
        Imgproc.resize(cropped, cm, Size(CAN.toDouble(), CAN.toDouble()), 0.0, 0.0, Imgproc.INTER_AREA)
        Imgproc.threshold(cm, cm, 127.0, 255.0, Imgproc.THRESH_BINARY)

        val (iouTh, fracTh) = MODE_TH.getOrDefault(mode, MODE_TH["standard"]!!)
        var bestIou = -1.0; var bestPiece: String? = null
        val sets = if (theme != null && templates.containsKey(theme)) listOf(templates[theme]!!)
                   else templates.values.toList()
        for (tset in sets) {              // 选定主题(单套)或遍历所有棋子套件
            for (piece in PIECES) {
                val tpl = tset["$color$piece"] ?: continue
                val inter = Mat()
                Core.bitwise_and(cm, tpl, inter)
                val union = Mat()
                Core.bitwise_or(cm, tpl, union)
                val iou = Core.countNonZero(inter).toDouble() / max(1, Core.countNonZero(union))
                if (iou > bestIou) { bestIou = iou; bestPiece = piece }
            }
        }
        // 泛化箭头剔除(不依赖箭头颜色/引擎):
        //   匹配分低 + 面积小 -> 箭头线/箭头头, 判空;
        //   匹配分低 + 面积大 -> 被箭头污染的真子(棋子本体占格20%+), 保留.
        if (!assumeClean && bestIou < iouTh && frac <= fracTh) {
            diag.append("->ARROW_EMPTY(iou=${"%.2f".format(bestIou)},frac=${"%.2f".format(frac)})\n")
            return null
        }
        diag.append("->${color}${bestPiece}(${"%.2f".format(bestIou)})\n")
        return if (bestPiece != null) color + bestPiece else null
    }

    private fun pieceColor(fg: Mat, cell: Mat): String {
        // 收集剪影像素亮度
        val rows = fg.rows(); val cols = fg.cols()
        var brightCount = 0; var darkCount = 0; var total = 0
        for (y in 0 until rows) {
            for (x in 0 until cols) {
                if (fg.get(y, x)[0] > 128.0) {
                    val p = cell.get(y, x)
                    val lum = (p[0] + p[1] + p[2]) / 3.0
                    if (lum > 200) brightCount++
                    if (lum < 80) darkCount++
                    total++
                }
            }
        }
        if (total == 0) return "b"
        val bright = brightCount / total.toDouble()
        // 白棋主体有大量亮像素(>0.33); 黑棋主体暗, 亮像素少。此法抗描边/高光。
        return if (bright > 0.33) "w" else "b"
    }

    private fun highlightMask(cell: Mat): Mat {
        val hsv = Mat()
        Imgproc.cvtColor(cell, hsv, Imgproc.COLOR_BGR2HSV)
        // 引擎标注徽章(?,!!,! 等): 高饱和+高亮度的彩色小圆, 偏离棋盘色 (与 scan.py 一致)
        val badge = Mat(); Core.inRange(hsv, Scalar(0.0, 151.0, 191.0), Scalar(180.0, 255.0, 255.0), badge)
        // 走子高亮: 黄(h≈30)+绿(h 35-85) 半透明覆盖偏色。黄色高亮曾漏掩膜导致整格被判为前景大块→误判成车, 现并入
        val highlight = Mat(); Core.inRange(hsv, Scalar(15.0, 41.0, 61.0), Scalar(85.0, 255.0, 255.0), highlight)
        // 被将/红方高亮
        val red = Mat(); Core.inRange(hsv, Scalar(0.0, 41.0, 61.0), Scalar(10.0, 255.0, 255.0), red)
        val red2 = Mat(); Core.inRange(hsv, Scalar(170.0, 41.0, 61.0), Scalar(180.0, 255.0, 255.0), red2)
        val out = Mat()
        Core.bitwise_or(badge, highlight, out)
        Core.bitwise_or(out, red, out)
        Core.bitwise_or(out, red2, out)
        return out
    }

    // ---------------- 棋盘定位 ----------------
    // 每像素到目标 BGR 常量的欧氏距离(L2), 返回 CV_32FC1。
    // 必须与 scan.py 的 np.linalg.norm 一致; 早期版本误用逐通道 inRange(L∞)
    // 和 BGR2GRAY(加权平均), 都会让棋盘色掩膜偏宽、定位 bbox 偏大数十像素。
    private fun bgrDist(src: Mat, target: DoubleArray): Mat {
        val tgt = Mat(src.rows(), src.cols(), CvType.CV_8UC3, Scalar(target[0], target[1], target[2]))
        val diff = Mat()
        Core.absdiff(src, tgt, diff)
        val f = Mat()
        diff.convertTo(f, CvType.CV_32FC3)
        val sq = Mat()
        Core.multiply(f, f, sq)
        val chans = mutableListOf<Mat>()
        Core.split(sq, chans)
        val sum = Mat()
        Core.add(chans[0], chans[1], sum)
        Core.add(sum, chans[2], sum)
        val dist = Mat()
        Core.sqrt(sum, dist)
        return dist
    }

    private fun locateBoard(bgr: Mat): IntArray? {
        val h = bgr.rows(); val w = bgr.cols()
        val distL = bgrDist(bgr, LIGHT)
        val distD = bgrDist(bgr, DARK)
        val ml = Mat(); val md = Mat()
        Core.inRange(distL, Scalar(0.0), Scalar(PAL_TOL), ml)
        Core.inRange(distD, Scalar(0.0), Scalar(PAL_TOL), md)
        val bm = Mat()
        Core.bitwise_or(ml, md, bm)

        val closed = Mat()
        Imgproc.morphologyEx(bm, closed, Imgproc.MORPH_CLOSE, Imgproc.getStructuringElement(Imgproc.MORPH_RECT, Size(35.0, 35.0)))
        Imgproc.morphologyEx(closed, closed, Imgproc.MORPH_OPEN, Imgproc.getStructuringElement(Imgproc.MORPH_RECT, Size(9.0, 9.0)))

        // 行投影
        val row = Mat(1, h, CvType.CV_64FC1)
        for (y in 0 until h) {
            val ro = closed.row(y)
            row.put(0, y, Core.countNonZero(ro).toDouble() / w)
        }
        val spanY = maxSpan(row, 0.4)
        if (spanY == null || spanY[1] - spanY[0] < 0.2 * h) return null

        val band = closed.submat(spanY[0], spanY[1], 0, w)
        val col = Mat(1, w, CvType.CV_64FC1)
        for (x in 0 until w) {
            val co = band.col(x)
            col.put(0, x, Core.countNonZero(co).toDouble() / band.rows())
        }
        val spanX = maxSpan(col, 0.35)
        if (spanX == null || spanX[1] - spanX[0] < 0.2 * w) return null

        // 正方形：行高为边长，水平居中
        val side = spanY[1] - spanY[0]
        val cx = (spanX[0] + spanX[1]) / 2
        var bx0 = cx - side / 2; var by0 = spanY[0]
        if (bx0 < 0) bx0 = 0
        var bx1 = bx0 + side; var by1 = by0 + side
        if (bx1 > w) { bx1 = w; bx0 = bx1 - side }
        if (by1 > h) { by1 = h; by0 = by1 - side }
        return intArrayOf(bx0, by0, bx1, by1)
    }

    private fun maxSpan(profile: Mat, thr: Double): IntArray? {
        val n = profile.cols()
        var bestS = -1; var bestE = -1; var curS = -1
        for (i in 0 until n) {
            val v = profile.get(0, i)[0]
            if (v > thr) {
                if (curS < 0) curS = i
                if (i - curS > bestE - bestS) { bestS = curS; bestE = i }
            } else {
                curS = -1
            }
        }
        return if (bestS < 0) null else intArrayOf(bestS, bestE + 1)
    }

    // ---------------- FEN + 旋转 ----------------
    private fun gridToFen(grid: Array<Array<String?>>): String {
        val ranks = ArrayList<String>()
        for (r in 0 until 8) {
            val sb = StringBuilder()
            var e = 0
            for (c in 0 until 8) {
                val pc = grid[r][c]
                if (pc == null) { e++ }
                else {
                    if (e > 0) { sb.append(e); e = 0 }
                    sb.append(if (pc[0] == 'w') pc[1].uppercase() else pc[1].lowercase())
                }
            }
            if (e > 0) sb.append(e)
            ranks.add(sb.toString())
        }
        return ranks.joinToString("/")
    }

    private fun bestOrientation(grid: Array<Array<String?>>): Pair<String, Int> {
        var bestScore = Int.MIN_VALUE; var bestFen = gridToFen(grid); var bestRot = 0
        for (rot in 0 until 4) {
            val g = rotGrid(grid, rot)
            val f = gridToFen(g)
            var wb = 0; var wt = 0; var bb = 0; var bt = 0
            for (c in 0 until 8) {
                for (r in intArrayOf(6, 7)) { val pc = g[r][c]; if (pc != null) { if (pc[0] == 'w') wb++ else bb++ } }
                for (r in intArrayOf(0, 1)) { val pc = g[r][c]; if (pc != null) { if (pc[0] == 'w') wt++ else bt++ } }
            }
            var score = (wb + bt) - (wt + bb)
            // 白王在底部半区加分
            outer@ for (r in 4..7) { for (c in 0 until 8) { if (g[r][c] == "wK") { score += 2; break@outer } } }
            if (score > bestScore) { bestScore = score; bestFen = f; bestRot = rot }
        }
        return bestFen to bestRot
    }

    private fun rotGrid(grid: Array<Array<String?>>, rot: Int): Array<Array<String?>> {
        val g = Array(8) { arrayOfNulls<String>(8) }
        for (r in 0 until 8) for (c in 0 until 8) g[r][c] = grid[r][c]
        repeat(rot) {
            val ng = Array(8) { arrayOfNulls<String>(8) }
            for (r in 0 until 8) for (c in 0 until 8) ng[c][7 - r] = g[r][c]
            for (r in 0 until 8) for (c in 0 until 8) g[r][c] = ng[r][c]
        }
        return g
    }

    private object BitmapFactory2 {
        fun decodeStream(`is`: java.io.InputStream): Bitmap =
            android.graphics.BitmapFactory.decodeStream(`is`)!!
    }
}
