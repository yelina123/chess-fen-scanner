import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:chessground/chessground.dart';
import 'package:dartchess/dartchess.dart';

void main() => runApp(const FenEditorApp());

class FenEditorApp extends StatelessWidget {
  const FenEditorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FEN Editor',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.blue),
      home: const FenEditorPage(),
    );
  }
}

class FenEditorPage extends StatefulWidget {
  const FenEditorPage({super.key});

  @override
  State<FenEditorPage> createState() => _FenEditorPageState();
}

class _FenEditorPageState extends State<FenEditorPage> {
  static const channel = MethodChannel('com.chessscan/editor');

  Pieces _pieces = readFen('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR');
  EditorPointerMode _mode = EditorPointerMode.drag;
  Piece? _activePiece;
  Side _orientation = Side.white;
  String _fen = '';

  @override
  void initState() {
    super.initState();
    _fen = writeFen(_pieces);
    channel.setMethodCallHandler(_handleMethod);
    channel.invokeMethod('requestFen').then((value) {
      if (value != null && value is String && value.isNotEmpty) {
        final clean = value.split(' ').first;
        setState(() {
          _pieces = readFen(clean);
          _fen = writeFen(_pieces);
        });
      }
    });
  }

  Future<dynamic> _handleMethod(MethodCall call) async {
    if (call.method == 'setFen') {
      final fen = (call.arguments as String).split(' ').first;
      setState(() {
        _pieces = readFen(fen);
        _fen = writeFen(_pieces);
      });
    }
    return null;
  }

  void _syncFen() {
    _fen = writeFen(_pieces);
    channel.invokeMethod('onFenChanged', _fen);
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
    final boardSize = w < 400 ? w : w * 0.92;
    return Scaffold(
      appBar: AppBar(
        title: const Text('编辑识别结果', style: TextStyle(fontSize: 16)),
        actions: [
          IconButton(
            tooltip: '翻转',
            icon: const Icon(Icons.flip),
            onPressed: () => setState(() => _orientation = _orientation.opposite),
          ),
          IconButton(
            tooltip: '清空',
            icon: const Icon(Icons.delete_outline),
            onPressed: () => setState(() {
              _pieces = {};
              _syncFen();
            }),
          ),
        ],
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            _buildPieceMenu(Side.white, boardSize),
            Center(
              child: ChessboardEditor(
                size: boardSize,
                pieces: _pieces,
                orientation: _orientation,
                pointerMode: _mode,
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
                  color: Colors.grey[100],
                  borderRadius: BorderRadius.circular(8),
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
                    child: OutlinedButton(
                      onPressed: () {
                        Clipboard.setData(ClipboardData(text: _fen));
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('已复制FEN'), duration: Duration(seconds: 1)),
                        );
                      },
                      child: const Text('复制'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      onPressed: () => channel.invokeMethod('finish', _fen),
                      child: const Text('完成'),
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

  Widget _buildPieceMenu(Side side, double boardSize) {
    final squareSize = boardSize / 8;
    return Container(
      color: Colors.grey[200],
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _buildIconButton(
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
            final label = _roleLabel(role);
            return _buildPieceButton(
              label: label,
              isWhite: side == Side.white,
              selected: _mode == EditorPointerMode.edit && _activePiece == piece,
              onTap: () => setState(() {
                _mode = EditorPointerMode.edit;
                _activePiece = piece;
              }),
              size: squareSize,
            );
          }),
          _buildIconButton(
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

  Widget _buildIconButton({
    required IconData icon,
    required bool selected,
    required VoidCallback onTap,
    required double size,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: size,
        height: size,
        color: selected ? Colors.blue.withOpacity(0.25) : Colors.transparent,
        child: Icon(icon, size: size * 0.55, color: Colors.grey[700]),
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
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: size,
        height: size,
        color: selected ? Colors.blue.withOpacity(0.25) : Colors.transparent,
        alignment: Alignment.center,
        child: Text(
          label,
          style: TextStyle(
            fontSize: size * 0.5,
            fontWeight: FontWeight.bold,
            color: isWhite ? Colors.grey[400] : Colors.black87,
          ),
        ),
      ),
    );
  }
}
