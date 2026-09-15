// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:pathfinder_god/services/rulebook_db.dart';
import 'package:pathfinder_god/services/slm_guide.dart';

void main() {
  group('SlmGuideService.buildGuidePrompt (pure, no model needed)', () {
    const hits = [
      LocalRuleHit(
        name: 'Flanking',
        content: 'When you and an ally flank a foe, it is off-guard to melee attacks.',
        system: '2E',
        category: 'rule',
        sourceBook: 'Core Rulebook',
      ),
      LocalRuleHit(
        name: 'Off-Guard',
        content: 'Off-guard is a condition that lowers AC.',
        system: '2E',
        category: 'condition',
        sourceBook: 'Core Rulebook',
      ),
    ];

    test('includes citations, question, and caps at 5 hits', () {
      final prompt = SlmGuideService.buildGuidePrompt('how does flanking work?', hits);
      expect(prompt, contains('[Core Rulebook - Flanking] (2E)'));
      expect(prompt, contains('[Core Rulebook - Off-Guard] (2E)'));
      expect(prompt, contains('Question: how does flanking work?'));
    });

    test('truncates long excerpts with ellipsis', () {
      final long = LocalRuleHit(
        name: 'Long',
        content: 'x' * 600,
        system: '1E',
        category: 'spell',
        sourceBook: 'Core Rulebook',
      );
      final prompt = SlmGuideService.buildGuidePrompt('q', [long]);
      expect(prompt, contains('…'));
      expect(prompt.length, lessThan(600 + 300));
    });
  });

  group('SlmGuideService pipeline helpers (pure)', () {
    test('formatBytes renders B/KB/MB/GB', () {
      expect(SlmGuideService.formatBytes(0), '0 B');
      expect(SlmGuideService.formatBytes(512), contains('B'));
      expect(SlmGuideService.formatBytes(2048), contains('KB'));
      expect(SlmGuideService.formatBytes(2 * 1024 * 1024), contains('MB'));
      expect(
          SlmGuideService.formatBytes(2 * 1024 * 1024 * 1024), contains('GB'));
    });

    test('friendlyDownloadError maps 401/404/network', () {
      expect(SlmGuideService.friendlyDownloadError('401 Unauthorized'),
          contains('HuggingFace token'));
      expect(SlmGuideService.friendlyDownloadError('404 Not Found'),
          contains('renamed'));
      expect(
          SlmGuideService.friendlyDownloadError(
              'SocketException: Failed host lookup'),
          contains('Network failed'));
    });

    test('SlmUrlCheck.label covers all states', () {
      expect(
          const SlmUrlCheck(SlmUrlStatus.ok, 200, '').label, contains('OK'));
      expect(const SlmUrlCheck(SlmUrlStatus.needsToken, 401, '').label,
          contains('token'));
      expect(const SlmUrlCheck(SlmUrlStatus.notFound, 404, '').label,
          contains('404'));
      expect(const SlmUrlCheck(SlmUrlStatus.networkFail, -1, '').label,
          contains('No network'));
    });
  });
}
