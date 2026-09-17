// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:convert';

/// A single campaign: one identifier unifying characters, maps, encounters.
class CampaignModel {
  final String id;
  final String name;
  final String description;
  final List<String> sessionNotes;
  final DateTime updatedAt;

  const CampaignModel({
    required this.id,
    required this.name,
    this.description = '',
    this.sessionNotes = const [],
    required this.updatedAt,
  });

  CampaignModel withNote(String note) => CampaignModel(
        id: id,
        name: name,
        description: description,
        sessionNotes: [...sessionNotes, note],
        updatedAt: DateTime.now().toUtc(),
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'description': description,
        'sessionNotes': sessionNotes,
        'updatedAt': updatedAt.toIso8601String(),
      };

  factory CampaignModel.fromJson(Map<String, dynamic> json) => CampaignModel(
        id: json['id'] as String,
        name: json['name'] as String? ?? 'Untitled Campaign',
        description: json['description'] as String? ?? '',
        sessionNotes: (json['sessionNotes'] as List<dynamic>? ?? [])
            .map((e) => e as String)
            .toList(),
        updatedAt: DateTime.tryParse(json['updatedAt'] as String? ?? '') ??
            DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
      );

  String toJsonString() => jsonEncode(toJson());

  factory CampaignModel.fromJsonString(String source) =>
      CampaignModel.fromJson(jsonDecode(source) as Map<String, dynamic>);
}
