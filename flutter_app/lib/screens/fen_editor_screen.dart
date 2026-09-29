import 'dart:typed_data';

import 'package:chessground/chessground.dart';
import 'package:dartchess/dartchess.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// FEN 棋盘编辑器：布局与交互复刻 Lichess 移动端棋盘编辑器。
/// - 棋盘上下各一组棋子面板（朝下颜色的面板在棋盘下方）
/// - 每组：拖拽按钮 + 6 枚棋子图形 + 删除按钮
/// - 点击棋子 → 编辑模式点击棋盘放置；拖拽棋子 → 拖到棋盘移动
/// - 底部：初始局面 / 清空棋盘 / 翻转棋盘 / 复制 / 完成
class FenEditorScreen extends StatefulWidget {
  final String initialFen;
  final PieceSet pieceSet;

  /// 截图棋盘预览（PNG），用于对照修改
  final Uint8List? boardPreview;

  const FenEditorScreen({
    super.key,
    required this.initialFen,
    this.pieceSet = PieceSet.cburnett,
    this.boardPreview,
  });

  @override
  State<FenEditorScreen> createState() => _FenEditorScreenState();
}

class _FenEditorScreenState extends State<FenEditorScreen> {
  late Pieces _pieces;
  EditorPointerMode _mode = EditorPointerMode.drag;
  Piece? _activePiece;
  Side _orientation = Side.white;
  late String _fen;

  @override
  void initState() {
    super.initState();
    final clean = widget.initialFen.split(' ').first;
    _pieces = readFen(clean);
    _fen = writeFen(_pieces);
  }

  void _syncFen() {
    setState(() => _fen = writeFen(_pieces));
  }

  // Lichess 控制器逻辑：editSquare / movePiece / discardPiece
  void _editSquare(Square square) {
    setState(() {
      final piece = _activePiece;
      if (piece != null) {
        if (_pieces[square] == piece) {
          _pieces.remove(square); // 已存在同棋子 → 删除
        } else {
          _pieces[square] = piece;
        }
      } else {
        _pieces.remove(square); // 删除模式
      }
      _syncFen();
    });
  }

  void _movePiece(Square? origin, Square dest, Piece piece) {
    setState(() {
      if (origin != null && origin != dest) _pieces.remove(origin);
      _pieces[dest] = piece;
      _syncFen();
    });
  }

  void _discardPiece(Square square) {
    setState(() {
      _pieces.remove(square);
      _syncFen();
    });
  }

  void _updateMode(EditorPointerMode mode, [Piece? piece]) {
    setState(() {
      _mode = mode;
      _activePiece = piece;
    });
  }

  void _loadFen(String fen) {
    setState(() {
      _pieces = readFen(fen.split(' ').first);
      _mode = EditorPointerMode.drag;
      _activePiece = null;
      _syncFen();
    });
  }

  void _clearBoard() {
    setState(() {
      _pieces = {};
      _syncFen();
    });
  }

  @override
  Widget build(BuildContext context) {
    final w = MediaQuery.of(context).size.width;
    final boardSize = w < 400 ? w : w * 0.94;
    return Scaffold(
      appBar: AppBar(
        title: const Text('编辑棋盘', style: TextStyle(fontSize: 16)),
        actions: [
          IconButton(
            tooltip: '粘贴 FEN',
            icon: const Icon(Icons.edit_outlined, size: 20),
            onPressed: _pasteFen,
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            children: [
              if (widget.boardPreview != null) _buildScreenshotStrip(boardSize),
              _buildPieceMenu(_orientation.opposite, boardSize),
              Center(
                child: ChessboardEditor(
                  size: boardSize,
                  pieces: _pieces,
                  orientation: _orientation,
                  pointerMode: _mode,
                  settings: ChessboardSettings(
                    pieceAssets: widget.pieceSet.assets,
                    animationDuration: Duration.zero,
                  ),
                  onEditedSquare: _editSquare,
                  onDroppedPiece: _movePiece,
                  onDiscardedPiece: _discardPiece,
                ),
              ),
              _buildPieceMenu(_orientation, boardSize),
              _buildFenBar(),
              _buildActionRow(),
            ],
          ),
        ),
      ),
    );
  }

  // ---------------- 截图棋盘对照 ----------------
  Widget _buildScreenshotStrip(double boardSize) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      child: Row(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: Image.memory(
              widget.boardPreview!,
              width: boardSize * 0.28,
              height: boardSize * 0.28,
              fit: BoxFit.cover,
              gaplessPlayback: true,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('截图棋盘', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                const SizedBox(height: 4),
                Text('带字母标记的是识别结果，可在下方棋盘上对照修改',
                    style: TextStyle(fontSize: 11, color: scheme.onSurfaceVariant)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ---------------- 棋子面板（Lichess 风格） ----------------
  Widget _buildPieceMenu(Side side, double boardSize) {
    final squareSize = boardSize / 8;
    return Container(
      clipBehavior: Clip.hardEdge,
      decoration: BoxDecoration(color: Theme.of(context).disabledColor),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        mainAxisSize: MainAxisSize.min,
        children: [
          // 拖拽模式
          _menuCell(
            size: squareSize,
            color: _mode == EditorPointerMode.drag
                ? Theme.of(context).colorScheme.primary
                : Colors.transparent,
            child: Icon(Icons.back_hand_outlined, size: squareSize * 0.55),
            onTap: () => _updateMode(EditorPointerMode.drag),
          ),
          // 6 枚棋子
          ...Role.values.map((role) {
            final piece = Piece(role: role, color: side);
            return _menuCell(
              size: squareSize,
              color: _mode == EditorPointerMode.edit && _activePiece == piece
                  ? Theme.of(context).colorScheme.primary
                  : Colors.transparent,
              child: PieceWidget(
                piece: piece,
                size: squareSize,
                pieceAssets: widget.pieceSet.assets,
              ),
              onTap: () => _updateMode(EditorPointerMode.edit, piece),
              draggableData: piece,
            );
          }),
          // 删除模式
          _menuCell(
            size: squareSize,
            color: _mode == EditorPointerMode.edit && _activePiece == null
                ? Theme.of(context).colorScheme.error
                : Colors.transparent,
            child: Icon(Icons.delete_outline, size: squareSize * 0.55),
            onTap: () => _updateMode(EditorPointerMode.edit, null),
          ),
        ],
      ),
    );
  }

  Widget _menuCell({
    required double size,
    required Color color,
    required Widget child,
    required VoidCallback onTap,
    Piece? draggableData,
  }) {
    final content = ColoredBox(
      color: color,
      child: SizedBox(width: size, height: size, child: child),
    );
    if (draggableData == null) {
      return GestureDetector(onTap: onTap, child: content);
    }
    return GestureDetector(
      onTap: onTap,
      child: Draggable<Piece>(
        data: draggableData,
        feedback: PieceDragFeedback(
          piece: draggableData,
          squareSize: size,
          pieceAssets: widget.pieceSet.assets,
        ),
        childWhenDragging: Opacity(opacity: 0.4, child: content),
        child: content,
        onDragEnd: (_) => _updateMode(EditorPointerMode.drag),
      ),
    );
  }

  // ---------------- FEN 显示与操作 ----------------
  Widget _buildFenBar() {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: scheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(10),
        ),
        child: SelectableText(
          _fen,
          style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
        ),
      ),
    );
  }

  Widget _buildActionRow() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _loadFen('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR'),
                  icon: const Icon(Icons.home_outlined, size: 16),
                  label: const Text('初始局面', style: TextStyle(fontSize: 12)),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _clearBoard,
                  icon: const Icon(Icons.delete_sweep_outlined, size: 16),
                  label: const Text('清空棋盘', style: TextStyle(fontSize: 12)),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => setState(() => _orientation = _orientation.opposite),
                  icon: const Icon(Icons.flip, size: 16),
                  label: const Text('翻转', style: TextStyle(fontSize: 12)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: _fen));
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('已复制 FEN'), duration: Duration(seconds: 1)),
                    );
                  },
                  icon: const Icon(Icons.copy, size: 16),
                  label: const Text('复制', style: TextStyle(fontSize: 12)),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton.icon(
                  onPressed: () => Navigator.pop(context, _fen),
                  icon: const Icon(Icons.check, size: 16),
                  label: const Text('完成', style: TextStyle(fontSize: 12)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _pasteFen() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    final text = data?.text?.trim();
    if (text == null || text.isEmpty) return;
    if (!mounted) return;
    try {
      Setup.parseFen(text);
      _loadFen(text);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('已载入 FEN'), duration: Duration(seconds: 1)),
      );
    } catch (_) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('无效 FEN'), duration: Duration(seconds: 1)),
      );
    }
  }
}
