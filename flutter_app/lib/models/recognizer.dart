import 'dart:typed_data';

/// 识别结果
class RecogResult {
  final String? fen;      // 完整 FEN（含 " w - - 0 1"）
  final String? error;    // 出错信息（fen 为 null 时）
  final int rot;          // 旋转次数（0-3）
  final List<List<String?>> grid; // 8x8 识别结果（rank8 top，未旋转）
  final int bx0, by0, bw, bh;     // 棋盘区域（原图坐标）

  /// 逐格诊断日志（与识别算法一致，用于排查）
  final List<String> diag;

  RecogResult({
    this.fen,
    this.error,
    this.rot = 0,
    required this.grid,
    this.bx0 = 0,
    this.by0 = 0,
    this.bw = 0,
    this.bh = 0,
    this.diag = const [],
  });
}

/// 手动框选区域（像素，原图坐标）
class BoardRect {
  final int x, y, w, h;
  const BoardRect(this.x, this.y, this.w, this.h);
}

/// 纯 Dart 棋盘截图 → FEN 识别器。
/// 算法与 PC 版 scan.py / 安卓 Kotlin 版严格一致：
/// 固定棋盘双色前景提取 → 形态学 → 最大连通域 → 亮度判色 → 多套件模板 IoU → 泛化箭头剔除。
/// 不依赖 OpenCV，全部像素操作手写实现。
class Recognizer {
  // lichess 默认棋盘色 (RGB 顺序)
  static const double lightR = 239, lightG = 216, lightB = 182;
  static const double darkR = 180, darkG = 137, darkB = 97;
  static const double palTol = 34.0;
  static const double palTolSq = palTol * palTol;
  static const int can = 64;
  static const List<String> pieces = ['K', 'Q', 'R', 'B', 'N', 'P'];

  // 识别档位: (best_iou 阈值, frac 面积阈值)
  static const modeTh = {
    'standard': (0.85, 0.22),
    'recall': (0.81, 0.18),
    'precision': (0.90, 0.26),
  };

  /// 模板: set 名 -> (color+piece -> 64x64 二值剪影)
  final Map<String, Map<String, Uint8List>> templates;

  /// 诊断日志缓冲（每次 recognize 清空）
  final List<String> diag = [];

  Recognizer(this.templates);

  // ---------------- 主入口 ----------------
  /// [rgb] 平面 RGB 字节数组（w*h*3），[w] [h] 为原图宽高。
  /// [boardRect] 非 null 时严格按框选区域识别（绝不外扩）。
  RecogResult recognize(
    Uint8List rgb,
    int w,
    int h, {
    BoardRect? boardRect,
    String mode = 'standard',
    String? theme,
    bool assumeClean = false,
  }) {
    diag.clear();
    List<int>? bbox;
    if (boardRect != null) {
      bbox = [boardRect.x, boardRect.y, boardRect.x + boardRect.w, boardRect.y + boardRect.h];
    } else {
      bbox = locateBoard(rgb, w, h);
      if (bbox == null) {
        return RecogResult(error: '定位不到棋盘', grid: List.generate(8, (_) => List.filled(8, null)));
      }
    }
    final bx0 = bbox[0].clamp(0, w - 1);
    final by0 = bbox[1].clamp(0, h - 1);
    final bx1 = bbox[2].clamp(bx0 + 1, w);
    final by1 = bbox[3].clamp(by0 + 1, h);
    final bw = bx1 - bx0, bh = by1 - by0;
    if (bw < 8 || bh < 8) {
      return RecogResult(error: '棋盘区域过小', grid: List.generate(8, (_) => List.filled(8, null)));
    }

    final cellW = bw ~/ 8, cellH = bh ~/ 8;
    if (cellW < 4 || cellH < 4) {
      return RecogResult(error: '棋盘区域过小', grid: List.generate(8, (_) => List.filled(8, null)));
    }

    diag.add('board=($bx0,$by0)-($bx1,$by1) size=${bw}x${bh} cell=${cellW}x${cellH} mode=$mode theme=${theme ?? 'auto'}');

    final grid = List.generate(8, (_) => List<String?>.filled(8, null));
    for (var r = 0; r < 8; r++) {
      for (var c = 0; c < 8; c++) {
        grid[r][c] = _classifyCell(rgb, w, h, bx0 + c * cellW, by0 + r * cellH, cellW, cellH,
            mode: mode, theme: theme, assumeClean: assumeClean);
      }
    }

    final (fen, rot) = bestOrientation(grid);
    return RecogResult(fen: '$fen w - - 0 1', rot: rot, grid: grid,
        bx0: bx0, by0: by0, bw: bw, bh: bh, diag: List.unmodifiable(diag));
  }

  // ---------------- 棋盘定位 ----------------
  /// 返回 [x0, y0, x1, y1] 或 null。内部降采样 1/4 加速。
  /// 行/列投影各做 1D 闭运算填谷：棋子行会把棋盘色占比压低成"谷"，
  /// 2D 形态学核不够大填不上，1D close 在投影序列上直接填平，等价全分辨率 2D close 的效果。
  List<int>? locateBoard(Uint8List rgb, int w, int h) {
    final sw = w ~/ 4, sh = h ~/ 4;
    if (sw < 8 || sh < 8) return null;
    // 降采样：4x4 块 or 聚合（块内任一像素接近棋盘色 → 1）。
    // 单点取样会系统性丢失棋盘色像素（抗锯齿/压缩），导致行投影偏低切断棋盘。
    final small = Uint8List(sw * sh);
    for (var y = 0; y < sh; y++) {
      final dy = y * sw;
      for (var x = 0; x < sw; x++) {
        var hit = 0;
        outer:
        for (var yy = 0; yy < 4; yy++) {
          final sy = y * 4 + yy;
          for (var xx = 0; xx < 4; xx++) {
            final sx = x * 4 + xx;
            final idx = (sy * w + sx) * 3;
            final dr = rgb[idx].toDouble(), dg = rgb[idx + 1].toDouble(), db = rgb[idx + 2].toDouble();
            final dL = (dr - lightR) * (dr - lightR) + (dg - lightG) * (dg - lightG) + (db - lightB) * (db - lightB);
            final dD = (dr - darkR) * (dr - darkR) + (dg - darkG) * (dg - darkG) + (db - darkB) * (db - darkB);
            if (dL < palTolSq || dD < palTolSq) { hit = 1; break outer; }
          }
        }
        small[dy + x] = hit;
      }
    }

    // 行投影 + 1D close 17（填棋子行谷，≈全分辨率 35px 谷）
    final rowProj = Float64List(sh);
    for (var y = 0; y < sh; y++) {
      var cnt = 0;
      final o = y * sw;
      for (var x = 0; x < sw; x++) cnt += small[o + x];
      rowProj[y] = cnt / sw;
    }
    final spanY = _maxSpan(_close1d(rowProj, 17), 0.4);
    if (spanY == null) return null;
    final y0s = spanY.$1, y1s = spanY.$2;
    if ((y1s - y0s) < 0.2 * sh) return null;

    // 列投影（在行带内）+ 1D close
    final colProj = Float64List(sw);
    for (var x = 0; x < sw; x++) {
      var cnt = 0;
      for (var y = y0s; y < y1s; y++) cnt += small[y * sw + x];
      colProj[x] = cnt / (y1s - y0s);
    }
    final spanX = _maxSpan(_close1d(colProj, 9), 0.35);
    if (spanX == null) return null;
    final x0s = spanX.$1, x1s = spanX.$2;
    if ((x1s - x0s) < 0.2 * sw) return null;

    // 正方形：行带高度为边长，水平居中
    final sideS = y1s - y0s;
    final cx = (x0s + x1s) ~/ 2;
    var bx0s = cx - sideS ~/ 2, by0s = y0s;
    if (bx0s < 0) bx0s = 0;
    var bx1s = bx0s + sideS, by1s = by0s + sideS;
    if (bx1s > sw) { bx1s = sw; bx0s = bx1s - sideS; }
    if (by1s > sh) { by1s = sh; by0s = by1s - sideS; }
    // 水平被裁剪时回落以列投影左缘对齐（lichess 截图棋盘常紧贴左缘）
    if (bx1s - bx0s < sideS) {
      bx0s = x0s.clamp(0, sw - 1);
      bx1s = bx0s + sideS;
      if (bx1s > sw) bx1s = sw;
      by1s = by0s + sideS;
      if (by1s > sh) by1s = sh;
    }

    return [bx0s * 4, by0s * 4, bx1s * 4, by1s * 4];
  }

  /// 1D 闭运算：先膨胀（窗口 max）再腐蚀（窗口 min），填投影序列上的谷。
  Float64List _close1d(Float64List src, int size) {
    final half = size ~/ 2;
    final n = src.length;
    final dil = Float64List(n);
    for (var i = 0; i < n; i++) {
      var m = 0.0;
      for (var k = -half; k <= half; k++) {
        final j = i + k;
        if (j < 0 || j >= n) continue;
        if (src[j] > m) m = src[j];
      }
      dil[i] = m;
    }
    final er = Float64List(n);
    for (var i = 0; i < n; i++) {
      var m = 1.0;
      for (var k = -half; k <= half; k++) {
        final j = i + k;
        if (j < 0 || j >= n) continue;
        if (dil[j] < m) m = dil[j];
      }
      er[i] = m;
    }
    return er;
  }

  /// 返回 (start, endExclusive)
  (int, int)? _maxSpan(Float64List profile, double thr) {
    final n = profile.length;
    var bestS = -1, bestE = -1, curS = -1;
    for (var i = 0; i < n; i++) {
      if (profile[i] > thr) {
        if (curS < 0) curS = i;
        if (i - curS > bestE - bestS) { bestS = curS; bestE = i; }
      } else {
        curS = -1;
      }
    }
    if (bestS < 0) return null;
    return (bestS, bestE + 1);
  }

  // ---------------- 单格分类 ----------------
  String? _classifyCell(Uint8List rgb, int w, int h, int x0, int y0, int cw, int ch,
      {required String mode, String? theme, required bool assumeClean}) {
    final (iouTh, fracTh) = modeTh[mode] ?? modeTh['standard']!;

    // 1. 走子高亮 + 引擎标注徽章掩膜（HSV）
    final omask = _overlayMask(rgb, w, h, x0, y0, cw, ch);

    // 2. 前景 = 与两种棋盘底色距离都大的像素
    final fg = Uint8List(cw * ch);
    for (var y = 0; y < ch; y++) {
      var o = (y0 + y) * w + x0;
      final fo = y * cw;
      for (var x = 0; x < cw; x++) {
        final idx = o * 3;
        final dr = rgb[idx], dg = rgb[idx + 1], db = rgb[idx + 2];
        final dL = (dr - lightR) * (dr - lightR) + (dg - lightG) * (dg - lightG) + (db - lightB) * (db - lightB);
        final dD = (dr - darkR) * (dr - darkR) + (dg - darkG) * (dg - darkG) + (db - darkB) * (db - darkB);
        var v = (dL > palTolSq && dD > palTolSq) ? 1 : 0;
        if (omask[fo + x] == 1) v = 0; // 高亮/徽章不是棋子
        fg[fo + x] = v;
        o++;
      }
    }

    // 3. 形态学 open 3x3 + close 5x5
    var f = _morph(fg, cw, ch, 3, close: false);
    f = _morph(f, cw, ch, 5, close: true);

    // 4. 只保留最大连通域
    final largest = _largestComponent(f, cw, ch);

    // 5. 面积比例
    var cnt = 0;
    for (var i = 0; i < largest.length; i++) cnt += largest[i];
    final frac = cnt / (cw * ch);
    if (frac < 0.03) {
      diag.add('frac=${frac.toStringAsFixed(4)} ->EMPTY');
      return null;
    }

    // 6. 判色：剪影像素亮度 >200 占比 >0.33 = 白
    var brightCnt = 0;
    for (var y = 0; y < ch; y++) {
      final fo = y * cw;
      var o = (y0 + y) * w + x0;
      for (var x = 0; x < cw; x++) {
        if (largest[fo + x] == 1) {
          final idx = o * 3;
          final lum = (rgb[idx] + rgb[idx + 1] + rgb[idx + 2]) / 3.0;
          if (lum > 200) brightCnt++;
        }
        o++;
      }
    }
    final color = (brightCnt / cnt) > 0.33 ? 'w' : 'b';

    // 7. bbox crop + resize 64x64 + IoU 模板匹配
    var minX = cw, minY = ch, maxX = -1, maxY = -1;
    for (var y = 0; y < ch; y++) {
      final fo = y * cw;
      for (var x = 0; x < cw; x++) {
        if (largest[fo + x] == 1) {
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
      }
    }
    if (maxX < 0) return null;
    final cm = _resizeBinary(largest, cw, ch, minX, minY, maxX - minX + 1, maxY - minY + 1, can, can);

    var bestIou = -1.0;
    String? bestPiece;
    final sets = (theme != null && templates.containsKey(theme))
        ? [templates[theme]!]
        : templates.values.toList();
    for (final tset in sets) {
      for (final piece in pieces) {
        final tm = tset['$color$piece'];
        if (tm == null) continue;
        var inter = 0, union = 0;
        for (var i = 0; i < can * can; i++) {
          final a = cm[i], b = tm[i];
          if (a == 1 && b == 1) inter++;
          if (a == 1 || b == 1) union++;
        }
        final iou = union == 0 ? 0.0 : inter / union;
        if (iou > bestIou) { bestIou = iou; bestPiece = piece; }
      }
    }

    // 8. 泛化箭头剔除
    if (!assumeClean && bestIou < iouTh && frac <= fracTh) {
      diag.add('->ARROW_EMPTY(iou=${bestIou.toStringAsFixed(2)},frac=${frac.toStringAsFixed(2)})');
      return null;
    }
    diag.add('frac=${frac.toStringAsFixed(4)} ->${color}${bestPiece ?? '?'}(${bestIou.toStringAsFixed(2)})');
    return bestPiece != null ? color + bestPiece : null;
  }

  /// HSV 掩膜：引擎标注徽章（高饱和+高亮）+ 走子高亮（黄/绿/红）
  Uint8List _overlayMask(Uint8List rgb, int w, int h, int x0, int y0, int cw, int ch) {
    final out = Uint8List(cw * ch);
    for (var y = 0; y < ch; y++) {
      final fo = y * cw;
      var o = (y0 + y) * w + x0;
      for (var x = 0; x < cw; x++) {
        final idx = o * 3;
        final r = rgb[idx] / 255.0, g = rgb[idx + 1] / 255.0, b = rgb[idx + 2] / 255.0;
        final mx = r > g ? (r > b ? r : b) : (g > b ? g : b);
        final mn = r < g ? (r < b ? r : b) : (g < b ? g : b);
        final delta = mx - mn;
        final v = mx;
        double hh = 0;
        if (delta > 0) {
          if (mx == r) { hh = 60 * (((g - b) / delta) % 6); }
          else if (mx == g) { hh = 60 * ((b - r) / delta + 2); }
          else { hh = 60 * ((r - g) / delta + 4); }
          if (hh < 0) hh += 360;
        }
        final s = mx == 0 ? 0.0 : delta / mx;
        // badge: s>150/255≈0.588, v>190/255≈0.745
        var hit = (s > 0.588 && v > 0.745) ? 1 : 0;
        // highlight 黄绿: OpenCV h(0-179) 15-85 → 角度 30-170°
        if (hit == 0 && hh >= 30 && hh <= 170 && s > 0.157 && v > 0.235) hit = 1;
        // red: OpenCV h<=10 或 h>=170 → 角度 <=20° 或 >=340°
        if (hit == 0 && (hh <= 20 || hh >= 340) && s > 0.157 && v > 0.235) hit = 1;
        out[fo + x] = hit;
        o++;
      }
    }
    return out;
  }

  /// 二值形态学（方形 kernel，size 奇数）。close=true 先膨胀后腐蚀，否则先腐蚀后膨胀。
  Uint8List _morph(Uint8List src, int w, int h, int size, {required bool close}) {
    final half = size ~/ 2;
    Uint8List dilate(Uint8List input) {
      final out = Uint8List(w * h);
      for (var y = 0; y < h; y++) {
        final o = y * w;
        for (var x = 0; x < w; x++) {
          var hit = 0;
          outer:
          for (var ky = -half; ky <= half; ky++) {
            final yy = y + ky;
            if (yy < 0 || yy >= h) continue;
            final io = yy * w;
            for (var kx = -half; kx <= half; kx++) {
              final xx = x + kx;
              if (xx < 0 || xx >= w) continue;
              if (input[io + xx] == 1) { hit = 1; break outer; }
            }
          }
          out[o + x] = hit;
        }
      }
      return out;
    }

    Uint8List erode(Uint8List input) {
      final out = Uint8List(w * h);
      for (var y = 0; y < h; y++) {
        final o = y * w;
        for (var x = 0; x < w; x++) {
          var all = 1;
          outer:
          for (var ky = -half; ky <= half; ky++) {
            final yy = y + ky;
            if (yy < 0 || yy >= h) { all = 0; break; }
            final io = yy * w;
            for (var kx = -half; kx <= half; kx++) {
              final xx = x + kx;
              if (xx < 0 || xx >= w) { all = 0; break outer; }
              if (input[io + xx] != 1) { all = 0; break outer; }
            }
          }
          out[o + x] = all;
        }
      }
      return out;
    }

    return close ? erode(dilate(src)) : dilate(erode(src));
  }

  /// 最大连通域（8 邻域 BFS）
  Uint8List _largestComponent(Uint8List src, int w, int h) {
    final label = Int32List(w * h);
    final area = <int>[];
    var comps = 0;
    final stack = <int>[];
    for (var i = 0; i < w * h; i++) {
      if (src[i] == 1 && label[i] == 0) {
        comps++;
        var a = 0;
        stack.clear();
        stack.add(i);
        label[i] = comps;
        while (stack.isNotEmpty) {
          final p = stack.removeLast();
          a++;
          final x = p % w, y = p ~/ w;
          for (var dy = -1; dy <= 1; dy++) {
            final yy = y + dy;
            if (yy < 0 || yy >= h) continue;
            for (var dx = -1; dx <= 1; dx++) {
              if (dx == 0 && dy == 0) continue;
              final xx = x + dx;
              if (xx < 0 || xx >= w) continue;
              final q = yy * w + xx;
              if (src[q] == 1 && label[q] == 0) {
                label[q] = comps;
                stack.add(q);
              }
            }
          }
        }
        area.add(a);
      }
    }
    if (comps == 0) return Uint8List(w * h);
    var bestIdx = 0, bestArea = 0;
    for (var i = 0; i < comps; i++) {
      if (area[i] > bestArea) { bestArea = area[i]; bestIdx = i + 1; }
    }
    final out = Uint8List(w * h);
    for (var i = 0; i < w * h; i++) {
      if (label[i] == bestIdx) out[i] = 1;
    }
    return out;
  }

  /// bbox 裁剪后缩放到 can x can 的二值图
  /// 区域平均缩放 + 阈值 0.5（等价 OpenCV INTER_AREA + THRESH_BINARY）。
  /// 点采样会丢失兵杆/王冠等细特征，导致跨套件 IoU 翻转误判。
  Uint8List _resizeBinary(Uint8List src, int sw, int sh, int bx, int by, int bw, int bh, int dw, int dh) {
    final out = Uint8List(dw * dh);
    for (var y = 0; y < dh; y++) {
      final y0 = by + (y * bh) ~/ dh;
      final y1 = by + ((y + 1) * bh) ~/ dh;
      final o = y * dw;
      for (var x = 0; x < dw; x++) {
        final x0 = bx + (x * bw) ~/ dw;
        final x1 = bx + ((x + 1) * bw) ~/ dw;
        var cnt = 0, tot = 0;
        for (var sy = y0; sy < y1; sy++) {
          final so = sy * sw;
          for (var sx = x0; sx < x1; sx++) {
            tot++;
            if (src[so + sx] == 1) cnt++;
          }
        }
        out[o + x] = (cnt * 2 > tot) ? 1 : 0; // 占比 > 0.5
      }
    }
    return out;
  }

  // ---------------- FEN + 旋转 ----------------
  String gridToFen(List<List<String?>> grid) {
    final ranks = <String>[];
    for (var r = 0; r < 8; r++) {
      final sb = StringBuffer();
      var e = 0;
      for (var c = 0; c < 8; c++) {
        final pc = grid[r][c];
        if (pc == null) {
          e++;
        } else {
          if (e > 0) { sb.write(e); e = 0; }
          sb.write(pc[0] == 'w' ? pc[1].toUpperCase() : pc[1].toLowerCase());
        }
      }
      if (e > 0) sb.write(e);
      ranks.add(sb.toString());
    }
    return ranks.join('/');
  }

  (String, int) bestOrientation(List<List<String?>> grid) {
    var bestScore = -1 << 30;
    var bestFen = gridToFen(grid);
    var bestRot = 0;
    for (var rot = 0; rot < 4; rot++) {
      final g = rotGrid(grid, rot);
      final f = gridToFen(g);
      var wb = 0, wt = 0, bb = 0, bt = 0;
      for (var c = 0; c < 8; c++) {
        for (final r in [6, 7]) {
          final pc = g[r][c];
          if (pc != null) { if (pc[0] == 'w') wb++; else bb++; }
        }
        for (final r in [0, 1]) {
          final pc = g[r][c];
          if (pc != null) { if (pc[0] == 'w') wt++; else bt++; }
        }
      }
      var score = (wb + bt) - (wt + bb);
      outer:
      for (var r = 4; r <= 7; r++) {
        for (var c = 0; c < 8; c++) {
          if (g[r][c] == 'wK') { score += 2; break outer; }
        }
      }
      if (score > bestScore) { bestScore = score; bestFen = f; bestRot = rot; }
    }
    return (bestFen, bestRot);
  }

  List<List<String?>> rotGrid(List<List<String?>> grid, int rot) {
    var g = List.generate(8, (r) => List<String?>.from(grid[r]));
    for (var k = 0; k < rot; k++) {
      final ng = List.generate(8, (_) => List<String?>.filled(8, null));
      for (var r = 0; r < 8; r++) {
        for (var c = 0; c < 8; c++) ng[c][7 - r] = g[r][c];
      }
      g = ng;
    }
    return g;
  }
}
