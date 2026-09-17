// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:pathfinder_god/models/campaign.dart';

void main() {
  group('CampaignModel', () {
    test('creation keeps fields', () {
      final campaign = CampaignModel(
        id: 'c1',
        name: 'Abomination Vaults',
        description: 'Delve below Otari.',
        updatedAt: DateTime.utc(2026, 1, 1),
      );
      expect(campaign.id, 'c1');
      expect(campaign.name, 'Abomination Vaults');
      expect(campaign.description, 'Delve below Otari.');
      expect(campaign.sessionNotes, isEmpty);
    });

    test('withNote appends without mutating the original', () {
      final campaign = CampaignModel(
        id: 'c1',
        name: 'Abomination Vaults',
        updatedAt: DateTime.utc(2026, 1, 1),
      );
      final updated = campaign.withNote('Cleared the tavern.');
      expect(updated.sessionNotes, ['Cleared the tavern.']);
      expect(campaign.sessionNotes, isEmpty);
      expect(
        updated.updatedAt.isAfter(DateTime.utc(2026, 1, 1)),
        isTrue,
      );
    });

    test('toJson/fromJson round-trip preserves notes', () {
      final campaign = CampaignModel(
        id: 'c1',
        name: 'Abomination Vaults',
        description: 'Delve below Otari.',
        sessionNotes: const ['Session one.', 'Session two.'],
        updatedAt: DateTime.utc(2026, 2, 3, 4, 5, 6),
      );
      final restored = CampaignModel.fromJson(campaign.toJson());
      expect(restored.id, 'c1');
      expect(restored.name, 'Abomination Vaults');
      expect(restored.description, 'Delve below Otari.');
      expect(restored.sessionNotes, ['Session one.', 'Session two.']);
      expect(restored.updatedAt, DateTime.utc(2026, 2, 3, 4, 5, 6));
    });

    test('fromJson tolerates missing keys', () {
      final restored = CampaignModel.fromJson({'id': 'c9'});
      expect(restored.name, 'Untitled Campaign');
      expect(restored.description, isEmpty);
      expect(restored.sessionNotes, isEmpty);
    });

    test('json string round-trip', () {
      final campaign = CampaignModel(
        id: 'c1',
        name: 'Abomination Vaults',
        sessionNotes: const ['A quiet night.'],
        updatedAt: DateTime.utc(2026, 1, 1),
      );
      final restored = CampaignModel.fromJsonString(campaign.toJsonString());
      expect(restored.sessionNotes, ['A quiet night.']);
    });
  });
}
