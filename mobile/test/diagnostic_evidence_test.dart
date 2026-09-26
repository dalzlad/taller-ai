import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/api_client.dart';
import 'package:mobile/models/diagnostic_evidence.dart';

const _evidence = {
  'id': 12,
  'diagnostic_id': 5,
  'evidence_type': 'IMAGE',
  'file_name': 'motor.jpg',
  'mime_type': 'image/jpeg',
  'file_size': 4,
  'description': 'Zona del motor',
  'created_at': '2026-09-26T10:00:00Z',
};

const _lockedDetail =
    'No se pueden modificar las evidencias porque el diagnóstico ya tiene un análisis de IA.';

final _jpegBytes = [0xff, 0xd8, 0xff, 0x00];

http.Response _json(Object body, [int status = 200]) => http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

List<http.Request> _mockBackend(FutureOr<http.Response> Function(http.Request) handler) {
  final requests = <http.Request>[];
  apiHttpClient = MockClient((request) async {
    requests.add(request);
    return handler(request);
  });
  return requests;
}

Future<DiagnosticEvidence> _uploadJpeg({String? description}) => uploadEvidence(
      5,
      bytes: _jpegBytes,
      fileName: 'motor.jpg',
      mimeType: 'image/jpeg',
      description: description,
    );

Matcher _apiError(int statusCode, String message) => isA<ApiException>()
    .having((e) => e.statusCode, 'statusCode', statusCode)
    .having((e) => e.message, 'message', message);

void main() {
  tearDown(() => apiHttpClient = http.Client());

  test('DiagnosticEvidence.fromJson interpreta la respuesta del backend', () {
    final evidence = DiagnosticEvidence.fromJson(_evidence);

    expect(evidence.id, 12);
    expect(evidence.diagnosticId, 5);
    expect(evidence.evidenceType, 'IMAGE');
    expect(evidence.fileName, 'motor.jpg');
    expect(evidence.mimeType, 'image/jpeg');
    expect(evidence.fileSize, 4);
    expect(evidence.description, 'Zona del motor');
    expect(evidence.createdAt, DateTime.utc(2026, 9, 26, 10));

    final withoutDescription = DiagnosticEvidence.fromJson({..._evidence, 'description': null});
    expect(withoutDescription.description, isNull);
  });

  group('uploadEvidence', () {
    test('envía multipart/form-data con el archivo y su content type', () async {
      final requests = _mockBackend((_) => _json(_evidence, 201));

      final evidence = await _uploadJpeg(description: '  Zona del motor  ');

      final request = requests.single;
      expect(request.method, 'POST');
      expect(request.url.toString(), '$backendBaseUrl/diagnostics/5/evidences');
      expect(request.headers['content-type'], startsWith('multipart/form-data; boundary='));
      final body = latin1.decode(request.bodyBytes);
      expect(body, contains('content-disposition: form-data; name="file"; filename="motor.jpg"'));
      expect(body, contains('content-type: image/jpeg'));
      expect(body, contains(latin1.decode(_jpegBytes)));
      expect(body, contains('content-disposition: form-data; name="description"'));
      expect(body, contains('Zona del motor'));
      expect(body, isNot(contains('  Zona del motor  ')));

      expect(evidence.id, 12);
      expect(evidence.fileName, 'motor.jpg');
    });

    test('omite la descripción si viene vacía (el backend la trata como opcional)', () async {
      final requests = _mockBackend((_) => _json(_evidence, 201));

      await _uploadJpeg(description: '   ');

      expect(latin1.decode(requests.single.bodyBytes), isNot(contains('name="description"')));
    });

    test('409: el diagnóstico ya tiene análisis', () async {
      _mockBackend((_) => _json({'detail': _lockedDetail}, 409));

      await expectLater(_uploadJpeg(), throwsA(_apiError(409, _lockedDetail)));
    });

    test('413: archivo demasiado grande', () async {
      _mockBackend((_) => _json({'detail': 'File exceeds size limit'}, 413));

      await expectLater(_uploadJpeg(), throwsA(_apiError(413, 'File exceeds size limit')));
    });

    test('415: tipo de archivo no soportado', () async {
      _mockBackend((_) => _json({'detail': 'Unsupported file type'}, 415));

      await expectLater(_uploadJpeg(), throwsA(_apiError(415, 'Unsupported file type')));
    });
  });

  group('deleteEvidence', () {
    test('acepta 204 No Content', () async {
      final requests = _mockBackend((_) => http.Response('', 204));

      await deleteEvidence(12);

      expect(requests.single.method, 'DELETE');
      expect(requests.single.url.toString(), '$backendBaseUrl/evidences/12');
    });

    test('409: el diagnóstico ya tiene análisis', () async {
      _mockBackend((_) => _json({'detail': _lockedDetail}, 409));

      await expectLater(deleteEvidence(12), throwsA(_apiError(409, _lockedDetail)));
    });

    test('404: evidencia inexistente', () async {
      _mockBackend((_) => _json({'detail': 'Evidence not found'}, 404));

      await expectLater(deleteEvidence(99), throwsA(_apiError(404, 'Evidence not found')));
    });
  });
}
