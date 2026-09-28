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
import 'crop_screen.dart';
import 'fen_editor_screen.dart';
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

  Map<String, Map<String, Uint8List>> _templates = {};

  static const _version = '2.0.0';
  static const _build = '23';

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    _settings = await AppSettings.load();
    // 后台加载模板（全部套件）
    final tpl = await Isolate.run(() => TemplateLoader.load());
    if (mounted) {
      setState(() => _templates = tpl);
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
      final result = await Isolate.run(() {
        final r = Recognizer(templates);
        return r.recognize(bytes, w, h,
            boardRect: boardRect, mode: mode, theme: theme, assumeClean: assumeClean);
      });
      if (!mounted) return;
      setState(() {
        _busy = false;
        _result = result;
        _displayFen = result.fen;
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
      MaterialPageRoute(builder: (_) => FenEditorScreen(initialFen: fen, pieceSet: ps)),
    );
    if (edited != null && edited.isNotEmpty) {
      setState(() => _displayFen = edited);
      _toast('已更新 FEN');
    }
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
                            onPressed: () => setState(() => _orientation = _orientation.opposite),
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
                            fen,
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
