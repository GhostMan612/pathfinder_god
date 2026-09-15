// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/foundation.dart';
import 'package:flutter_gemma/core/domain/model_source.dart';
import 'package:flutter_gemma/flutter_gemma.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'dart:io';

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

  /// Download the model (Wi-Fi recommended, ~2GB, resumable). Throws on error.
  Future<void> download({String? token}) async {
    final t = (token ?? await this.token ?? '').trim();
    try {
      await FlutterGemmaPlugin.instance.modelManager.downloadModel(
        _spec(token: t.isEmpty ? null : t),
        token: t.isEmpty ? null : t,
      );
    } catch (e) {
      throw SlmException('Download failed: $e');
    }
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
