import 'package:chessground/chessground.dart';
import 'package:dartchess/dartchess.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// FEN 编辑器：drag 拖拽 / edit 点击放置双模式，参考 lichess 棋盘编辑器。
class FenEditorScreen extends StatefulWidget {
  final String initialFen;
  final PieceSet pieceSet;
  const FenEditorScreen({super.key, required this.initialFen, this.pieceSet = PieceSet.cburnett});

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

  void _editSquare(Square square) {
    setState(() {
      if (_activePiece != null) {
        _pieces[square] = _activePiece!;
      } else {
        _pieces.remove(square);
      }
      _syncFen();
    });
  }

  void _dropPiece(Square? origin, Square dest, Piece piece) {
    setState(() {
      if (origin != null) _pieces.remove(origin);
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

  @override
  Widget build(BuildContext context) {
    final w = MediaQuery.of(context).size.width;
    final boardSize = w < 400 ? w : w * 0.94;
    return Scaffold(
      appBar: AppBar(
        title: const Text('编辑 FEN', style: TextStyle(fontSize: 16)),
        actions: [
          IconButton(
            tooltip: '翻转棋盘',
            icon: const Icon(Icons.flip),
            onPressed: () => setState(() => _orientation = _orientation.opposite),
          ),
          IconButton(
            tooltip: '清空棋盘',
            icon: const Icon(Icons.delete_outline),
            onPressed: () => setState(() {
              _pieces = {};
              _syncFen();
            }),
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            children: [
              _buildPieceMenu(Side.white, boardSize),
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
                  onDroppedPiece: _dropPiece,
                  onDiscardedPiece: _discardPiece,
                ),
              ),
              _buildPieceMenu(Side.black, boardSize),
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: SelectableText(
                    _fen,
                    style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () {
                          Clipboard.setData(ClipboardData(text: _fen));
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('已复制 FEN'), duration: Duration(seconds: 1)),
                          );
                        },
                        icon: const Icon(Icons.copy, size: 18),
                        label: const Text('复制'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton.icon(
                        onPressed: () => Navigator.pop(context, _fen),
                        icon: const Icon(Icons.check, size: 18),
                        label: const Text('完成'),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPieceMenu(Side side, double boardSize) {
    final squareSize = boardSize / 8;
    final isWhite = side == Side.white;
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 4),
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _buildToolButton(
            icon: Icons.pan_tool,
            selected: _mode == EditorPointerMode.drag,
            onTap: () => setState(() {
              _mode = EditorPointerMode.drag;
              _activePiece = null;
            }),
            size: squareSize,
          ),
          ...Role.values.map((role) {
            final piece = Piece(role: role, color: side);
            return _buildPieceButton(
              label: _roleLabel(role),
              isWhite: isWhite,
              selected: _mode == EditorPointerMode.edit && _activePiece == piece,
              onTap: () => setState(() {
                _mode = EditorPointerMode.edit;
                _activePiece = piece;
              }),
              size: squareSize,
            );
          }),
          _buildToolButton(
            icon: Icons.delete,
            selected: _mode == EditorPointerMode.edit && _activePiece == null,
            onTap: () => setState(() {
              _mode = EditorPointerMode.edit;
              _activePiece = null;
            }),
            size: squareSize,
          ),
        ],
      ),
    );
  }

  String _roleLabel(Role role) {
    switch (role) {
      case Role.king: return 'K';
      case Role.queen: return 'Q';
      case Role.rook: return 'R';
      case Role.bishop: return 'B';
      case Role.knight: return 'N';
      case Role.pawn: return 'P';
    }
  }

  Widget _buildToolButton({
    required IconData icon,
    required bool selected,
    required VoidCallback onTap,
    required double size,
  }) {
    final scheme = Theme.of(context).colorScheme;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color: selected ? scheme.primary.withOpacity(0.2) : Colors.transparent,
          borderRadius: BorderRadius.circular(6),
        ),
        child: Icon(icon, size: size * 0.5, color: selected ? scheme.primary : scheme.onSurfaceVariant),
      ),
    );
  }

  Widget _buildPieceButton({
    required String label,
    required bool isWhite,
    required bool selected,
    required VoidCallback onTap,
    required double size,
  }) {
    final scheme = Theme.of(context).colorScheme;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color: selected ? scheme.primary.withOpacity(0.2) : Colors.transparent,
          borderRadius: BorderRadius.circular(6),
        ),
        alignment: Alignment.center,
        child: Text(
          label,
          style: TextStyle(
            fontSize: size * 0.45,
            fontWeight: FontWeight.bold,
            color: isWhite ? (Theme.of(context).brightness == Brightness.dark ? Colors.white70 : Colors.grey) : Colors.black,
          ),
        ),
      ),
    );
  }
}
