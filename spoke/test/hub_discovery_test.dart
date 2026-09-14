// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:pathfinder_god/services/hub_discovery.dart';

void main() {
  group('HubDiscovery static candidates (no network)', () {
    test('includes hotspot gateway and emulator loopback', () {
      final hubs = HubDiscovery().staticCandidates();
      final urls = hubs.map((h) => h.baseUrl).toList();
      expect(urls, contains('http://192.168.137.1:8000'));
      expect(urls, contains('http://10.0.2.2:8000'));
    });

    test('last-known URL is probed first', () {
      final hubs = HubDiscovery()
          .staticCandidates(savedBaseUrl: 'http://192.168.4.144:8000');
      expect(hubs.first.name, 'Last known hub');
      expect(hubs.first.baseUrl, 'http://192.168.4.144:8000');
    });

    test('detail string includes version, model, url', () {
      const hub = DiscoveredHub(
        name: 'Laptop',
        host: '192.168.1.2',
        port: 8000,
        version: '0.1.0',
        model: 'phi4-mini',
      );
      expect(hub.detail, contains('v0.1.0'));
      expect(hub.detail, contains('phi4-mini'));
      expect(hub.detail, contains('http://192.168.1.2:8000'));
    });
  });
}
