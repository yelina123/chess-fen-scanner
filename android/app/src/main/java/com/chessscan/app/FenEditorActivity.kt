package com.chessscan.app

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Typeface
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.chessscan.app.databinding.ActivityFenEditorBinding
import java.io.InputStream

/**
 * FEN 编辑器, UI/交互参考 lichess 开源移动端棋盘编辑器(GPL-3.0):
 *  - 棋盘上下两侧各有棋子菜单: 手形(拖拽模式) + 6棋子 + 垃圾桶(擦除)
 *  - 拖拽模式: 拖动棋盘上的棋子移动, 拖出棋盘删除
 *  - 编辑模式: 点选棋子后, 点击/滑动棋盘格子放置; 选垃圾桶则擦除
 * 代码为独立 Kotlin 实现。
 */
class FenEditorActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_FEN = "fen"
        const val EXTRA_URI = "src_uri"
        const val EXTRA_RESULT = "fen_result"
        private val PIECES = arrayOf("K", "Q", "R", "B", "N", "P")
    }

    private lateinit var binding: ActivityFenEditorBinding
    private val menuButtons = mutableListOf<View>()  // 所有菜单按钮, 用于刷新高亮

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityFenEditorBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val fen = intent.getStringExtra(EXTRA_FEN)?.substringBefore(" ") ?: ""
        binding.fenEditor.setFromFen(fen)
        refreshFen()
        binding.fenEditor.onChanged = { refreshFen() }

        // 原图对照
        val uri = intent.getStringExtra(EXTRA_URI)?.let(Uri::parse)
        val src = readBitmap(uri)
        if (src != null) {
            binding.imgEditorSrc.setImageBitmap(src)
            binding.imgEditorSrc.visibility = View.VISIBLE
        }

        // 构建上下棋子菜单
        buildPieceMenu(binding.menuWhite, "w")
        buildPieceMenu(binding.menuBlack, "b")
        refreshMenuHighlight()

        binding.btnFlip.setOnClickListener { binding.fenEditor.flipBoard() }
        binding.btnClear.setOnClickListener { binding.fenEditor.clearBoard() }
        binding.btnFenCopy.setOnClickListener {
            copy(binding.tvFenOut.text.toString())
            Toast.makeText(this, "已复制FEN", Toast.LENGTH_SHORT).show()
        }
        binding.btnFenDone.setOnClickListener {
            val data = Intent()
            data.putExtra(EXTRA_RESULT, "${binding.tvFenOut.text} w - - 0 1")
            setResult(RESULT_OK, data)
            finish()
        }
    }

    /** 构建一侧棋子菜单: 手形 + 6棋子 + 垃圾桶 */
    private fun buildPieceMenu(container: LinearLayout, side: String) {
        container.removeAllViews()
        menuButtons.clear()
        val dp = resources.displayMetrics.density
        val btnSize = (56 * dp).toInt()

        // 手形: 拖拽模式
        val handBtn = makeMenuButton(btnSize, null, "✋") {
            binding.fenEditor.mode = FenEditorView.Mode.DRAG
            binding.fenEditor.activePiece = null
            refreshMenuHighlight()
        }
        (handBtn.getChildAt(0) as TextView).textSize = 20f
        container.addView(handBtn)

        // 6 棋子
        for (p in PIECES) {
            val key = "$side$p"
            val btn = makeMenuButton(btnSize, key, null) {
                binding.fenEditor.mode = FenEditorView.Mode.EDIT
                binding.fenEditor.activePiece = key
                refreshMenuHighlight()
            }
            container.addView(btn)
        }

        // 垃圾桶: 擦除
        val trashBtn = makeMenuButton(btnSize, null, "🗑") {
            binding.fenEditor.mode = FenEditorView.Mode.EDIT
            binding.fenEditor.activePiece = null
            refreshMenuHighlight()
        }
        (trashBtn.getChildAt(0) as TextView).textSize = 18f
        container.addView(trashBtn)
    }

    private fun makeMenuButton(size: Int, pieceKey: String?, label: String?, onClick: () -> Unit): View {
        val frame = FrameLayout(this).apply {
            layoutParams = LinearLayout.LayoutParams(size, size).apply {
                marginStart = 2; marginEnd = 2
            }
        }
        if (pieceKey != null) {
            val iv = ImageView(this).apply {
                setImageBitmap(binding.fenEditor.getIcon(pieceKey))
                scaleType = ImageView.ScaleType.FIT_CENTER
                setPadding(6, 6, 6, 6)
            }
            frame.addView(iv)
        } else {
            val tv = TextView(this).apply {
                text = label
                gravity = Gravity.CENTER
                setTextColor(Color.GRAY)
            }
            frame.addView(tv)
        }
        frame.setOnClickListener { onClick() }
        frame.tag = pieceKey ?: if (label == "✋") "DRAG" else "ERASE"
        menuButtons.add(frame)
        return frame
    }

    private fun refreshMenuHighlight() {
        val mode = binding.fenEditor.mode
        val active = binding.fenEditor.activePiece
        for (btn in menuButtons) {
            val tag = btn.tag as String
            val selected = when {
                mode == FenEditorView.Mode.DRAG && tag == "DRAG" -> true
                mode == FenEditorView.Mode.EDIT && active == null && tag == "ERASE" -> true
                mode == FenEditorView.Mode.EDIT && active != null && tag == active -> true
                else -> false
            }
            btn.setBackgroundColor(if (selected) Color.argb(60, 0, 150, 255) else Color.TRANSPARENT)
        }
    }

    private fun refreshFen() {
        binding.tvFenOut.text = binding.fenEditor.toFen()
    }

    private fun readBitmap(uri: Uri?): Bitmap? {
        if (uri == null) return null
        return try {
            val input: InputStream? = contentResolver.openInputStream(uri)
            input?.use { BitmapFactory.decodeStream(it) }
        } catch (e: Throwable) { null }
    }

    private fun copy(text: String) {
        val clip = android.content.ClipData.newPlainText("FEN", text)
        val cm = getSystemService(CLIPBOARD_SERVICE) as android.content.ClipboardManager
        cm.setPrimaryClip(clip)
    }
}
