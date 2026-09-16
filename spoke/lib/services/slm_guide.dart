// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_gemma/core/domain/model_source.dart';
import 'package:flutter_gemma/flutter_gemma.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'rulebook_db.dart';

/// On-device SLM Guide — a real chatbot brain with zero network.
///
/// Uses MediaPipe LLM Inference (flutter_gemma) with Gemma 3n. The ~2GB model
/// file is NOT bundled (APK would explode); the user downloads it once over
/// Wi-Fi from HuggingFace (gated repo — accept the license + paste a token),
/// or side-loads `guide_model.task` into app documents. Every answer is
/// grounded in offline FTS5 hits passed as context — the SLM narrates, the
/// database provides the facts.
///
/// NOTE: verify the model URL in a browser before downloading (Google
/// renames task files between releases). If it 404s, update [_modelUrl].
class SlmGuideService {
  static final SlmGuideService instance = SlmGuideService._();
  SlmGuideService._();

  /// Gemma 3n E2B instruction-tuned LiteRT task file (VERIFY FIRST).
  static const modelUrl =
      'https://huggingface.co/google/gemma-3n-E2B-it-litert-preview/resolve/main/gemma-3n-E2B-it-int4.task?download=true';
  static const sideLoadName = 'guide_model.task';

  static const _keyEnabled = 'slm_enabled';
  static const _keyToken = 'slm_hf_token';
  static const _keyModelFile = 'slm_guide_model';

  InferenceChat? _chat;
  bool _warming = false;

  Future<SharedPreferences> get _prefs => SharedPreferences.getInstance();

  Future<bool> get enabled async =>
      (await _prefs).getBool(_keyEnabled) ?? false;

  Future<void> setEnabled(bool v) async {
    (await _prefs).setBool(_keyEnabled, v);
    if (!v) await close();
  }

  Future<String?> get token async => (await _prefs).getString(_keyToken);

  Future<void> setToken(String v) async =>
      (await _prefs).setString(_keyToken, v.trim());

  _GuideSpec _spec({String? token}) => _GuideSpec(token: token);

  /// True when the model file is installed and ready to load.
  Future<bool> isInstalled() async {
    try {
      return await FlutterGemmaPlugin.instance.modelManager
          .isModelInstalled(_spec());
    } catch (e) {
      debugPrint('SlmGuide: isInstalled failed: $e');
      return false;
    }
  }

  Future<void> download({String? token}) async {
    final t = (token ?? await this.token ?? '').trim();
    try {
      await FlutterGemmaPlugin.instance.modelManager.downloadModel(
        _spec(token: t.isEmpty ? null : t),
        token: t.isEmpty ? null : t,
      );
    } catch (e) {
      throw SlmException(friendlyDownloadError(e));
    }
  }

  Stream<int> downloadWithProgress({String? token}) async* {
    final t = (token ?? await this.token ?? '').trim();
    final spec = _spec(token: t.isEmpty ? null : t);
    try {
      await for (final p in FlutterGemmaPlugin.instance.modelManager
          .downloadModelWithProgress(
        spec,
        token: t.isEmpty ? null : t,
      )) {
        yield p.overallProgress.clamp(0, 100);
      }
    } catch (e) {
      throw SlmException(friendlyDownloadError(e));
    }
  }

  Future<SlmUrlCheck> verifyModelUrl({String? token}) async {
    final t = (token ?? await this.token ?? '').trim();
    final client = HttpClient();
    client.connectionTimeout = const Duration(seconds: 15);
    try {
      final uri = Uri.parse(modelUrl);
      final req = await client.openUrl('HEAD', uri);
      if (t.isNotEmpty) req.headers.set('Authorization', 'Bearer $t');
      req.followRedirects = true;
      final res = await req.close().timeout(const Duration(seconds: 20));
      await res.drain<void>();
      if (res.statusCode >= 200 && res.statusCode < 300) {
        return SlmUrlCheck(SlmUrlStatus.ok, res.statusCode, '');
      }
      if (res.statusCode == 401 || res.statusCode == 403) {
        return SlmUrlCheck(SlmUrlStatus.needsToken, res.statusCode, '');
      }
      if (res.statusCode == 404) {
        return SlmUrlCheck(SlmUrlStatus.notFound, res.statusCode, '');
      }
      return SlmUrlCheck(SlmUrlStatus.unknown, res.statusCode, '');
    } on SocketException {
      return const SlmUrlCheck(SlmUrlStatus.networkFail, -1, '');
    } on TimeoutException {
      return const SlmUrlCheck(SlmUrlStatus.networkFail, -1, '');
    } catch (_) {
      return const SlmUrlCheck(SlmUrlStatus.unknown, -1, '');
    } finally {
      client.close(force: true);
    }
  }

  Future<String> sideLoadExpectedPath() async {
    final dir = await getApplicationDocumentsDirectory();
    return '${dir.path}/$sideLoadName';
  }

  Future<SlmSideLoadCheck> validateSideLoad() async {
    try {
      final dir = await getApplicationDocumentsDirectory();
      final file = File('${dir.path}/$sideLoadName');
      if (!await file.exists()) {
        return const SlmSideLoadCheck(false, 0, false);
      }
      final len = await file.length();
      return SlmSideLoadCheck(true, len, len > 100 * 1024 * 1024);
    } catch (_) {
      return const SlmSideLoadCheck(false, 0, false);
    }
  }

  static String formatBytes(int bytes) {
    if (bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    var v = bytes.toDouble();
    var i = 0;
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i++;
    }
    final s = v >= 100 ? v.toStringAsFixed(0) : v.toStringAsFixed(1);
    return '$s ${units[i]}';
  }

  static String friendlyDownloadError(Object e) {
    final s = '$e';
    if (s.contains('401') || s.contains('403')) {
      return 'Download needs a HuggingFace token (gated Gemma repo). Accept the license on huggingface.co, paste a token in Setup, then retry. Detail: $e';
    }
    if (s.contains('404')) {
      return 'Model file not found (Google renamed it). Verify the URL in a browser, update SlmGuideService.modelUrl, then retry. Detail: $e';
    }
    if (s.contains('SocketException') ||
        s.contains('Connection') ||
        s.contains('Timeout') ||
        s.contains('timed out')) {
      return 'Network failed during download (resumable — retry on Wi-Fi). Detail: $e';
    }
    return 'Download failed: $e';
  }

  /// Use a manually placed `guide_model.task` from app documents instead.
  Future<bool> installSideLoaded() async {
    try {
      final dir = await getApplicationDocumentsDirectory();
      final file = File('${dir.path}/$sideLoadName');
      if (!await file.exists()) return false;
      await FlutterGemma.installModel(modelType: ModelType.gemmaIt)
          .fromFile(file.path)
          .install();
      return true;
    } catch (e) {
      debugPrint('SlmGuide: side-load failed: $e');
      return false;
    }
  }

  Future<void> deleteModel() async {
    await close();
    try {
      await FlutterGemmaPlugin.instance.modelManager
          .deleteModel(_spec());
    } catch (e) {
      debugPrint('SlmGuide: delete failed: $e');
    }
  }

  Future<InferenceChat> _ensureChat() async {
    final existing = _chat;
    if (existing != null) return existing;
    if (_warming) throw SlmException('Model is still loading.');
    _warming = true;
    try {
      final model = await FlutterGemmaPlugin.instance.createModel(
        modelType: ModelType.gemmaIt,
        maxTokens: 512,
        preferredBackend: PreferredBackend.gpu,
      );
      final chat = await model.createChat();
      await chat.addQuery(const Message(
        text: _systemPrompt,
        isUser: false,
      ));
      _chat = chat;
      return chat;
    } catch (e) {
      throw SlmException('Could not start offline brain: $e');
    } finally {
      _warming = false;
    }
  }

  /// Ask with FTS5 hits as grounding. Yields text tokens; throws [SlmException].
  Stream<String> ask(String question, List<LocalRuleHit> hits) async* {
    final chat = await _ensureChat();
    await chat.addQuery(Message.text(
      text: buildGuidePrompt(question, hits),
      isUser: true,
    ));
    await for (final event in chat.generateChatResponseAsync()) {
      if (event is TextResponse) yield event.token;
    }
  }

  Future<void> close() async {
    try {
      await _chat?.close();
    } catch (_) {}
    _chat = null;
  }

  void dispose() => close();

  static const _systemPrompt =
      'You are the Pathfinder Guide, a helpful tabletop RPG assistant running '
      'fully offline on a phone. Answer concisely in markdown. '
      'Use the provided rulebook excerpts as your facts and cite them like '
      '[Source Book - Rule Name]. If the excerpts do not cover the question, '
      'say so briefly and answer from general Pathfinder knowledge, clearly '
      'marked as general knowledge. Never invent page numbers.';

  /// Pure prompt builder (unit-tested).
  static String buildGuidePrompt(String question, List<LocalRuleHit> hits) {
    final buf = StringBuffer('Offline rulebook excerpts:\n');
    for (var i = 0; i < hits.length && i < 5; i++) {
      final h = hits[i];
      final content = h.content.replaceAll('\n', ' ').trim();
      final snippet =
          content.length > 400 ? '${content.substring(0, 400)}…' : content;
      buf.write('\n[${h.sourceBook} - ${h.name}] (${h.system})\n$snippet\n');
    }
    buf.write('\nQuestion: $question');
    return buf.toString();
  }
}

class _GuideModelFile implements ModelFile {
  final String? token;
  const _GuideModelFile({this.token});

  @override
  ModelSource get source =>
      ModelSource.network(SlmGuideService.modelUrl, authToken: token);

  @override
  String get filename => 'guide_model.task';

  @override
  String get prefsKey => SlmGuideService._keyModelFile;

  @override
  bool get isRequired => true;

  @override
  String get extension => '.task';
}

class _GuideSpec implements ModelSpec {
  final String? token;
  const _GuideSpec({this.token});

  @override
  ModelManagementType get type => ModelManagementType.inference;

  @override
  String get name => 'Pathfinder Guide (Gemma 3n)';

  @override
  List<ModelFile> get files => [_GuideModelFile(token: token)];

  @override
  ModelReplacePolicy get replacePolicy => ModelReplacePolicy.keep;

  @override
  bool get isValid => files.isNotEmpty && files.any((f) => f.isRequired);
}

class SlmException implements Exception {
  final String message;
  SlmException(this.message);
  @override
  String toString() => message;
}

enum SlmUrlStatus { ok, needsToken, notFound, networkFail, unknown }

class SlmUrlCheck {
  final SlmUrlStatus status;
  final int statusCode;
  final String detail;
  const SlmUrlCheck(this.status, this.statusCode, this.detail);

  String get label {
    switch (status) {
      case SlmUrlStatus.ok:
        return 'Model URL OK ($statusCode) — safe to download.';
      case SlmUrlStatus.needsToken:
        return 'Model URL needs a HuggingFace token ($statusCode). Accept the Gemma license, paste a token, then retry.';
      case SlmUrlStatus.notFound:
        return 'Model URL 404 — Google renamed the file. Open the URL in a browser, find the new .task name, update SlmGuideService.modelUrl.';
      case SlmUrlStatus.networkFail:
        return 'No network to HuggingFace. Check Wi-Fi, then retry.';
      case SlmUrlStatus.unknown:
        return statusCode > 0
            ? 'HuggingFace returned $statusCode. Open the URL in a browser to inspect.'
            : 'Could not reach HuggingFace. Retry on Wi-Fi.';
    }
  }
}

class SlmSideLoadCheck {
  final bool exists;
  final int sizeBytes;
  final bool looksValid;
  const SlmSideLoadCheck(this.exists, this.sizeBytes, this.looksValid);
}
