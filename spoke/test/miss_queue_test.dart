// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:pathfinder_god/services/miss_queue.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  group('MissQueue (prefs-backed, no network)', () {
    setUp(() async {
      SharedPreferences.setMockInitialValues({});
    });

    test('queues, dedupes, and round-trips pending', () async {
      expect(await MissQueue.pending(), isEmpty);
      await MissQueue.queue('  Flanking  ', edition: '2e');
      await MissQueue.queue('Flanking', edition: '2e'); // dupe
      await MissQueue.queue('Flanking', edition: '1e'); // different edition: kept
      await MissQueue.queue('   '); // blank: ignored
      final items = await MissQueue.pending();
      expect(items.length, 2);
      expect(items.first, {'q': 'Flanking', 'edition': '2e'});
    });

    test('clear empties the queue', () async {
      await MissQueue.queue('Fireball');
      await MissQueue.clear();
      expect(await MissQueue.pending(), isEmpty);
    });
  });
}
