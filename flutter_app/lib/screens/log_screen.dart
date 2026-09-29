import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// 识别日志页：显示本次识别的逐格诊断，可复制/清空。
class LogScreen extends StatefulWidget {
  final List<String> initialLog;
  const LogScreen({super.key, required this.initialLog});

  @override
  State<LogScreen> createState() => _LogScreenState();
}

class _LogScreenState extends State<LogScreen> {
  late final List<String> _log = List.of(widget.initialLog);

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final text = _log.join('\n');
    return Scaffold(
      appBar: AppBar(
        title: const Text('识别日志', style: TextStyle(fontSize: 16)),
        actions: [
          IconButton(
            tooltip: '复制日志',
            icon: const Icon(Icons.copy, size: 20),
            onPressed: text.isEmpty
                ? null
                : () {
                    Clipboard.setData(ClipboardData(text: text));
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('已复制日志'), duration: Duration(seconds: 1)),
                    );
                  },
          ),
          IconButton(
            tooltip: '清空日志',
            icon: const Icon(Icons.delete_outline, size: 20),
            onPressed: _log.isEmpty
                ? null
                : () => setState(() => _log.clear()),
          ),
        ],
      ),
      body: _log.isEmpty
          ? Center(
              child: Text('暂无日志，识别一次棋盘后自动生成',
                  style: TextStyle(color: scheme.onSurfaceVariant)),
            )
          : SingleChildScrollView(
              padding: const EdgeInsets.all(12),
              child: SelectableText(
                text,
                style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
              ),
            ),
    );
  }
}
