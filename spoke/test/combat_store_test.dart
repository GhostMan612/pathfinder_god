// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:pathfinder_god/models/combatant.dart';
import 'package:pathfinder_god/services/combat_store.dart';
import 'package:pathfinder_god/api/hub_client.dart';
import 'package:pathfinder_god/api/models.dart';
import 'package:pathfinder_god/config/hub_config.dart';
import 'package:http/http.dart' as http;

/// Minimal fake HubClient for testing CombatStore without network.
/// Extends HubClient and provides minimal implementations.
class _FakeHubClient extends HubClient {
  _FakeHubClient() : super(HubConfig('http://test'), httpClient: http.Client());

  @override
  Future<HubHealth> health() async => HubHealth(
        version: 'test',
        ollamaModel: 'test',
        databasesFound: const [],
        status: 'ok',
      );

  @override
  Future<AskResponse> ask(String query, {String edition = 'both', String? mode, List<List<String>> history = const []}) async => throw UnimplementedError();

  @override
  Future<AskResponse> generate(String kind, String prompt, {String edition = 'both'}) async => throw UnimplementedError();

  @override
  Future<List<RuleHit>> searchRules(String query, {String edition = 'both', int limit = 10}) async => [];

  @override
  Future<Map<String, dynamic>> exportCampaign(int campaignId) async => throw UnimplementedError();

  @override
  Future<void> importCampaign(Map<String, dynamic> payload) async => throw UnimplementedError();

  @override
  Future<RuleHit> fetchRule(String query, {String edition = 'both'}) async => throw UnimplementedError();

  @override
  Future<int> reportMisses(List<Map<String, String>> queries) async => 0;

  @override
  Future<Map<String, dynamic>> buildCharacter(String prompt) async => throw UnimplementedError();

  @override
  Future<Map<String, dynamic>> resolveStrike({
    required int attackRoll,
    required int targetAc,
    required int damageRoll,
    required int targetHp,
    int targetTempHp = 0,
  }) async => {};

  @override
  Future<EndTurnOutcome> endTurnConditions(
    List<Map<String, dynamic>> conditions, {
    int currentHp = 0,
  }) async =>
      const EndTurnOutcome(conditions: []);

  @override
  void close() {}
}

void main() {
  late CombatStore store;
  late _FakeHubClient fakeClient;

  setUp(() {
    fakeClient = _FakeHubClient();
    store = CombatStore(fakeClient);
  });

  group('CombatStore', () {
    test('adds combatants and sorts by initiative descending', () {
      store.addCombatant(Combatant(
        id: '1',
        name: 'Low Init',
        isPc: false,
        initiative: 5,
        currentHp: 10,
        maxHp: 10,
        ac: 15,
      ));
      store.addCombatant(Combatant(
        id: '2',
        name: 'High Init',
        isPc: false,
        initiative: 20,
        currentHp: 10,
        maxHp: 10,
        ac: 15,
      ));

      expect(store.combatants.length, 2);
      expect(store.combatants[0].name, 'High Init');
      expect(store.combatants[1].name, 'Low Init');
    });

    test('round rollover when activeIndex cycles', () {
      store.addCombatant(Combatant(
        id: '1',
        name: 'A',
        isPc: false,
        initiative: 15,
        currentHp: 10,
        maxHp: 10,
        ac: 15,
      ));
      store.addCombatant(Combatant(
        id: '2',
        name: 'B',
        isPc: false,
        initiative: 10,
        currentHp: 10,
        maxHp: 10,
        ac: 15,
      ));

      expect(store.activeIndex, 0);
      expect(store.currentRound, 1);

      // Next turn -> B's turn
      store.nextTurn();
      expect(store.activeIndex, 1);
      expect(store.currentRound, 1);

      // Next turn -> round 2, back to A
      store.nextTurn();
      expect(store.activeIndex, 0);
      expect(store.currentRound, 2);
    });

    test('HP clamping min 0', () {
      store.addCombatant(Combatant(
        id: '1',
        name: 'Test',
        isPc: false,
        initiative: 10,
        currentHp: 10,
        maxHp: 20,
        ac: 15,
      ));

      // Deal more damage than current HP
      store.updateHp('1', -50);
      expect(store.combatants.first.currentHp, 0);
    });

    test('HP clamping max maxHp', () {
      store.addCombatant(Combatant(
        id: '1',
        name: 'Test',
        isPc: false,
        initiative: 10,
        currentHp: 10,
        maxHp: 20,
        ac: 15,
      ));

      // Heal more than max
      store.updateHp('1', 50);
      expect(store.combatants.first.currentHp, 20);
    });

    test('remove combatant adjusts activeIndex', () {
      store.addCombatant(Combatant(
        id: '1',
        name: 'A',
        isPc: false,
        initiative: 15,
        currentHp: 10,
        maxHp: 10,
        ac: 15,
      ));
      store.addCombatant(Combatant(
        id: '2',
        name: 'B',
        isPc: false,
        initiative: 10,
        currentHp: 10,
        maxHp: 10,
        ac: 15,
      ));

      // Remove the active combatant (index 0)
      store.removeCombatant('1');
      expect(store.activeIndex, 0);
      expect(store.combatants.length, 1);
      expect(store.combatants[0].id, '2');
    });

    test('clear encounter resets all state', () {
      store.addCombatant(Combatant(
        id: '1',
        name: 'A',
        isPc: false,
        initiative: 15,
        currentHp: 10,
        maxHp: 10,
        ac: 15,
      ));
      store.nextTurn(); // Round 2
      store.clearEncounter();

      expect(store.combatants.isEmpty, isTrue);
      expect(store.activeIndex, 0);
      expect(store.currentRound, 1);
    });

    test('temp HP tracked separately', () {
      store.addCombatant(Combatant(
        id: '1',
        name: 'Test',
        isPc: false,
        initiative: 10,
        currentHp: 10,
        maxHp: 20,
        ac: 15,
        tempHp: 5,
      ));

      expect(store.combatants.first.tempHp, 5);
      store.setTempHp('1', 10);
      expect(store.combatants.first.tempHp, 10);
    });

    test('conditions added and removed', () {
      store.addCombatant(Combatant(
        id: '1',
        name: 'Test',
        isPc: false,
        initiative: 10,
        currentHp: 10,
        maxHp: 20,
        ac: 15,
      ));

      store.addCondition('1', const CombatCondition(name: 'Frightened', value: 2));
      expect(store.combatants.first.conditions.length, 1);
      expect(store.combatants.first.conditions.first.name, 'Frightened');
      expect(store.combatants.first.conditions.first.value, 2);

      store.removeCondition('1', 'Frightened');
      expect(store.combatants.first.conditions.isEmpty, isTrue);
    });
  });
}