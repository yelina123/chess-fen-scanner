package com.chessscan.app

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Rect
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.chessscan.app.databinding.ActivityCropBinding
import java.io.InputStream

/** 手动框选棋盘页: 显示原图, 拖拽框出棋盘区域, 确认后把 (图片 Uri + 像素 Rect) 返回给主界面。 */
class CropActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_URI = "crop_uri"
        const val EXTRA_RECT = "crop_rect"
    }

    private lateinit var binding: ActivityCropBinding
    private var uri: Uri? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCropBinding.inflate(layoutInflater)
        setContentView(binding.root)

        uri = intent.getStringExtra(EXTRA_URI)?.let(Uri::parse)
        val bmp = readBitmap(uri)
        if (bmp == null) {
            Toast.makeText(this, "无法读取图片", Toast.LENGTH_SHORT).show()
            finish()
            return
        }
        binding.cropView.setBoardBitmap(bmp)
        binding.tvCropHint.text = "拖拽框选棋盘，可拖动调整"

        binding.btnCropOk.setOnClickListener {
            val rect = binding.cropView.getCropRect()
            if (rect == null || rect.width() < 40 || rect.height() < 40) {
                Toast.makeText(this, "请先拖拽框选棋盘区域", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            val data = Intent()
            data.putExtra(EXTRA_URI, uri.toString())
            data.putExtra(EXTRA_RECT, rect)
            setResult(RESULT_OK, data)
            finish()
        }

        binding.btnCropCancel.setOnClickListener {
            setResult(RESULT_CANCELED)
            finish()
        }
    }

    private fun readBitmap(uri: Uri?): Bitmap? {
        if (uri == null) return null
        return try {
            val input: InputStream? = contentResolver.openInputStream(uri)
            input?.use { BitmapFactory.decodeStream(it) }
        } catch (e: Throwable) {
            null
        }
    }
}
