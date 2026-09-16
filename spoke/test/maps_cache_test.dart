// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:pathfinder_god/storage/maps_cache_store.dart';

void main() {
  group('CachedMap dual-layer payload', () {
    test('round-trips gm and player base64 through toMap/fromMap', () {
      final map = CachedMap(
        id: 'map_1',
        prompt: 'A tavern with a pit trap',
        gmBase64Png: 'Z20tbGF5ZXI=',
        playerBase64Png: 'cGxheWVyLWxheWVy',
        width: 10,
        height: 8,
        createdAt: DateTime.utc(2026, 1, 1),
      );
      final restored = CachedMap.fromMap(map.toMap());
      expect(restored.gmBase64Png, 'Z20tbGF5ZXI=');
      expect(restored.playerBase64Png, 'cGxheWVyLWxheWVy');
    });

    test('fromMap reads gm_base64_png and player_base64_png columns', () {
      final restored = CachedMap.fromMap({
        'id': 'map_2',
        'prompt': 'Dungeon',
        'gm_base64_png': 'Z20=',
        'player_base64_png': 'cGxheWVy',
        'width': 5,
        'height': 5,
        'created_at': DateTime.utc(2026, 1, 1).toIso8601String(),
      });
      expect(restored.gmBase64Png, 'Z20=');
      expect(restored.playerBase64Png, 'cGxheWVy');
      expect(restored.width, 5);
      expect(restored.height, 5);
    });
  });
}
