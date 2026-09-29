import 'dart:typed_data';
import 'dart:isolate';

import 'package:chessground/chessground.dart';
import 'package:dartchess/dartchess.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image/image.dart' as img;
import 'package:image_picker/image_picker.dart';

import '../models/recognizer.dart';
import '../models/settings.dart';
import '../models/template_loader.dart';
import 'about_screen.dart';
import 'crop_screen.dart';
import 'fen_editor_screen.dart';
import 'log_screen.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _picker = ImagePicker();
  late AppSettings _settings;

  Uint8List? _imageBytes;
  int _imgW = 0, _imgH = 0;

  bool _busy = false;
  RecogResult? _result;
  String? _displayFen; // 编辑后的 FEN
  Side _orientation = Side.white;

  /// 截图棋盘预览（棋盘区域裁剪 + 网格 + 识别标注），PNG
  Uint8List? _boardPreviewPng;

  /// 最近一次识别的逐格诊断日志
  List<String> _diag = const [];

  Map<String, Map<String, Uint8List>> _templates = {};

  static const _version = '2.0.2';
  static const _build = '25';

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    _settings = await AppSettings.load();
    // 模板在主 isolate 加载（rootBundle 只能在主 isolate 使用）
    try {
      final tpl = await TemplateLoader.load();
      if (mounted) {
        setState(() => _templates = tpl);
      }
    } catch (e) {
      debugPrint('模板加载失败: $e');
    }
  }

  // ---------------- 选图 ----------------
  Future<void> _pickImage(ImageSource source) async {
    try {
      final file = await _picker.pickImage(source: source, maxWidth: 2600, maxHeight: 2600, imageQuality: 95);
      if (file == null) return;
      final bytes = await file.readAsBytes();
      final decoded = img.decodeImage(bytes);
      if (decoded == null) {
        _toast('无法解析图片');
        return;
      }
      // 转 RGB 平面数组
      final rgb = Uint8List(decoded.width * decoded.height * 3);
      var o = 0;
      for (var y = 0; y < decoded.height; y++) {
        for (var x = 0; x < decoded.width; x++) {
          final p = decoded.getPixel(x, y);
          rgb[o++] = p.r.toInt();
          rgb[o++] = p.g.toInt();
          rgb[o++] = p.b.toInt();
        }
      }
      setState(() {
        _imageBytes = rgb;
        _imgW = decoded.width;
        _imgH = decoded.height;
        _result = null;
        _displayFen = null;
        _orientation = Side.white;
      });
      await _recognize();
    } catch (e) {
      _toast('选择图片失败: $e');
    }
  }

  // ---------------- 识别 ----------------
  Future<void> _recognize({BoardRectView? rect}) async {
    final bytes = _imageBytes;
    if (bytes == null) return;
    setState(() { _busy = true; });

    final templates = _templates;
    if (templates.isEmpty) {
      setState(() { _busy = false; });
      _toast('棋子模板加载中，请稍候重试');
      return;
    }
    final w = _imgW, h = _imgH;
    final mode = _settings.mode;
    final theme = _settings.theme;
    final assumeClean = _settings.assumeClean;
    final boardRect = rect == null
        ? null
        : BoardRect(
            (rect.left * w).round(),
            (rect.top * h).round(),
            ((rect.right - rect.left) * w).round(),
            ((rect.bottom - rect.top) * h).round(),
          );

    try {
      // 用 Isolate.spawn + 顶层 worker（不捕获 this，避免把 Widget 树发进 isolate）
      final job = RecogJob(
        templates: templates,
        rgb: bytes,
        w: w,
        h: h,
        boardRect: boardRect,
        mode: mode,
        theme: theme,
        assumeClean: assumeClean,
      );
      final port = ReceivePort();
      await Isolate.spawn(_recognizeWorker, [port.sendPort, job]);
      final result = await port.first as RecogResult;
      port.close();
      if (!mounted) return;
      setState(() {
        _busy = false;
        _result = result;
        _displayFen = result.fen;
        _boardPreviewPng = _buildBoardPreview();
        _diag = result.diag;
      });
      if (result.error != null) _toast(result.error!);
    } catch (e) {
      if (!mounted) return;
      setState(() { _busy = false; });
      _toast('识别失败: $e');
    }
  }

  // ---------------- 操作 ----------------
  Future<void> _openCrop() async {
    final bytes = _imageBytes;
    if (bytes == null) return;
    // 需要原图字节用于显示：把 RGB 转回可显示的图像
    final disp = _rgbToDisplayImage();
    if (disp == null) return;
    final initial = _result != null
        ? BoardRectView(
            _result!.bx0 / _imgW, _result!.by0 / _imgH,
            (_result!.bx0 + _result!.bw) / _imgW, (_result!.by0 + _result!.bh) / _imgH)
        : null;
    final rect = await Navigator.push<BoardRectView>(
      context,
      MaterialPageRoute(
        builder: (_) => CropScreen(
          imageBytes: disp,
          imageWidth: _imgW,
          imageHeight: _imgH,
          initialRect: initial,
        ),
      ),
    );
    if (rect != null) {
      await _recognize(rect: rect);
    }
  }

  Uint8List? _rgbToDisplayImage() {
    final bytes = _imageBytes;
    if (bytes == null) return null;
    final im = img.Image(width: _imgW, height: _imgH);
    var o = 0;
    for (var y = 0; y < _imgH; y++) {
      for (var x = 0; x < _imgW; x++) {
        im.setPixelRgb(x, y, bytes[o], bytes[o + 1], bytes[o + 2]);
        o += 3;
      }
    }
    return Uint8List.fromList(img.encodePng(im));
  }

  Future<void> _openEditor() async {
    final fen = _displayFen ?? _result?.fen;
    if (fen == null) return;
    final ps = _themeToPieceSet(_settings.theme);
    final edited = await Navigator.push<String>(
      context,
      MaterialPageRoute(
        builder: (_) => FenEditorScreen(
          initialFen: fen,
          pieceSet: ps,
          boardPreview: _boardPreviewPng,
        ),
      ),
    );
    if (edited != null && edited.isNotEmpty) {
      setState(() => _displayFen = edited);
      _toast('已更新 FEN');
    }
  }

  /// 估算 BitmapFont 字符串宽度
  int _textWidth(img.BitmapFont font, String s) {
    var w = 0;
    for (final c in s.codeUnits) {
      final ch = font.characters[c];
      if (ch != null) w += ch.xAdvance;
    }
    return w;
  }

  /// 生成截图棋盘预览：裁剪棋盘区域，画 8x8 网格并标注识别棋子。
  Uint8List? _buildBoardPreview() {
    final result = _result;
    final bytes = _imageBytes;
    if (result == null || result.error != null || bytes == null) return null;
    final bx0 = result.bx0, by0 = result.by0, bw = result.bw, bh = result.bh;
    if (bw < 8 || bh < 8) return null;

    const cell = 64;
    final size = cell * 8;
    final im = img.Image(width: size, height: size);
    for (var y = 0; y < size; y++) {
      final sy = by0 + (y * bh) ~/ size;
      if (sy >= _imgH) continue;
      for (var x = 0; x < size; x++) {
        final sx = bx0 + (x * bw) ~/ size;
        if (sx >= _imgW) continue;
        final o = (sy * _imgW + sx) * 3;
        im.setPixelRgb(x, y, bytes[o], bytes[o + 1], bytes[o + 2]);
      }
    }

    // 网格线
    final lineColor = img.ColorRgb8(0, 0, 0);
    for (var i = 0; i <= 8; i++) {
      final p = i * cell;
      img.drawLine(im, x1: p, y1: 0, x2: p, y2: size - 1, color: lineColor, thickness: 2);
      img.drawLine(im, x1: 0, y1: p, x2: size - 1, y2: p, color: lineColor, thickness: 2);
    }

    // 识别字母标注（grid 为 rank8 top）
    final font = img.arial24;
    for (var r = 0; r < 8; r++) {
      for (var c = 0; c < 8; c++) {
        final code = result.grid[r][c];
        if (code == null || code.length < 2) continue;
        final label = code.substring(1).toUpperCase();
        final isWhite = code.startsWith('w');
        img.fillRect(
          im,
          x1: c * cell,
          y1: r * cell,
          x2: c * cell + cell - 1,
          y2: r * cell + cell - 1,
          color: img.ColorRgba8(0, 0, 0, 70),
        );
        final tw = _textWidth(font, label);
        img.drawString(
          im,
          label,
          font: font,
          x: c * cell + (cell - tw) ~/ 2,
          y: r * cell + (cell - font.lineHeight) ~/ 2,
          color: isWhite ? img.ColorRgb8(255, 255, 255) : img.ColorRgb8(20, 20, 20),
        );
      }
    }

    // 按朝向 180° 旋转
    final out = _orientation == Side.white ? im : img.copyRotate(im, angle: 180);
    return Uint8List.fromList(img.encodePng(out));
  }

  PieceSet _themeToPieceSet(String? theme) {
    if (theme == null) return PieceSet.cburnett;
    for (final ps in PieceSet.values) {
      if (ps.name == theme) return ps;
    }
    return PieceSet.cburnett;
  }

  Future<void> _openSettings() async {
    await Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => SettingsScreen(settings: _settings)),
    );
    _settings = await AppSettings.load();
    if (_result != null && _result!.fen != null) {
      // 设置变化后自动重新识别
      await _recognize();
    }
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(SnackBar(content: Text(msg), duration: const Duration(seconds: 2)));
  }

  // ---------------- UI ----------------
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('棋盘 FEN 识别', style: TextStyle(fontSize: 17)),
        actions: [
          IconButton(
            tooltip: '识别日志',
            icon: const Icon(Icons.article_outlined),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => LogScreen(initialLog: _diag)),
            ),
          ),
          IconButton(
            tooltip: '关于',
            icon: const Icon(Icons.info_outline),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => AboutScreen(version: _version, buildNumber: _build),
              ),
            ),
          ),
          IconButton(
            tooltip: '设置',
            icon: const Icon(Icons.settings_outlined),
            onPressed: _openSettings,
          ),
        ],
      ),
      body: SafeArea(
        child: _imageBytes == null ? _buildWelcome() : _buildResult(),
      ),
    );
  }

  Widget _buildWelcome() {
    final scheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.grid_on, size: 72, color: scheme.primary),
            const SizedBox(height: 12),
            Text('选择棋盘截图，离线识别为 FEN',
                style: TextStyle(fontSize: 16, color: scheme.onSurfaceVariant)),
            const SizedBox(height: 28),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: () => _pickImage(ImageSource.gallery),
                icon: const Icon(Icons.photo_library_outlined),
                label: const Text('从相册选择'),
                style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () => _pickImage(ImageSource.camera),
                icon: const Icon(Icons.photo_camera_outlined),
                label: const Text('拍摄棋盘'),
                style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
              ),
            ),
            const SizedBox(height: 8),
            Text('v$_version (build $_build)', style: TextStyle(fontSize: 12, color: scheme.outline)),
          ],
        ),
      ),
    );
  }

  Widget _buildResult() {
    final result = _result;
    final fen = _displayFen;
    final scheme = Theme.of(context).colorScheme;
    final boardSize = MediaQuery.of(context).size.width - 32;

    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            child: Column(
              children: [
                const SizedBox(height: 12),
                if (result == null && _busy)
                  const Padding(padding: EdgeInsets.all(40), child: CircularProgressIndicator())
                else if (result == null)
                  _buildPickBar()
                else if (result.error != null)
                  Column(
                    children: [
                      const SizedBox(height: 40),
                      Icon(Icons.error_outline, size: 56, color: scheme.error),
                      const SizedBox(height: 12),
                      Text(result.error!, style: TextStyle(color: scheme.error, fontSize: 15)),
                      const SizedBox(height: 16),
                      _buildPickBar(),
                    ],
                  )
                else ...[
                  // 棋盘预览
                  Card(
                    elevation: 0,
                    color: scheme.surfaceContainerHighest,
                    clipBehavior: Clip.antiAlias,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                    child: Stack(
                      children: [
                        if (_boardPreviewPng != null)
                          Image.memory(
                            _boardPreviewPng!,
                            width: boardSize,
                            height: boardSize,
                            fit: BoxFit.fill,
                            gaplessPlayback: true,
                          )
                        else
                          StaticChessboard(
                            size: boardSize,
                            fen: fen!,
                            orientation: _orientation,
                            settings: StaticChessboardSettings(
                              pieceAssets: _themeToPieceSet(_settings.theme).assets,
                              animationDuration: Duration.zero,
                            ),
                          ),
                        Positioned(
                          top: 8,
                          right: 8,
                          child: IconButton.filledTonal(
                            tooltip: '翻转棋盘',
                            iconSize: 18,
                            constraints: const BoxConstraints.tightFor(width: 36, height: 36),
                            icon: const Icon(Icons.flip),
                            onPressed: () => setState(() {
                              _orientation = _orientation.opposite;
                              _boardPreviewPng = _buildBoardPreview();
                            }),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),
                  // FEN
                  Container(
                    margin: const EdgeInsets.symmetric(horizontal: 16),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: scheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Row(
                      children: [
                        Expanded(
                          child: SelectableText(
                            fen!,
                            style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
                          ),
                        ),
                        IconButton(
                          tooltip: '复制 FEN',
                          icon: const Icon(Icons.copy, size: 20),
                          onPressed: () {
                            Clipboard.setData(ClipboardData(text: fen));
                            _toast('已复制 FEN');
                          },
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text('识别耗时结果 | 主题: ${_settings.theme ?? '自动'} | 模式: ${_modeLabel(_settings.mode)}',
                      style: TextStyle(fontSize: 11, color: scheme.outline)),
                  const SizedBox(height: 4),
                ],
              ],
            ),
          ),
        ),
        // 底部操作栏
        if (result != null && result.error == null)
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 4, 12, 10),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _openCrop,
                    icon: const Icon(Icons.crop_free, size: 18),
                    label: const Text('框选'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _openEditor,
                    icon: const Icon(Icons.edit_outlined, size: 18),
                    label: const Text('编辑'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _pickImage(ImageSource.gallery),
                    icon: const Icon(Icons.refresh, size: 18),
                    label: const Text('重选'),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildPickBar() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          OutlinedButton.icon(
            onPressed: () => _pickImage(ImageSource.gallery),
            icon: const Icon(Icons.photo_library_outlined),
            label: const Text('重新选择图片'),
          ),
        ],
      ),
    );
  }

  String _modeLabel(String mode) {
    switch (mode) {
      case 'recall': return '保守';
      case 'precision': return '严格';
      default: return '均衡';
    }
  }
}

/// 识别任务（纯数据，可跨 isolate 发送）
class RecogJob {
  final Map<String, Map<String, Uint8List>> templates;
  final Uint8List rgb;
  final int w, h;
  final BoardRect? boardRect;
  final String mode;
  final String? theme;
  final bool assumeClean;

  const RecogJob({
    required this.templates,
    required this.rgb,
    required this.w,
    required this.h,
    this.boardRect,
    required this.mode,
    this.theme,
    required this.assumeClean,
  });
}

/// 识别 worker（顶层函数，不捕获任何外层状态）
void _recognizeWorker(List<Object?> msg) {
  final reply = msg[0] as SendPort;
  final job = msg[1] as RecogJob;
  RecogResult result;
  try {
    final r = Recognizer(job.templates);
    result = r.recognize(
      job.rgb, job.w, job.h,
      boardRect: job.boardRect,
      mode: job.mode,
      theme: job.theme,
      assumeClean: job.assumeClean,
    );
  } catch (e) {
    result = RecogResult(
      error: '识别异常: $e',
      grid: List.generate(8, (_) => List.filled(8, null)),
    );
  }
  reply.send(result);
}
