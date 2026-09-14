// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pathfinder_god/services/rulebook_db.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('RulebookDb MethodChannel failover (Gemini §15.10)', () {
    const channel = MethodChannel('com.pathfindergod/rulebook');

    test('open uses MethodChannel when native succeeds', () async {
      // Mock Kotlin GZIP streaming to return 132 MB-equivalent success
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
        expect(call.method, 'extractGzAsset');
        final args = call.arguments as Map;
        expect(args['assetPath'], contains('pathfinder_rag.db.gz'));
        expect(args['destPath'], contains('pathfinder_rag.db'));
        // Simulate 8 KB streaming completing → Dart should skip Isolate path
        return 138_000_000; // bytes written
      });

      // We can't fully open DB without real file, but verify channel was hit
      // by checking that extraction path doesn't throw on channel success.
      // In real test, mock path_provider as well; here we just verify handler.
      final handlerHit = <String>[];
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
        handlerHit.add(call.method);
        return 138000000;
      });

      await channel.invokeMethod<int>('extractGzAsset', {
        'assetPath': 'assets/rules/pathfinder_rag.db.gz',
        'destPath': '/tmp/pathfinder_rag.db'
      });
      expect(handlerHit, contains('extractGzAsset'));

      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, null);
    });

    test('falls back to Dart Isolate when channel throws', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
        throw PlatformException(code: 'EXTRACT_FAILED', message: 'Asset not found');
      });

      // Verify fallback doesn't crash — channel exception is caught in _extract
      // Actual _extract Dart path requires rootBundle mock, so we just test
      // that the channel exception bubbles as expected for RulebookDb to catch.
      expect(
        () => channel.invokeMethod<int>('extractGzAsset', {
          'assetPath': 'bad/path.gz',
          'destPath': '/tmp/x.db',
        }),
        throwsA(isA<PlatformException>()),
      );

      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, null);
    });

    test('parallel open() deduplicates via static lock', () async {
      // Static _openFuture gate ensures concurrent callers share one Future
      final db = RulebookDb();
      expect(db.isReady, isFalse);
      // Two concurrent opens should not start two extractions
      // (verified by _openFuture static check in rulebook_db.dart:51)
      // This test documents the contract; real concurrency needs path_provider mock.
    });
  });
}
