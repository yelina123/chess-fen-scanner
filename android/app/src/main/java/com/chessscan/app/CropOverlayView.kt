package com.chessscan.app

import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View

/**
 * 手动框选棋盘: 显示原图(fitCenter), 支持三种交互:
 *  - 拖拽矩形内部 -> 整体移动
 *  - 拖拽四角手柄 -> 缩放
 *  - 在矩形外按下 -> 重新画框
 * 内部以图片像素坐标保存选框。
 */
class CropOverlayView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null
) : View(context, attrs) {

    private var bitmap: Bitmap? = null
    private var crop: Rect? = null
    // fitCenter 映射（onSizeChanged / setBoardBitmap / onDraw 都会刷新）
    private var scale = 1f
    private var offX = 0f; private var offY = 0f
    private var mappingReady = false

    private fun updateMapping() {
        val bmp = bitmap ?: return
        if (width <= 0 || height <= 0) return
        scale = minOf(width.toFloat() / bmp.width, height.toFloat() / bmp.height)
        offX = (width - bmp.width * scale) / 2f
        offY = (height - bmp.height * scale) / 2f
        mappingReady = true
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        updateMapping()
    }

    private enum class DragMode { NONE, NEW, MOVE, RESIZE_TL, RESIZE_TR, RESIZE_BL, RESIZE_BR }
    private var mode = DragMode.NONE
    private var startX = 0f; private var startY = 0f   // 图片坐标
    private var startRect: Rect? = null

    private val maskPaint = Paint().apply {
        color = Color.argb(120, 0, 0, 0)
        style = Paint.Style.FILL
    }
    private val borderPaint = Paint().apply {
        color = Color.rgb(0, 220, 0)
        style = Paint.Style.STROKE
        strokeWidth = 8f
    }
    private val cornerPaint = Paint().apply {
        color = Color.WHITE
        style = Paint.Style.STROKE
        strokeWidth = 12f
    }

    fun setBoardBitmap(bmp: Bitmap) {
        bitmap = bmp
        crop = null
        updateMapping()
        invalidate()
    }

    fun getCropRect(): Rect? = crop

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val bmp = bitmap ?: return
        updateMapping()
        val vw = width.toFloat(); val vh = height.toFloat()
        val dst = RectF(offX, offY, offX + bmp.width * scale, offY + bmp.height * scale)
        canvas.drawBitmap(bmp, null, dst, null)

        val c = crop ?: return
        val rect = RectF(c.left * scale + offX, c.top * scale + offY,
            c.right * scale + offX, c.bottom * scale + offY)
        canvas.drawRect(0f, 0f, width.toFloat(), rect.top, maskPaint)
        canvas.drawRect(0f, rect.bottom, width.toFloat(), height.toFloat(), maskPaint)
        canvas.drawRect(0f, rect.top, rect.left, rect.bottom, maskPaint)
        canvas.drawRect(rect.right, rect.top, width.toFloat(), rect.bottom, maskPaint)
        canvas.drawRect(rect, borderPaint)
        val r = 30f
        val corners = listOf(
            RectF(rect.left - r, rect.top - r, rect.left + r, rect.top + r),
            RectF(rect.right - r, rect.top - r, rect.right + r, rect.top + r),
            RectF(rect.left - r, rect.bottom - r, rect.left + r, rect.bottom + r),
            RectF(rect.right - r, rect.bottom - r, rect.right + r, rect.bottom + r),
        )
        for (c2 in corners) canvas.drawRect(c2, cornerPaint)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (!mappingReady) updateMapping()
        val ix = viewToImgX(event.x)
        val iy = viewToImgY(event.y)
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                val c = crop
                if (c != null) {
                    val hit = hitCorner(ix, iy, c)
                    when {
                        hit != null -> { mode = hit; startRect = Rect(c) }
                        c.contains(ix.toInt(), iy.toInt()) -> { mode = DragMode.MOVE; startRect = Rect(c) }
                        else -> { mode = DragMode.NEW }
                    }
                } else {
                    mode = DragMode.NEW
                }
                startX = ix; startY = iy
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                when (mode) {
                    DragMode.NEW -> updateNew(ix, iy)
                    DragMode.MOVE -> updateMove(ix, iy)
                    DragMode.RESIZE_TL -> updateResize(ix, iy, true, true)
                    DragMode.RESIZE_TR -> updateResize(ix, iy, false, true)
                    DragMode.RESIZE_BL -> updateResize(ix, iy, true, false)
                    DragMode.RESIZE_BR -> updateResize(ix, iy, false, false)
                    else -> {}
                }
                invalidate()
                return true
            }
            MotionEvent.ACTION_UP -> {
                val w = crop?.width() ?: 0; val h = crop?.height() ?: 0
                if (w < 40 || h < 40) crop = null
                mode = DragMode.NONE
                startRect = null
                invalidate()
                return true
            }
        }
        return super.onTouchEvent(event)
    }

    private fun hitCorner(ix: Float, iy: Float, c: Rect): DragMode? {
        val th = 48f / scale   // 图片坐标下的命中半径
        val pts = listOf(
            DragMode.RESIZE_TL to (c.left to c.top),
            DragMode.RESIZE_TR to (c.right to c.top),
            DragMode.RESIZE_BL to (c.left to c.bottom),
            DragMode.RESIZE_BR to (c.right to c.bottom),
        )
        for ((m, p) in pts) {
            if (kotlin.math.abs(ix - p.first) < th && kotlin.math.abs(iy - p.second) < th) return m
        }
        return null
    }

    private fun clampX(v: Float) = v.coerceIn(0f, (bitmap?.width ?: 1).toFloat() - 1)
    private fun clampY(v: Float) = v.coerceIn(0f, (bitmap?.height ?: 1).toFloat() - 1)

    private fun updateNew(ix: Float, iy: Float) {
        crop = Rect(
            clampX(kotlin.math.min(startX, ix)).toInt(),
            clampY(kotlin.math.min(startY, iy)).toInt(),
            clampX(kotlin.math.max(startX, ix)).toInt(),
            clampY(kotlin.math.max(startY, iy)).toInt(),
        )
    }

    private fun updateMove(ix: Float, iy: Float) {
        val s = startRect ?: return
        val dx = ix - startX; val dy = iy - startY
        val bw = bitmap?.width ?: 1; val bh = bitmap?.height ?: 1
        val w = s.width(); val h = s.height()
        var nl = (s.left + dx).toInt()
        var nt = (s.top + dy).toInt()
        if (nl < 0) nl = 0; if (nt < 0) nt = 0
        if (nl + w > bw) nl = bw - w
        if (nt + h > bh) nt = bh - h
        crop = Rect(nl, nt, nl + w, nt + h)
    }

    private fun updateResize(ix: Float, iy: Float, leftSide: Boolean, topSide: Boolean) {
        val s = startRect ?: return
        val l = if (leftSide) clampX(ix).toInt() else s.left
        val t = if (topSide) clampY(iy).toInt() else s.top
        val r = if (leftSide) s.right else clampX(ix).toInt()
        val b = if (topSide) s.bottom else clampY(iy).toInt()
        if (r - l < 20 || b - t < 20) return
        crop = Rect(l, t, r, b)
    }

    private fun viewToImgX(vx: Float) = (vx - offX) / scale
    private fun viewToImgY(vy: Float) = (vy - offY) / scale
}
