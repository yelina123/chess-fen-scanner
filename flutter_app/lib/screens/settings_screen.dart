import 'package:chessground/chessground.dart';
import 'package:flutter/material.dart';
import '../models/settings.dart';
import '../models/template_loader.dart';

/// 设置界面：棋子主题、识别模式、引擎标注开关
class SettingsScreen extends StatefulWidget {
  final AppSettings settings;
  const SettingsScreen({super.key, required this.settings});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late AppSettings _settings;
  List<String> _setNames = const [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _settings = widget.settings;
    _loadSets();
  }

  Future<void> _loadSets() async {
    final names = await TemplateLoader.listSets();
    if (mounted) setState(() { _setNames = names; _loading = false; });
  }

  /// chessground 内置主题名（用于预览显示）
  String _displayName(String set) {
    for (final ps in PieceSet.values) {
      if (ps.name == set) return ps.label;
    }
    return set;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('设置', style: TextStyle(fontSize: 16))),
      body: ListView(
        children: [
          ListTile(
            title: const Text('识别模式'),
            subtitle: const Text('standard 均衡 · recall 少漏子 · precision 少误判'),
            trailing: DropdownButton<String>(
              value: _settings.mode,
              items: const [
                DropdownMenuItem(value: 'standard', child: Text('均衡')),
                DropdownMenuItem(value: 'recall', child: Text('保守(少漏)')),
                DropdownMenuItem(value: 'precision', child: Text('严格(少误)')),
              ],
              onChanged: (v) {
                if (v == null) return;
                setState(() => _settings.mode = v);
                _settings.save();
              },
            ),
          ),
          SwitchListTile(
            title: const Text('图中有引擎标注'),
            subtitle: const Text('箭头 / ? / ! 等。关闭时用更准确的算法'),
            value: _settings.assumeClean,
            onChanged: (v) {
              setState(() => _settings.assumeClean = v);
              _settings.save();
            },
          ),
          const Divider(),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: Text('棋子主题', style: Theme.of(context).textTheme.titleSmall),
          ),
          ListTile(
            title: const Text('自动（遍历全部主题）'),
            leading: Icon(
              _settings.theme == null ? Icons.radio_button_checked : Icons.radio_button_off,
              color: _settings.theme == null ? Theme.of(context).colorScheme.primary : null,
            ),
            onTap: () {
              setState(() => _settings.theme = null);
              _settings.save();
            },
          ),
          if (_loading)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            )
          else
            for (final set in _setNames)
              ListTile(
                dense: true,
                title: Text(_displayName(set)),
                leading: Icon(
                  _settings.theme == set ? Icons.radio_button_checked : Icons.radio_button_off,
                  color: _settings.theme == set ? Theme.of(context).colorScheme.primary : null,
                ),
                onTap: () {
                  setState(() => _settings.theme = set);
                  _settings.save();
                },
              ),
        ],
      ),
    );
  }
}
