import 'dart:typed_data';
import 'package:flutter/material.dart';

/// 手动框选棋盘界面。
/// 显示原图，拖拽 8x8 网格框选棋盘区域；支持整体移动与四角/边缘微调。
/// 确认后返回框选区域的原图像素坐标，识别严格按此区域裁切，绝不扩展。
class CropScreen extends StatefulWidget {
  final Uint8List imageBytes;
  final int imageWidth;
  final int imageHeight;
  final BoardRectView? initialRect;
  const CropScreen({
    super.key,
    required this.imageBytes,
    required this.imageWidth,
    required this.imageHeight,
    this.initialRect,
  });

  @override
  State<CropScreen> createState() => _CropScreenState();
}

/// 归一化(0-1)的棋盘框，便于在不同尺寸间转换
class BoardRectView {
  double left, top, right, bottom;
  BoardRectView(this.left, this.top, this.right, this.bottom);
}

class _CropScreenState extends State<CropScreen> {
  late BoardRectView _rect;
  int _dragMode = 0; // 0=无 1=整体 2=右下角 3=左边 4=右边 5=上边 6=下边 7=左上 8=右上 9=左下
  double _startDx = 0, _startDy = 0;
  late BoardRectView _startRect;

  // 图片显示区域（在控件内的位置）
  double _dispLeft = 0, _dispTop = 0, _dispW = 0, _dispH = 0;

  @override
  void initState() {
    super.initState();
    final r = widget.initialRect;
    if (r != null) {
      _rect = r;
    } else {
      // 默认：整图 88% 宽的正方形居中偏上
      final side = 0.88;
      final l = (1 - side) / 2;
      _rect = BoardRectView(l, 0.06, l + side, 0.06 + side);
    }
  }

  void _layoutDisplay(Size size) {
    final iw = widget.imageWidth, ih = widget.imageHeight;
    final scale = (size.width / iw) < (size.height / ih) ? size.width / iw : size.height / ih;
    final dw = iw * scale, dh = ih * scale;
    _dispLeft = (size.width - dw) / 2;
    _dispTop = (size.height - dh) / 2;
    _dispW = dw;
    _dispH = dh;
  }

  double _px(double norm) => _dispLeft + norm * _dispW;
  double _py(double norm) => _dispTop + norm * _dispH;

  int _hitTest(double dx, double dy, double t) {
    final l = _px(_rect.left), t2 = _py(_rect.top), r = _px(_rect.right), b = _py(_rect.bottom);
    bool near(double a, double c) => (a - c).abs() < t;
    if (near(dx, l) && near(dy, t2)) return 7;
    if (near(dx, r) && near(dy, t2)) return 8;
    if (near(dx, l) && near(dy, b)) return 9;
    if (near(dx, r) && near(dy, b)) return 2;
    if (near(dx, l)) return 3;
    if (near(dx, r)) return 4;
    if (near(dy, t2)) return 5;
    if (near(dy, b)) return 6;
    return 1;
  }

  void _applyDrag(double dx, double dy) {
    final l = _startRect.left, t = _startRect.top, r = _startRect.right, b = _startRect.bottom;
    final ddx = (dx - _startDx) / _dispW;
    final ddy = (dy - _startDy) / _dispH;
    switch (_dragMode) {
      case 1:
        var nl = l + ddx, nt = t + ddy;
        final w0 = r - l, h0 = b - t;
        if (nl < 0) nl = 0;
        if (nt < 0) nt = 0;
        if (nl + w0 > 1) nl = 1 - w0;
        if (nt + h0 > 1) nt = 1 - h0;
        _rect = BoardRectView(nl, nt, nl + w0, nt + h0);
        break;
      case 2:
        _rect = BoardRectView(l, t, (r + ddx).clamp(l + 0.02, 1.0), (b + ddy).clamp(t + 0.02, 1.0));
        break;
      case 3:
        _rect = BoardRectView((l + ddx).clamp(0.0, r - 0.02), t, r, b);
        break;
      case 4:
        _rect = BoardRectView(l, t, (r + ddx).clamp(l + 0.02, 1.0), b);
        break;
      case 5:
        _rect = BoardRectView(l, (t + ddy).clamp(0.0, b - 0.02), r, b);
        break;
      case 6:
        _rect = BoardRectView(l, t, r, (b + ddy).clamp(t + 0.02, 1.0));
        break;
      case 7:
        _rect = BoardRectView((l + ddx).clamp(0.0, r - 0.02), (t + ddy).clamp(0.0, b - 0.02), r, b);
        break;
      case 8:
        _rect = BoardRectView(l, (t + ddy).clamp(0.0, b - 0.02), (r + ddx).clamp(l + 0.02, 1.0), b);
        break;
      case 9:
        _rect = BoardRectView((l + ddx).clamp(0.0, r - 0.02), t, r, (b + ddy).clamp(t + 0.02, 1.0));
        break;
    }
  }

  void _confirm() {
    // 严格按框选区域返回（不扩展），由调用方裁切识别
    Navigator.pop(context, BoardRectView(_rect.left, _rect.top, _rect.right, _rect.bottom));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('框选棋盘', style: TextStyle(fontSize: 16)),
        actions: [
          TextButton(
            onPressed: _confirm,
            child: const Text('识别', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  _layoutDisplay(Size(constraints.maxWidth, constraints.maxHeight));
                  return GestureDetector(
                    onPanStart: (d) {
                      final t = 24.0;
                      _startDx = d.localPosition.dx;
                      _startDy = d.localPosition.dy;
                      _dragMode = _hitTest(_startDx, _startDy, t);
                      _startRect = BoardRectView(_rect.left, _rect.top, _rect.right, _rect.bottom);
                    },
                    onPanUpdate: (d) {
                      if (_dragMode == 0) return;
                      setState(() => _applyDrag(d.localPosition.dx, d.localPosition.dy));
                    },
                    onPanEnd: (_) => _dragMode = 0,
                    child: Stack(
                      children: [
                        Positioned.fill(
                          child: Image.memory(
                            widget.imageBytes,
                            fit: BoxFit.contain,
                            gaplessPlayback: true,
                          ),
                        ),
                        CustomPaint(
                          size: Size.infinite,
                          painter: _CropPainter(_rect, _px, _py, _dispW, _dispH),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Column(
                children: [
                  const Text('拖动框体移动，拖动边缘/四角微调', style: TextStyle(fontSize: 12, color: Colors.grey)),
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: _confirm,
                      icon: const Icon(Icons.crop_free),
                      label: const Text('按框选区域识别'),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CropPainter extends CustomPainter {
  final BoardRectView rect;
  final double Function(double) px;
  final double Function(double) py;
  final double dispW;
  final double dispH;
  _CropPainter(this.rect, this.px, this.py, this.dispW, this.dispH);

  @override
  void paint(Canvas canvas, Size size) {
    final l = px(rect.left), t = py(rect.top), r = px(rect.right), b = py(rect.bottom);
    // 暗化框外区域
    final paint = Paint()..color = Colors.black.withOpacity(0.55);
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, t), paint);
    canvas.drawRect(Rect.fromLTWH(0, b, size.width, size.height - b), paint);
    canvas.drawRect(Rect.fromLTWH(0, t, l, b - t), paint);
    canvas.drawRect(Rect.fromLTWH(r, t, size.width - r, b - t), paint);

    // 8x8 网格
    final gridPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2
      ..color = Colors.white.withOpacity(0.85);
    final step = (b - t) / 8;
    for (var i = 0; i <= 8; i++) {
      final p = t + i * step;
      canvas.drawLine(Offset(l, p), Offset(r, p), gridPaint);
      canvas.drawLine(Offset(l + i * step, t), Offset(l + i * step, b), gridPaint);
    }

    // 边框
    final borderPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..color = Colors.lightGreenAccent;
    canvas.drawRect(Rect.fromLTWH(l, t, r - l, b - t), borderPaint);

    // 四角手柄
    final h = 16.0;
    final cornerPaint = Paint()..color = Colors.lightGreenAccent;
    for (final p in [Offset(l, t), Offset(r, t), Offset(l, b), Offset(r, b)]) {
      canvas.drawCircle(p, h / 2, cornerPaint);
    }
  }

  @override
  bool shouldRepaint(_CropPainter old) => true;
}
