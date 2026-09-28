import 'package:shared_preferences/shared_preferences.dart';

/// 用户设置持久化
class AppSettings {
  static const _kMode = 'mode';
  static const _kTheme = 'theme';        // null = 自动（遍历全部套件）
  static const _kAssumeClean = 'assume_clean';

  String mode = 'standard';
  String? theme; // null = 自动
  bool assumeClean = false;

  static Future<AppSettings> load() async {
    final sp = await SharedPreferences.getInstance();
    final s = AppSettings();
    s.mode = sp.getString(_kMode) ?? 'standard';
    s.theme = sp.getString(_kTheme);
    s.assumeClean = sp.getBool(_kAssumeClean) ?? false;
    return s;
  }

  Future<void> save() async {
    final sp = await SharedPreferences.getInstance();
    await sp.setString(_kMode, mode);
    if (theme == null) {
      await sp.remove(_kTheme);
    } else {
      await sp.setString(_kTheme, theme!);
    }
    await sp.setBool(_kAssumeClean, assumeClean);
  }
}
