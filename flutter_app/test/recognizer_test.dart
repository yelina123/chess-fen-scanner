import 'dart:io';
import 'dart:typed_data';

import 'package:image/image.dart' as img;
import 'package:flutter_test/flutter_test.dart';

import 'package:chess_fen_app/models/recognizer.dart';

/// 文件系统版模板加载（测试用，不走 asset bundle）
Future<Map<String, Map<String, Uint8List>>> loadTemplatesFromFs(String root) async {
  final pieces = ['K', 'Q', 'R', 'B', 'N', 'P'];
  final result = <String, Map<String, Uint8List>>{};
  for (final set in Directory('$root').listSync().whereType<Directory>()) {
    final name = set.path.split(Platform.pathSeparator).last;
    final stpl = <String, Uint8List>{};
    for (final color in ['w', 'b']) {
      for (final piece in pieces) {
        final f = File('${set.path}/png/${color}${piece}_90.png');
        if (!f.existsSync()) continue;
        final bytes = f.readAsBytesSync();
        final im = img.decodeImage(bytes);
        if (im == null) continue;
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
        final bin = Uint8List(64 * 64);
        for (var y = 0; y < 64; y++) {
          final sy = minY + (y * bh) ~/ 64;
          final o = y * 64;
          for (var x = 0; x < 64; x++) {
            final sx = minX + (x * bw) ~/ 64;
            bin[o + x] = im.getPixel(sx, sy).a.toInt() > 128 ? 1 : 0;
          }
        }
        stpl['$color$piece'] = bin;
      }
    }
    if (stpl.length == 12) result[name] = stpl;
  }
  return result;
}

/// 读取 jpg → RGB 平面数组
(Uint8List, int, int) loadRgb(String path) {
  final bytes = File(path).readAsBytesSync();
  final im = img.decodeImage(bytes)!;
  final rgb = Uint8List(im.width * im.height * 3);
  var o = 0;
  for (var y = 0; y < im.height; y++) {
    for (var x = 0; x < im.width; x++) {
      final p = im.getPixel(x, y);
      rgb[o++] = p.r.toInt();
      rgb[o++] = p.g.toInt();
      rgb[o++] = p.b.toInt();
    }
  }
  return (rgb, im.width, im.height);
}

void main() {
  final root = '/home/user/Doubao/chats/38439971696524290/chess-fen-scanner';
  final tplRoot = '$root/assets/pieces';
  final testDir = '$root/test_supplement';

  test('模板加载', () async {
    final tpl = await loadTemplatesFromFs(tplRoot);
    expect(tpl.length, 38);
    expect(tpl['cburnett']!.length, 12);
  });

  final cases = [
    ('a.jpg', 'rnbqkbnr/pppp1ppp/8/4p3/3P4/8/PPP1PPPP/RNBQKBNR'),
    ('b.jpg', 'r1bqkbnr/pppp1ppp/2n5/4P3/8/8/PPP1PPKP/RNBQKBNR'),
    ('c.jpg', 'r1bqk1nr/ppp2ppp/2n5/2bpP3/5B2/5N2/PPP1PPPP/RN1QKB1R'),
  ];

  for (final (file, expected) in cases) {
    test('识别 $file', () async {
      final tpl = await loadTemplatesFromFs(tplRoot);
      final (rgb, w, h) = loadRgb('$testDir/$file');
      final r = Recognizer(tpl);
      final result = r.recognize(rgb, w, h);
      expect(result.error, isNull);
      expect(result.fen!.split(' ').first, expected,
          reason: '与 Python 版 scan.py 结果一致');
    });
  }

  test('手动框选严格不扩展', () async {
    final tpl = await loadTemplatesFromFs(tplRoot);
    final (rgb, w, h) = loadRgb('$testDir/a.jpg');
    final r = Recognizer(tpl);
    // 整图识别（自动定位）
    final auto = r.recognize(rgb, w, h);
    // 用自动定位结果作为框选区域再识别，结果应一致
    final rect = BoardRect(auto.bx0, auto.by0, auto.bw, auto.bh);
    final manual = r.recognize(rgb, w, h, boardRect: rect);
    expect(manual.fen, auto.fen);
    // 更小区域（只框棋盘左半边）应严格返回框内结果，不会扩展
    final half = BoardRect(auto.bx0, auto.by0, auto.bw ~/ 2, auto.bh);
    final small = r.recognize(rgb, w, h, boardRect: half);
    expect(small.bw, auto.bw ~/ 2);
    expect(small.fen, isNotNull);
  });

  test('assumeClean 开关可用', () async {
    final tpl = await loadTemplatesFromFs(tplRoot);
    final (rgb, w, h) = loadRgb('$testDir/a.jpg');
    final r = Recognizer(tpl);
    final clean = r.recognize(rgb, w, h, assumeClean: true);
    final normal = r.recognize(rgb, w, h, assumeClean: false);
    // 两者都须产出合法 FEN 摆放段（8 排，每排合计 8）
    for (final res in [clean, normal]) {
      expect(res.error, isNull);
      final placement = res.fen!.split(' ').first;
      final ranks = placement.split('/');
      expect(ranks.length, 8);
      for (final rank in ranks) {
        var n = 0;
        for (final ch in rank.split('')) {
          if (int.tryParse(ch) != null) {
            n += int.parse(ch);
          } else {
            n += 1;
          }
        }
        expect(n, 8);
      }
    }
  });
}
