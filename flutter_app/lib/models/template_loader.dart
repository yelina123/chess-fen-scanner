import 'package:flutter/services.dart';
import 'package:image/image.dart' as img;

/// 从 assets 加载全部棋子剪影模板。
/// 每套 12 个 PNG（6 兵种 × 黑白），提取 alpha 通道 → bbox 裁剪 → 缩放到 64x64 二值。
class TemplateLoader {
  static const _root = 'assets/pieces';
  static const _pieces = ['K', 'Q', 'R', 'B', 'N', 'P'];
  static const _can = 64;

  static Future<List<String>> listSets() async {
    try {
      final data = await rootBundle.loadString('$_root/sets.txt');
      return data.split('\n').map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
    } catch (_) {
      return const ['cburnett'];
    }
  }

  /// 加载全部套件（或仅 [only] 指定套件）
  static Future<Map<String, Map<String, Uint8List>>> load({String? only}) async {
    final sets = only != null ? [only] : await listSets();
    final result = <String, Map<String, Uint8List>>{};
    for (final set in sets) {
      final tpl = await _loadSet(set);
      if (tpl.length == 12) result[set] = tpl;
    }
    return result;
  }

  static Future<Map<String, Uint8List>> _loadSet(String set) async {
    final stpl = <String, Uint8List>{};
    for (final color in ['w', 'b']) {
      for (final piece in _pieces) {
        try {
          final name = '${color}${piece}_90.png';
          final bytes = await rootBundle.load('$_root/$set/png/$name');
          final im = img.decodeImage(bytes.buffer.asUint8List());
          if (im == null) continue;
          // 提取 alpha 通道 (>128) 并 bbox 裁剪
          final w = im.width, h = im.height;
          var minX = w, minY = h, maxX = -1, maxY = -1;
          for (var y = 0; y < h; y++) {
            for (var x = 0; x < w; x++) {
              if (im.getPixel(x, y).a.toInt() > 128) {
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;
              }
            }
          }
          if (maxX < 0) continue;
          final bw = maxX - minX + 1, bh = maxY - minY + 1;
          final bin = Uint8List(_can * _can);
          for (var y = 0; y < _can; y++) {
            final sy = minY + (y * bh) ~/ _can;
            final o = y * _can;
            for (var x = 0; x < _can; x++) {
              final sx = minX + (x * bw) ~/ _can;
              bin[o + x] = im.getPixel(sx, sy).a.toInt() > 128 ? 1 : 0;
            }
          }
          stpl['$color$piece'] = bin;
        } catch (_) {
          // 单图缺失跳过
        }
      }
    }
    return stpl;
  }
}
