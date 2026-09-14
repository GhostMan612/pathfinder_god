// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:multicast_dns/multicast_dns.dart';

/// A hub candidate found on the local network (or a well-known address).
class DiscoveredHub {
  final String name;
  final String host;
  final int port;
  final String? version;
  final String? model;
  final bool viaMdns;

  const DiscoveredHub({
    required this.name,
    required this.host,
    required this.port,
    this.version,
    this.model,
    this.viaMdns = true,
  });

  String get baseUrl => 'http://$host:$port';

  String get detail {
    final bits = <String>[];
    if (version != null && version!.isNotEmpty) bits.add('v$version');
    if (model != null && model!.isNotEmpty) bits.add(model!);
    bits.add(baseUrl);
    return bits.join(' · ');
  }
}

/// Zero-config hub discovery — no IP typing for non-technical users.
///
/// Strategy (in order):
/// 1. mDNS browse for `_pathfindergod._tcp.local` (hub advertises itself
///    from `hub/app/discovery.py`). Works on home Wi-Fi.
/// 2. Well-known fallbacks, verified by the caller via `/health`:
///    - Windows Mobile Hotspot gateway `192.168.137.1:8000` (covers the
///      Sovereign SSH hotspot setup — the laptop is always the gateway,
///      so no SSH involvement is needed for discovery).
///    - Android emulator loopback `10.0.2.2:8000`.
///    - The last-known saved URL (survives DHCP IP changes by re-probing).
class HubDiscovery {
  static const serviceType = '_pathfindergod._tcp.local';
  static const defaultPort = 8000;
  static const hotspotGateway = '192.168.137.1';
  static const emulatorLoopback = '10.0.2.2';

  /// Browse mDNS for hubs. Never throws — returns [] when multicast is
  /// unavailable (guest networks, VPNs, mobile data).
  Future<List<DiscoveredHub>> discoverMdns({
    Duration timeout = const Duration(seconds: 4),
  }) async {
    final found = <String, DiscoveredHub>{};
    MDnsClient? client;
    try {
      client = MDnsClient();
      await client.start().timeout(const Duration(seconds: 5));
    } catch (e) {
      debugPrint('HubDiscovery: mDNS unavailable: $e');
      return const [];
    }
    try {
      final ptrs = <PtrResourceRecord>[];
      final sub = client
          .lookup<PtrResourceRecord>(
            ResourceRecordQuery.serverPointer(serviceType),
          )
          .listen(ptrs.add, onError: (_) {});
      await Future<void>.delayed(timeout);
      await sub.cancel();

      for (final ptr in ptrs) {
        try {
          final srv = await client
              .lookup<SrvResourceRecord>(
                ResourceRecordQuery.service(ptr.domainName),
              )
              .first
              .timeout(const Duration(seconds: 2));
          String? version;
          String? model;
          try {
            final txt = await client
                .lookup<TxtResourceRecord>(
                  ResourceRecordQuery.text(ptr.domainName),
                )
                .first
                .timeout(const Duration(seconds: 2));
            final props = _parseTxt(txt.text);
            version = props['version'];
            model = props['model'];
          } catch (_) {/* TXT optional */}

          final ips = <String>[];
          try {
            await for (final ip in client
                .lookup<IPAddressResourceRecord>(
                  ResourceRecordQuery.addressIPv4(srv.target),
                )
                .timeout(const Duration(seconds: 2))) {
              if (ip.address.type == InternetAddressType.IPv4) {
                ips.add(ip.address.address);
              }
            }
          } catch (_) {/* fall back to target hostname */}

          final host = ips.isNotEmpty ? ips.first : srv.target;
          final name = ptr.domainName
              .replaceFirst('.$serviceType', '')
              .replaceAll('-', ' ');
          found[host] = DiscoveredHub(
            name: name.isEmpty ? 'Pathfinder God Hub' : name,
            host: host,
            port: srv.port,
            version: version,
            model: model,
          );
        } catch (e) {
          debugPrint('HubDiscovery: skipping ${ptr.domainName}: $e');
        }
      }
    } finally {
      client.stop();
    }
    return found.values.toList();
  }

  /// Static candidates that need no multicast (hotspot gateway, emulator).
  /// The caller probes each with `/health` and keeps the reachable ones.
  List<DiscoveredHub> staticCandidates({String? savedBaseUrl}) {
    final out = <DiscoveredHub>[
      const DiscoveredHub(
        name: 'Laptop hotspot',
        host: hotspotGateway,
        port: defaultPort,
        viaMdns: false,
      ),
      const DiscoveredHub(
        name: 'Android emulator',
        host: emulatorLoopback,
        port: defaultPort,
        viaMdns: false,
      ),
    ];
    if (savedBaseUrl != null && savedBaseUrl.isNotEmpty) {
      final uri = Uri.tryParse(savedBaseUrl.trim());
      if (uri != null && (uri.host.isNotEmpty)) {
        out.insert(
          0,
          DiscoveredHub(
            name: 'Last known hub',
            host: uri.host,
            port: uri.hasPort ? uri.port : defaultPort,
            viaMdns: false,
          ),
        );
      }
    }
    return out;
  }

  Map<String, String> _parseTxt(String raw) {
    final out = <String, String>{};
    for (final part in raw.split('\n')) {
      final idx = part.indexOf('=');
      if (idx > 0) {
        out[part.substring(0, idx).trim()] = part.substring(idx + 1).trim();
      }
    }
    return out;
  }
}
