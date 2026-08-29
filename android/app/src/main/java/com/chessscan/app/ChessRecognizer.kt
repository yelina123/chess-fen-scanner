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
        // 逐格诊断缓冲
        val diag = StringBuilder()
        fun clearDiag() { synchronized(diag) { diag.setLength(0) } }
    }

    private val appContext = context.applicationContext
    private var opencvReady = false
    private val templates: MutableMap<String, Mat> = HashMap()

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
        for (color in arrayOf("w", "b")) {
            for (piece in PIECES) {
                try {
                    val name = "${color}${piece}_90.png"
                    val `is` = appContext.assets.open("pieces/cburnett/png/$name")
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
                    // resize to CAN
                    val out = Mat()
                    Imgproc.resize(a, out, Size(CAN.toDouble(), CAN.toDouble()))
                    Imgproc.threshold(out, out, 127.0, 255.0, Imgproc.THRESH_BINARY)
                    templates["$color$piece"] = out
                } catch (e: Exception) {
                    // template missing; skip
                }
            }
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
    fun recognize(bitmap: Bitmap): String {
        if (!opencvReady) return "OpenCV 初始化失败"
        // 兼容性: 硬件位图/非ARGB无法直接转Mat, 统一复制成 ARGB_8888 软件位图
        val safe = if (bitmap.config == Bitmap.Config.HARDWARE ||
            bitmap.config != Bitmap.Config.ARGB_8888) {
            bitmap.copy(Bitmap.Config.ARGB_8888, false)
        } else bitmap
        val bgr = Mat()
        Utils.bitmapToMat(safe, bgr)
        Imgproc.cvtColor(bgr, bgr, Imgproc.COLOR_RGBA2BGR)

        val boardRect = locateBoard(bgr) ?: return "定位不到棋盘"
        val board = Mat(bgr, Rect(boardRect[0], boardRect[1], boardRect[2] - boardRect[0], boardRect[3] - boardRect[1]))
        val cellCount = 8
        val cw = board.cols(); val ch = board.rows()
        val cellW = cw / cellCount; val cellH = ch / cellCount
        clearDiag()
        diag.append("board=${boardRect.contentToString()} size=${cw}x${ch} cell=${cellW}x${cellH}\n")
        val grid: Array<Array<String?>> = Array(8) { arrayOfNulls<String>(8) }

        for (r in 0 until 8) {
            for (c in 0 until 8) {
                val cell = Mat(board, Rect(c * cellW, r * cellH, cellW, cellH))
                grid[r][c] = classify(cell)
            }
        }
        val (fen, rot) = bestOrientation(grid)
        return "$fen w - - 0 1"
    }

    // ---------------- 单格分类 ----------------
    private fun classify(cell: Mat): String? {
        val ch = cell.rows(); val cw = cell.cols()
        val hmask = highlightMask(cell)

        // 前景 = 与两种棋盘底色(LIGHT/DARK)距离都大的像素。
        // 这样黑白棋子都能从任何颜色(浅格/深格)上提取, 不依赖"格子内均值"背景(后者会被
        // 深色格上的黑棋子拉暗, 导致黑子前景提取失败 -> 误判为空)。
        val dL = Mat()
        Core.absdiff(cell, Mat(cell.rows(), cell.cols(), CvType.CV_8UC3, Scalar(LIGHT[0], LIGHT[1], LIGHT[2])), dL)
        val dD = Mat()
        Core.absdiff(cell, Mat(cell.rows(), cell.cols(), CvType.CV_8UC3, Scalar(DARK[0], DARK[1], DARK[2])), dD)
        Imgproc.cvtColor(dL, dL, Imgproc.COLOR_BGR2GRAY)
        Imgproc.cvtColor(dD, dD, Imgproc.COLOR_BGR2GRAY)
        // 与任一棋盘色接近则不是棋子; 与两者都远才是棋子
        val nearL = Mat(); Core.inRange(dL, Scalar(0.0), Scalar(PAL_TOL), nearL)
        val nearD = Mat(); Core.inRange(dD, Scalar(0.0), Scalar(PAL_TOL), nearD)
        val isBoard = Mat(); Core.bitwise_or(nearL, nearD, isBoard)
        val fg = Mat()
        Core.bitwise_not(isBoard, fg)
        fg.setTo(Scalar(0.0), hmask) // 高亮不是棋子
        Imgproc.morphologyEx(fg, fg, Imgproc.MORPH_OPEN, Imgproc.getStructuringElement(Imgproc.MORPH_RECT, Size(3.0, 3.0)))
        Imgproc.morphologyEx(fg, fg, Imgproc.MORPH_CLOSE, Imgproc.getStructuringElement(Imgproc.MORPH_RECT, Size(5.0, 5.0)))

        val frac = Core.countNonZero(fg).toDouble() / (ch * cw)
        diag.append("frac=$frac ")
        if (frac < 0.03) { diag.append("->EMPTY\n"); return null }

        // 判色：剪影像素亮度中位数
        val color = pieceColor(fg, cell)
        // bbox 归一化 + IoU
        val bb = bboxOf(fg)
        val cm = Mat()
        val cropped = fg.submat(bb)
        Imgproc.resize(cropped, cm, Size(CAN.toDouble(), CAN.toDouble()))
        Imgproc.threshold(cm, cm, 127.0, 255.0, Imgproc.THRESH_BINARY)

        var bestIou = -1.0; var bestPiece: String? = null
        for (piece in PIECES) {
            val tpl = templates["$color$piece"] ?: continue
            val inter = Mat()
            Core.bitwise_and(cm, tpl, inter)
            val union = Mat()
            Core.bitwise_or(cm, tpl, union)
            val iou = Core.countNonZero(inter).toDouble() / max(1, Core.countNonZero(union))
            if (iou > bestIou) { bestIou = iou; bestPiece = piece }
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
        val green = Mat(); Core.inRange(hsv, Scalar(35.0, 40.0, 60.0), Scalar(85.0, 255.0, 255.0), green)
        val yellow = Mat(); Core.inRange(hsv, Scalar(12.0, 50.0, 100.0), Scalar(35.0, 255.0, 255.0), yellow)
        val red = Mat(); Core.inRange(hsv, Scalar(0.0, 40.0, 60.0), Scalar(10.0, 255.0, 255.0), red)
        val red2 = Mat(); Core.inRange(hsv, Scalar(170.0, 40.0, 60.0), Scalar(180.0, 255.0, 255.0), red2)
        val out = Mat()
        Core.bitwise_or(green, yellow, out)
        Core.bitwise_or(out, red, out)
        Core.bitwise_or(out, red2, out)
        return out
    }

    // ---------------- 棋盘定位 ----------------
    private fun locateBoard(bgr: Mat): IntArray? {
        val h = bgr.rows(); val w = bgr.cols()
        val bm = Mat()
        val diffL = Mat(); val diffD = Mat()
        Core.absdiff(bgr, Mat(bgr.rows(), bgr.cols(), CvType.CV_8UC3, Scalar(LIGHT[0], LIGHT[1], LIGHT[2])), diffL)
        Core.absdiff(bgr, Mat(bgr.rows(), bgr.cols(), CvType.CV_8UC3, Scalar(DARK[0], DARK[1], DARK[2])), diffD)
        val ml = Mat(); val md = Mat()
        Core.inRange(diffL, Scalar(0.0, 0.0, 0.0), Scalar(PAL_TOL, PAL_TOL, PAL_TOL), ml)
        Core.inRange(diffD, Scalar(0.0, 0.0, 0.0), Scalar(PAL_TOL, PAL_TOL, PAL_TOL), md)
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
