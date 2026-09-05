package com.chessscan.app

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
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

        private const val PREFS = "chessscan_prefs"
        private const val KEY_MODE = "mode"
        private const val KEY_THEME = "theme"
        private const val KEY_CLEAN = "assume_clean"
        // 算法档位: 内部值 -> 显示文案
        private val MODE_LABELS = linkedMapOf(
            "standard"  to "标准（推荐，平衡漏判/误判）",
            "recall"    to "高召回（少漏子，截图模糊/棋子小时用）",
            "precision" to "高精确（少误判，箭头/引擎标注多时用）",
        )
        private const val THEME_AUTO = "auto"
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

        // 版本号
        binding.tvVersion.text = "v${appVersionName()}"

        log("APP", "使用相册选择 (ACTION_PICK + MediaStore)")
        recognizer = ChessRecognizer(this)
        log("APP", recognizer.initMsg)

        setupSpinners()
        setupCleanCheckbox()

        binding.btnPick.setOnClickListener {
            launchGallery()
        }

        binding.btnClear.setOnClickListener {
            clearSelection()
        }

        // 日志区默认折叠, 点击标题行展开/收起
        binding.llLogHeader.setOnClickListener { toggleLog() }
        binding.tvLogToggle.setOnClickListener { toggleLog() }

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

    private fun appVersionName(): String = try {
        val pi = packageManager.getPackageInfo(packageName, 0)
        pi.versionName ?: "?"
    } catch (e: Throwable) { "?" }

    /** 算法档位 + 棋子主题两个下拉框, 选择持久化并实时作用于 recognizer。 */
    private fun setupSpinners() {
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)

        // --- 算法档位 ---
        val modeKeys = MODE_LABELS.keys.toList()
        val modeAdapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, MODE_LABELS.values.toList())
        modeAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        binding.spinnerMode.adapter = modeAdapter
        val savedMode = prefs.getString(KEY_MODE, "standard") ?: "standard"
        recognizer.mode = if (modeKeys.contains(savedMode)) savedMode else "standard"
        binding.spinnerMode.setSelection(modeKeys.indexOf(recognizer.mode))
        binding.spinnerMode.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                val key = modeKeys[position]
                recognizer.mode = key
                prefs.edit().putString(KEY_MODE, key).apply()
                log("CFG", "识别算法切换为: ${MODE_LABELS[key]}")
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }

        // --- 棋子主题 ---
        val setNames = recognizer.pieceSetNames()
        val themeKeys = mutableListOf(THEME_AUTO).apply { addAll(setNames) }
        val themeLabels = themeKeys.map { if (it == THEME_AUTO) "自动（匹配全部 ${setNames.size} 套样式）" else it }
        val themeAdapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, themeLabels)
        themeAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        binding.spinnerTheme.adapter = themeAdapter
        val savedTheme = prefs.getString(KEY_THEME, THEME_AUTO) ?: THEME_AUTO
        val themeIdx = if (savedTheme == THEME_AUTO || !setNames.contains(savedTheme)) 0 else themeKeys.indexOf(savedTheme)
        applyTheme(themeKeys[themeIdx])
        binding.spinnerTheme.setSelection(themeIdx)
        binding.spinnerTheme.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                val key = themeKeys[position]
                applyTheme(key)
                prefs.edit().putString(KEY_THEME, key).apply()
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }
    }

    private fun applyTheme(key: String) {
        recognizer.theme = if (key == THEME_AUTO) null else key
        log("CFG", "棋子主题切换为: ${if (key == THEME_AUTO) "自动(全部套件)" else key}")
    }

    /** "图中无引擎箭头/标注" 勾选框: 勾选后跳过箭头判空, 直接取最佳匹配。 */
    private fun setupCleanCheckbox() {
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        val saved = prefs.getBoolean(KEY_CLEAN, false)
        recognizer.assumeClean = saved
        binding.cbClean.isChecked = saved
        binding.cbClean.setOnCheckedChangeListener { _, isChecked ->
            recognizer.assumeClean = isChecked
            prefs.edit().putBoolean(KEY_CLEAN, isChecked).apply()
            log("CFG", "无箭头/标注模式: ${if (isChecked) "开启(更准确)" else "关闭(默认)"}")
        }
    }

    override fun onResume() { super.onResume(); refreshLogView() }

    private fun refreshLogView() {
        binding.tvLog.text = dumpLog()
    }

    /** 清除当前已选图片: 清空原图/标注预览、FEN、状态(日志保留, 便于诊断) */
    private fun clearSelection() {
        binding.imgBoard.setImageDrawable(null)
        binding.imgPreview.setImageDrawable(null)
        binding.tvFen.text = ""
        binding.tvStatus.text = "尚未识别"
        toast("已清除")
    }

    private fun toggleLog() {
        val show = binding.llLogBody.visibility != View.VISIBLE
        binding.llLogBody.visibility = if (show) View.VISIBLE else View.GONE
        binding.tvLogToggle.text = if (show) "收起 ▴" else "展开 ▾"
    }

    private fun loadAndRecognize(uri: Uri) {
        log("IMAGE", "读取图片: ${uri.path ?: uri.toString()}")
        val bitmap = readBitmap(uri)
        if (bitmap == null) { toast("无法读取图片"); log("IMAGE", "读取图片失败"); refreshLogView(); return }
        log("IMAGE", "图片尺寸: ${bitmap.width}x${bitmap.height}, config=${bitmap.config}")
        binding.imgBoard.setImageBitmap(bitmap)
        binding.imgPreview.setImageDrawable(null)
        binding.tvStatus.text = "识别中..."
        binding.tvFen.text = ""
        binding.tvLog.text = dumpLog()
        Thread {
            try {
                val result = recognizer.recognize(bitmap)
                val fen = result.fen ?: "定位不到棋盘"
                runOnUiThread {
                    binding.tvStatus.text = if (result.preview != null) "识别完成（请核对下方标注图）" else fen
                    binding.tvFen.text = fen
                    if (result.preview != null) binding.imgPreview.setImageBitmap(result.preview)
                    log("RECOG", "识别完成: $fen")
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
