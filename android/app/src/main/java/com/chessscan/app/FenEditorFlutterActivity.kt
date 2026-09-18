package com.chessscan.app

import android.content.Intent
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * FEN 编辑器, 基于 Flutter + lichess chessground (ChessboardEditor)。
 * 通过 MethodChannel 与 Dart 端通信: 传入初始 FEN, 编辑完成后返回。
 */
class FenEditorFlutterActivity : FlutterActivity() {

    companion object {
        const val EXTRA_FEN = "fen"
        const val EXTRA_RESULT = "fen_result"
        private const val CHANNEL = "com.chessscan/editor"
    }

    private var initialFen = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        initialFen = intent.getStringExtra(EXTRA_FEN)?.substringBefore(" ") ?: ""
        super.onCreate(savedInstanceState)
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "requestFen" -> result.success(initialFen)
                    "finish" -> {
                        val fen = call.arguments as? String ?: ""
                        val data = Intent()
                        data.putExtra(EXTRA_RESULT, "$fen w - - 0 1")
                        setResult(RESULT_OK, data)
                        finish()
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }
    }
}
