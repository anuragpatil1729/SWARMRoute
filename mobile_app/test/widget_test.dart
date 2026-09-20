import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/main.dart';

void main() {
  testWidgets('SwarmRouteApp initializes to login screen', (WidgetTester tester) async {
    await tester.pumpWidget(const SwarmRouteApp());
    expect(find.text('SWARMRoute'), findsOneWidget);
    expect(find.text('Autonomous Real-World Fleet Platform'), findsOneWidget);
  });
}
