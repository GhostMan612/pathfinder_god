// ignore_for_file: unused_local_variable, avoid_print
import 'dart:io';
import 'package:yaml/yaml.dart';

void main() async {
  stdout.writeln('Generating API models from OpenAPI spec...');

  final specPath = '../shared/openapi.yaml';
  final outputFile = File('lib/api/models.dart.gen');

  if (!await File(specPath).exists()) {
    stderr.writeln('OpenAPI spec not found at $specPath');
    exit(1);
  }

  final yamlString = await File(specPath).readAsString();
  final spec = loadYaml(yamlString) as Map;
  final schemas = (spec['components'] as Map?)?['schemas'] as Map?;

  if (schemas == null || schemas.isEmpty) {
    stderr.writeln('No schemas found');
    exit(1);
  }

  stdout.writeln('Found ${schemas.length} schemas');

  final buffer = StringBuffer();
  buffer.writeln('// ============================================================');
  buffer.writeln('// As Above, So Below. As Within, So Without.');
  buffer.writeln('// The Future Dictates the Past and the Past is Always Present.');
  buffer.writeln('// ============================================================');
  buffer.writeln('');
  buffer.writeln('/// Dart mirrors of shared/openapi.yaml.');
  buffer.writeln('/// GENERATED CODE - DO NOT EDIT MANUALLY');
  buffer.writeln('/// Run: dart run generate_models.dart');
  buffer.writeln('library;');
  buffer.writeln('');

  for (final name in schemas.keys) {
    buffer.writeln(generateModel(name as String, schemas[name] as Map));
    buffer.writeln('');
  }

  buffer.writeln('/// Frame from WebSocket /stream (not in OpenAPI, hub extension).');
  buffer.writeln('class StreamEvent {');
  buffer.writeln('  final String type;');
  buffer.writeln('  final String? backend;');
  buffer.writeln('  final String? mode;');
  buffer.writeln('  final String? edition;');
  buffer.writeln('  final String? text;');
  buffer.writeln('  final String? message;');
  buffer.writeln('  final List<RuleHit> sources;');
  buffer.writeln('  const StreamEvent({required this.type, this.backend, this.mode, this.edition, this.text, this.message, this.sources = const []});');
  buffer.writeln('  factory StreamEvent.fromJson(Map<String, dynamic> j) => StreamEvent(type: j[\'type\'] as String? ?? \'chunk\', backend: j[\'backend\'] as String?, mode: j[\'mode\'] as String?, edition: j[\'edition\'] as String?, text: j[\'text\'] as String?, message: j[\'message\'] as String?, sources: (j[\'sources\'] as List?)?.map((e) => RuleHit.fromJson(e as Map<String, dynamic>)).toList() ?? const []);');
  buffer.writeln('  Map<String, dynamic> toJson() => {\'type\': type, \'backend\': backend, \'mode\': mode, \'edition\': edition, \'text\': text, \'message\': message, \'sources\': sources.map((e) => e.toJson()).toList()};');
  buffer.writeln('}');

  await outputFile.writeAsString(buffer.toString());
  stdout.writeln('Wrote ${outputFile.path} (${schemas.length} schemas + StreamEvent)');
}

String toCamelCase(String input) => input.replaceAllMapped(RegExp(r'[_-]([a-z])'), (m) => m.group(1)!.toUpperCase());

String generateModel(String name, Map schema) {
  final properties = schema['properties'] as Map?;
  final required = (schema['required'] as List?)?.cast<String>() ?? [];
  final buffer = StringBuffer();
  buffer.writeln('class $name {');
  if (properties != null) {
    for (final e in properties.entries) {
      final dartType = mapSchemaToDartType(e.value as Map);
      final field = toCamelCase(e.key as String);
      final req = required.contains(e.key);
      buffer.writeln('  final $dartType${req ? '' : '?'} $field;');
    }
  }
  buffer.writeln('  const $name({');
  if (properties != null) {
    for (final e in properties.entries) {
      final field = toCamelCase(e.key as String);
      final req = required.contains(e.key);
      buffer.writeln(req ? '    required this.$field,' : '    this.$field,');
    }
  }
  buffer.writeln('  });');
  buffer.writeln('  $name copyWith({');
  if (properties != null) {
    for (final e in properties.entries) {
      final dartType = mapSchemaToDartType(e.value as Map);
      final field = toCamelCase(e.key as String);
      buffer.writeln('    $dartType? $field,');
    }
  }
  buffer.writeln('  }) => $name(');
  if (properties != null) {
    for (final e in properties.entries) {
      final field = toCamelCase(e.key as String);
      buffer.writeln('      $field: $field ?? this.$field,');
    }
  }
  buffer.writeln('  );');
  buffer.writeln('  Map<String, dynamic> toJson() => {');
  if (properties != null) {
    for (final e in properties.entries) {
      final prop = e.key as String;
      final field = toCamelCase(prop);
      buffer.writeln('    \'$prop\': $field,');
    }
  }
  buffer.writeln('  };');
  buffer.writeln('  factory $name.fromJson(Map<String, dynamic> json) => $name(');
  if (properties != null) {
    for (final e in properties.entries) {
      final prop = e.key as String;
      final field = toCamelCase(prop);
      final dartType = mapSchemaToDartType(e.value as Map);
      final req = required.contains(e.key);
      if (dartType.startsWith('List<')) {
        final inner = dartType.substring(5, dartType.length - 1);
        if (['String', 'int', 'double', 'bool'].contains(inner)) {
          buffer.writeln('      $field: (json[\'$prop\'] as List?)?.cast<$inner>()${req ? ' ?? const []' : ''},');
        } else {
          buffer.writeln('      $field: (json[\'$prop\'] as List?)?.map((e) => $inner.fromJson(e as Map<String, dynamic>)).toList()${req ? ' ?? const []' : ''},');
        }
      } else if (['String', 'int', 'double', 'bool'].contains(dartType)) {
        buffer.writeln('      $field: json[\'$prop\'] as $dartType${req ? '' : '?'},');
      } else if (dartType == 'dynamic' || dartType == 'Map<String, dynamic>') {
        buffer.writeln('      $field: json[\'$prop\'],');
      } else {
        buffer.writeln('      $field: json[\'$prop\'] != null ? $dartType.fromJson(json[\'$prop\'] as Map<String, dynamic>) : null,');
      }
    }
  }
  buffer.writeln('  );');
  buffer.writeln('}');
  return buffer.toString();
}

String mapSchemaToDartType(Map schema) {
  final ref = schema[r'$ref'] as String?;
  if (ref != null) return ref.split('/').last;
  final type = schema['type'] as String?;
  final fmt = schema['format'] as String?;
  switch (type) {
    case 'string':
      if (fmt == 'date-time' || fmt == 'date') return 'DateTime';
      return 'String';
    case 'integer':
      return 'int';
    case 'number':
      return 'double';
    case 'boolean':
      return 'bool';
    case 'array':
      final items = schema['items'] as Map?;
      if (items != null) return 'List<${mapSchemaToDartType(items)}>';
      return 'List<dynamic>';
    case 'object':
      return 'Map<String, dynamic>';
    default:
      final r2 = schema[r'$ref'] as String?;
      if (r2 != null) return r2.split('/').last;
      return 'dynamic';
  }
}
