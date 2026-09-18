package com.chessscan.app

import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View

/**
 * 8x8 FEN 棋盘编辑器, 交互设计参考 lichess 开源移动端(flutter-chessground ChessboardEditor, GPL-3.0):
 *  - DRAG 模式: 长按拖动棋盘上的棋子移动, 拖出棋盘即删除
 *  - EDIT 模式: 点击/滑动棋盘格子放置当前选中棋子, 选中"擦除"则清空格子
 * grid[0] = rank8, grid[7] = rank1. 代码为独立 Kotlin 实现。
 */
class FenEditorView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null
) : View(context, attrs) {

    enum class Mode { DRAG, EDIT }

    companion object {
        private val LIGHT = intArrayOf(239, 216, 182)
        private val DARK = intArrayOf(180, 137, 97)
    }

    var grid: Array<Array<String?>> = Array(8) { arrayOfNulls(8) }
    var onChanged: (() -> Unit)? = null

    var mode: Mode = Mode.DRAG
        set(value) { field = value; invalidate() }
    /** EDIT 模式下当前选中的棋子("wP"等); null 表示擦除模式 */
    var activePiece: String? = null
        set(value) { field = value; invalidate() }

    private val icons: MutableMap<String, Bitmap> = HashMap()

    // 拖拽状态
    private var dragFrom: IntArray? = null   // [r, c]
    private var dragPiece: String? = null
    private var dragX = 0f; private var dragY = 0f

    init { loadIcons() }

    private fun loadIcons() {
        try {
            val assets = context.assets
            for (color in arrayOf("w", "b")) {
                for (piece in arrayOf("K", "Q", "R", "B", "N", "P")) {
                    val key = "$color$piece"
                    val `is` = assets.open("pieces/cburnett/png/${key}_90.png")
                    icons[key] = BitmapFactory.decodeStream(`is`)
                }
            }
        } catch (e: Exception) { /* 图标缺失不致命 */ }
    }

    fun getIcon(colorPiece: String?): Bitmap? = colorPiece?.let { icons[it] }

    fun setFromFen(fen: String) {
        val ranks = fen.split("/")
        for (r in 0 until 8) {
            val row = ranks.getOrNull(r) ?: break
            var c = 0
            for (ch in row) {
                if (ch.isDigit()) { c += ch.digitToInt() }
                else {
                    val color = if (ch.isUpperCase()) "w" else "b"
                    grid[r][c] = color + ch.uppercase()
                    c++
                }
            }
        }
        invalidate()
    }

    fun toFen(): String {
        val sb = StringBuilder()
        for (r in 0 until 8) {
            var e = 0
            for (c in 0 until 8) {
                val pc = grid[r][c]
                if (pc == null) e++
                else {
                    if (e > 0) { sb.append(e); e = 0 }
                    sb.append(if (pc[0] == 'w') pc[1] else pc[1].lowercase())
                }
            }
            if (e > 0) sb.append(e)
            if (r < 7) sb.append('/')
        }
        return sb.toString()
    }

    fun clearBoard() {
        grid = Array(8) { arrayOfNulls(8) }
        invalidate()
        onChanged?.invoke()
    }

    /** 翻转棋盘(旋转180度) */
    fun flipBoard() {
        val new = Array(8) { arrayOfNulls<String?>(8) }
        for (r in 0 until 8) for (c in 0 until 8) {
            new[7 - r][7 - c] = grid[r][c]
        }
        grid = new
        invalidate()
        onChanged?.invoke()
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val w = MeasureSpec.getSize(widthMeasureSpec)
        val h = MeasureSpec.getSize(heightMeasureSpec)
        val side = minOf(
            if (MeasureSpec.getMode(widthMeasureSpec) == MeasureSpec.UNSPECIFIED) Int.MAX_VALUE else w,
            if (MeasureSpec.getMode(heightMeasureSpec) == MeasureSpec.UNSPECIFIED) Int.MAX_VALUE else h
        )
        setMeasuredDimension(side, side)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val cell = minOf(width, height) / 8f
        val offX = (width - cell * 8) / 2f
        val offY = (height - cell * 8) / 2f
        val paint = Paint().apply { isAntiAlias = true }

        for (r in 0 until 8) {
            for (c in 0 until 8) {
                val color = if ((r + c) % 2 == 0) LIGHT else DARK
                paint.color = Color.rgb(color[0], color[1], color[2])
                canvas.drawRect(offX + c * cell, offY + r * cell,
                    offX + (c + 1) * cell, offY + (r + 1) * cell, paint)
                val pc = grid[r][c] ?: continue
                // 拖拽中的棋子不画在原位
                if (dragFrom != null && dragFrom!![0] == r && dragFrom!![1] == c) continue
                val icon = icons[pc] ?: continue
                val dst = RectF(offX + c * cell + cell * 0.06f, offY + r * cell + cell * 0.06f,
                    offX + (c + 1) * cell - cell * 0.06f, offY + (r + 1) * cell - cell * 0.06f)
                canvas.drawBitmap(icon, null, dst, null)
            }
        }
        // 外框
        val border = Paint().apply {
            style = Paint.Style.STROKE; strokeWidth = 6f
            color = Color.rgb(0, 120, 200)
        }
        canvas.drawRect(offX, offY, offX + cell * 8, offY + cell * 8, border)

        // 拖拽中的棋子跟随手指(放大)
        if (dragFrom != null && dragPiece != null) {
            val icon = icons[dragPiece] ?: return
            val size = cell * 1.3f
            val dst = RectF(dragX - size / 2, dragY - size / 2, dragX + size / 2, dragY + size / 2)
            canvas.drawBitmap(icon, null, dst, null)
        }
    }

    private fun cellFromXY(x: Float, y: Float): IntArray? {
        val cell = minOf(width, height) / 8f
        val offX = (width - cell * 8) / 2f
        val offY = (height - cell * 8) / 2f
        val c = ((x - offX) / cell).toInt()
        val r = ((y - offY) / cell).toInt()
        return if (r in 0 until 8 && c in 0 until 8) intArrayOf(r, c) else null
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                dragX = event.x; dragY = event.y
                if (mode == Mode.DRAG) {
                    val pos = cellFromXY(event.x, event.y)
                    if (pos != null && grid[pos[0]][pos[1]] != null) {
                        dragFrom = pos
                        dragPiece = grid[pos[0]][pos[1]]
                        invalidate()
                    }
                } else {
                    // EDIT 模式: 放置/擦除
                    applyEdit(event.x, event.y)
                }
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                dragX = event.x; dragY = event.y
                if (mode == Mode.EDIT) {
                    applyEdit(event.x, event.y)
                } else if (dragFrom != null) {
                    invalidate()
                }
                return true
            }
            MotionEvent.ACTION_UP -> {
                if (mode == Mode.DRAG && dragFrom != null) {
                    val from = dragFrom!!
                    val to = cellFromXY(event.x, event.y)
                    if (to != null) {
                        // 移动到目标格(覆盖)
                        grid[to[0]][to[1]] = dragPiece
                        if (from[0] != to[0] || from[1] != to[1]) {
                            grid[from[0]][from[1]] = null
                        }
                    } else {
                        // 拖出棋盘: 删除
                        grid[from[0]][from[1]] = null
                    }
                    onChanged?.invoke()
                }
                dragFrom = null; dragPiece = null
                invalidate()
                return true
            }
            MotionEvent.ACTION_CANCEL -> {
                dragFrom = null; dragPiece = null
                invalidate()
                return true
            }
        }
        return super.onTouchEvent(event)
    }

    private var lastEditPos: IntArray? = null
    private fun applyEdit(x: Float, y: Float) {
        val pos = cellFromXY(x, y) ?: return
        if (lastEditPos != null && lastEditPos!![0] == pos[0] && lastEditPos!![1] == pos[1]) return
        lastEditPos = pos
        if (activePiece != null) {
            grid[pos[0]][pos[1]] = activePiece
        } else {
            grid[pos[0]][pos[1]] = null
        }
        invalidate()
        onChanged?.invoke()
    }
}
