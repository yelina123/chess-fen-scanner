import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

/// 关于页：版本、作者、GitHub 主页链接、开源协议。
class AboutScreen extends StatelessWidget {
  static const githubUrl = 'https://github.com/yelina123/chess-fen-scanner';

  final String version;
  final String buildNumber;
  const AboutScreen({super.key, required this.version, required this.buildNumber});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('关于', style: TextStyle(fontSize: 16))),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const SizedBox(height: 12),
          Icon(Icons.grid_on, size: 64, color: scheme.primary),
          const SizedBox(height: 12),
          Text(
            '棋盘 FEN 识别',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 4),
          Text(
            'v$version (build $buildNumber)',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 13, color: scheme.onSurfaceVariant),
          ),
          const SizedBox(height: 24),
          ListTile(
            leading: const Icon(Icons.person_outline),
            title: const Text('作者'),
            subtitle: const Text('yelina123'),
          ),
          ListTile(
            leading: const Icon(Icons.link),
            title: const Text('GitHub 主页'),
            subtitle: const Text(githubUrl),
            trailing: const Icon(Icons.open_in_new, size: 18),
            onTap: () async {
              final ok = await launchUrl(Uri.parse(githubUrl), mode: LaunchMode.externalApplication);
              if (!ok && context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('无法打开链接，请手动访问'), duration: Duration(seconds: 2)),
                );
              }
            },
          ),
          ListTile(
            leading: const Icon(Icons.code),
            title: const Text('开源协议'),
            subtitle: const Text('GPL-3.0'),
          ),
          ListTile(
            leading: const Icon(Icons.info_outline),
            title: const Text('项目说明'),
            subtitle: const Text('国际象棋棋盘截图 → FEN 离线识别，兼容 lichess / chess.com 常见棋子样式。'),
          ),
          const SizedBox(height: 12),
          Text(
            '识别结果仅供参考，导入前请在平台上核对。',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 12, color: scheme.outline),
          ),
        ],
      ),
    );
  }
}
