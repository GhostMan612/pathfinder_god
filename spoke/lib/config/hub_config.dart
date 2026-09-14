// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:shared_preferences/shared_preferences.dart';

/// Remembers where the hub lives (the laptop's LAN address) between launches.
///
/// Default assumes the Android emulator talking to a hub on the host machine
/// (`10.0.2.2`). On a real phone, set this to the laptop's Wi-Fi IP, e.g.
/// `http://192.168.1.42:8000`, from the Settings screen.
class HubConfig {
  static const _key = 'hub_base_url';
  static const defaultBaseUrl = 'http://10.0.2.2:8000';

  String _baseUrl;
  HubConfig(this._baseUrl);

  String get baseUrl => _baseUrl;

  /// http(s) base as-is, used for REST.
  Uri httpUri(String path, [Map<String, dynamic>? query]) {
    final base = Uri.parse(_baseUrl);
    return base.replace(
      path: path,
      queryParameters: query?.map((k, v) => MapEntry(k, '$v')),
    );
  }

  /// ws(s) base, derived by swapping the scheme — used for the /stream socket.
  Uri wsUri(String path) {
    final base = Uri.parse(_baseUrl);
    final scheme = base.scheme == 'https' ? 'wss' : 'ws';
    return base.replace(scheme: scheme, path: path);
  }

  static Future<HubConfig> load() async {
    final prefs = await SharedPreferences.getInstance();
    return HubConfig(prefs.getString(_key) ?? defaultBaseUrl);
  }

  Future<void> save(String baseUrl) async {
    _baseUrl = baseUrl.trim();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, _baseUrl);
  }
}
