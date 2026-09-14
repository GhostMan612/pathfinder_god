// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

/// Dart mirrors of shared/openapi.yaml.
/// Single source of truth is the YAML; this file mirrors it manually.
/// To regenerate, run: dart run generate_models.dart
/// The script writes to lib/api/models.dart.gen — diff it, then copy if clean.
library;

class RuleHit {
  final String name;
  final String content;
  final String category;
  final String sourceBook;
  final String system;
  const RuleHit({required this.name, required this.content, this.category = '', this.sourceBook = '', this.system = ''});
  factory RuleHit.fromJson(Map<String, dynamic> j) => RuleHit(name: j['name'] as String? ?? '', content: j['content'] as String? ?? '', category: j['category'] as String? ?? '', sourceBook: j['source_book'] as String? ?? j['sourceBook'] as String? ?? '', system: j['system'] as String? ?? '');
  Map<String, dynamic> toJson() => {'name': name, 'content': content, 'category': category, 'source_book': sourceBook, 'system': system};
}

class HubHealth {
  final String status;
  final String version;
  final String ollamaModel;
  final List<String> databasesFound;
  const HubHealth({this.status = 'ok', required this.version, required this.ollamaModel, this.databasesFound = const []});
  factory HubHealth.fromJson(Map<String, dynamic> j) => HubHealth(status: j['status'] as String? ?? 'ok', version: j['version'] as String? ?? '', ollamaModel: j['ollama_model'] as String? ?? j['ollamaModel'] as String? ?? '', databasesFound: (j['databases_found'] as List?)?.cast<String>() ?? (j['databasesFound'] as List?)?.cast<String>() ?? const []);
  Map<String, dynamic> toJson() => {'status': status, 'version': version, 'ollama_model': ollamaModel, 'databases_found': databasesFound};
}

class AskRequest {
  final String query;
  final String edition;
  final String? mode;
  final List<List<String>> history;
  const AskRequest({required this.query, this.edition = 'both', this.mode, this.history = const []});
  Map<String, dynamic> toJson() => {'query': query, 'edition': edition, 'mode': mode, 'history': history};
}

class AskResponse {
  final String answer;
  final String backend;
  final String edition;
  final String mode;
  final List<RuleHit> sources;
  const AskResponse({required this.answer, required this.backend, required this.edition, required this.mode, this.sources = const []});
  factory AskResponse.fromJson(Map<String, dynamic> j) => AskResponse(answer: j['answer'] as String? ?? '', backend: j['backend'] as String? ?? '', edition: j['edition'] as String? ?? 'both', mode: j['mode'] as String? ?? '', sources: (j['sources'] as List?)?.map((e) => RuleHit.fromJson(e as Map<String, dynamic>)).toList() ?? const []);
  Map<String, dynamic> toJson() => {'answer': answer, 'backend': backend, 'edition': edition, 'mode': mode, 'sources': sources.map((e) => e.toJson()).toList()};
}

class GenerateRequest {
  final String prompt;
  final String edition;
  const GenerateRequest({required this.prompt, this.edition = 'both'});
  Map<String, dynamic> toJson() => {'prompt': prompt, 'edition': edition};
}

class CampaignNote {
  final String prompt;
  final String response;
  const CampaignNote({required this.prompt, required this.response});
  factory CampaignNote.fromJson(Map<String, dynamic> j) => CampaignNote(prompt: j['prompt'] as String? ?? '', response: j['response'] as String? ?? '');
  Map<String, dynamic> toJson() => {'prompt': prompt, 'response': response};
}

class CampaignState {
  final List<Map<String, dynamic>> party;
  final List<CampaignNote> notes;
  const CampaignState({this.party = const [], this.notes = const []});
  factory CampaignState.fromJson(Map<String, dynamic> j) => CampaignState(party: (j['party'] as List?)?.cast<Map<String, dynamic>>() ?? const [], notes: (j['notes'] as List?)?.map((e) => CampaignNote.fromJson(e as Map<String, dynamic>)).toList() ?? const []);
  Map<String, dynamic> toJson() => {'party': party, 'notes': notes.map((e) => e.toJson()).toList()};
}

class RulesSearchResponse {
  final String query;
  final String edition;
  final List<RuleHit> results;
  const RulesSearchResponse({required this.query, required this.edition, required this.results});
  factory RulesSearchResponse.fromJson(Map<String, dynamic> j) => RulesSearchResponse(query: j['query'] as String? ?? '', edition: j['edition'] as String? ?? 'both', results: (j['results'] as List?)?.map((e) => RuleHit.fromJson(e as Map<String, dynamic>)).toList() ?? const []);
}

class StreamEvent {
  final String type;
  final String? backend;
  final String? mode;
  final String? edition;
  final String? text;
  final String? message;
  final List<RuleHit> sources;
  const StreamEvent({required this.type, this.backend, this.mode, this.edition, this.text, this.message, this.sources = const []});
  factory StreamEvent.fromJson(Map<String, dynamic> j) => StreamEvent(type: j['type'] as String? ?? 'chunk', backend: j['backend'] as String?, mode: j['mode'] as String?, edition: j['edition'] as String?, text: j['text'] as String?, message: j['message'] as String?, sources: (j['sources'] as List?)?.map((e) => RuleHit.fromJson(e as Map<String, dynamic>)).toList() ?? const []);
  Map<String, dynamic> toJson() => {'type': type, 'backend': backend, 'mode': mode, 'edition': edition, 'text': text, 'message': message, 'sources': sources.map((e) => e.toJson()).toList()};
}

class ValidationError {
  final List<dynamic> loc;
  final String msg;
  final String type;
  const ValidationError({required this.loc, required this.msg, required this.type});
  factory ValidationError.fromJson(Map<String, dynamic> j) => ValidationError(loc: j['loc'] as List? ?? const [], msg: j['msg'] as String? ?? '', type: j['type'] as String? ?? '');
}

class HTTPValidationError {
  final List<ValidationError> detail;
  const HTTPValidationError({this.detail = const []});
  factory HTTPValidationError.fromJson(Map<String, dynamic> j) => HTTPValidationError(detail: (j['detail'] as List?)?.map((e) => ValidationError.fromJson(e as Map<String, dynamic>)).toList() ?? const []);
}
