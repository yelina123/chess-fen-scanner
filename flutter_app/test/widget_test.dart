import 'package:flutter_test/flutter_test.dart';

import 'package:chess_fen_app/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const ChessFenApp());
    expect(find.text('棋盘 FEN 识别'), findsOneWidget);
    await tester.pumpAndSettle();
  });
}
