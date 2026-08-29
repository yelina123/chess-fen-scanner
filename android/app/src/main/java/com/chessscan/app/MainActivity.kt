package com.chessscan.app

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import com.chessscan.app.databinding.ActivityMainBinding
import java.io.InputStream
import java.io.StringWriter
import java.io.PrintWriter

class MainActivity : AppCompatActivity() {

    companion object {
        // 进程级日志缓冲, 方便查看和复制
        val logBuf = StringBuilder()
        fun log(tag: String, msg: String) {
            val line = "[$tag] $msg\n"
            synchronized(logBuf) { logBuf.append(line) }
        }
        fun dumpLog(): String = synchronized(logBuf) { logBuf.toString() }
        fun clearLog() { synchronized(logBuf) { logBuf.setLength(0) } }
    }

    private lateinit var binding: ActivityMainBinding
    private lateinit var recognizer: ChessRecognizer

    // 打开系统相册 (ACTION_PICK + MediaStore)。相比 Photo Picker,
    // 在华为/鸿蒙等机型上更可能弹出"相册"而非文件浏览器。
    private val pickImage = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val uri = result.data?.data
        uri?.let { loadAndRecognize(it) } ?: toast("未选择图片")
    }

    private fun launchGallery() {
        try {
            val intent = Intent(Intent.ACTION_PICK, android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI)
            intent.type = "image/*"
            pickImage.launch(intent)
        } catch (e: Throwable) {
            toast("无法打开相册: ${e.message}")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        log("APP", "使用相册选择 (Photo Picker)")
        recognizer = ChessRecognizer(this)
        log("APP", recognizer.initMsg)

        binding.btnPick.setOnClickListener {
            launchGallery()
        }

        binding.btnCopy.setOnClickListener {
            val fen = binding.tvFen.text.toString()
            if (fen.isNotEmpty()) {
                copyToClipboard("FEN", fen)
                toast("已复制FEN")
            } else toast("暂无FEN")
        }

        binding.btnOpenLichess.setOnClickListener {
            launchLichessEditorIfAvailable(binding.tvFen.text.toString())
        }

        binding.btnCopyLog.setOnClickListener {
            copyToClipboard("日志", dumpLog())
            toast("已复制日志")
        }
        binding.btnClearLog.setOnClickListener {
            clearLog(); refreshLogView()
        }
    }

    override fun onResume() { super.onResume(); refreshLogView() }

    private fun refreshLogView() {
        binding.tvLog.text = dumpLog()
    }

    private fun loadAndRecognize(uri: Uri) {
        log("IMAGE", "读取图片: ${uri.path ?: uri.toString()}")
        val bitmap = readBitmap(uri)
        if (bitmap == null) { toast("无法读取图片"); log("IMAGE", "读取图片失败"); refreshLogView(); return }
        log("IMAGE", "图片尺寸: ${bitmap.width}x${bitmap.height}, config=${bitmap.config}")
        binding.imgBoard.setImageBitmap(bitmap)
        binding.tvStatus.text = "识别中..."
        binding.tvFen.text = ""
        binding.tvLog.text = dumpLog()
        Thread {
            try {
                val result = recognizer.recognize(bitmap)
                runOnUiThread {
                    binding.tvStatus.text = "识别完成"
                    binding.tvFen.text = result
                    log("RECOG", "识别完成: $result")
                    log("DIAG", ChessRecognizer.diag.toString())
                    refreshLogView()
                }
            } catch (e: Throwable) {
                val sw = StringWriter(); e.printStackTrace(PrintWriter(sw))
                log("RECOG", "识别出错: ${e.javaClass.simpleName}: ${e.message}\n${sw.toString()}")
                log("DIAG", ChessRecognizer.diag.toString())
                runOnUiThread {
                    binding.tvStatus.text = "识别出错: ${e.javaClass.simpleName}"
                    refreshLogView()
                }
            }
        }.start()
    }

    private fun readBitmap(uri: Uri): Bitmap? {
        return try {
            val input: InputStream? = contentResolver.openInputStream(uri)
            input?.use { BitmapFactory.decodeStream(it) }
        } catch (e: Throwable) {
            log("IMAGE", "readBitmap 异常: ${e.javaClass.simpleName}: ${e.message}")
            null
        }
    }

    private fun copyToClipboard(label: String, text: String) {
        val clip = android.content.ClipData.newPlainText(label, text)
        val cm = getSystemService(CLIPBOARD_SERVICE) as android.content.ClipboardManager
        cm.setPrimaryClip(clip)
    }

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()

    private fun launchLichessEditorIfAvailable(fen: String) {
        if (fen.isEmpty()) { toast("暂无FEN"); return }
        val url = "https://lichess.org/editor/${fen.replace(" ", "_")}"
        try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
        catch (e: Exception) { toast("无法打开浏览器") }
    }
}
