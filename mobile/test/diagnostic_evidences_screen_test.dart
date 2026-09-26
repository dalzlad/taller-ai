import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/api_client.dart';
import 'package:mobile/screens/diagnostic_analysis_screen.dart';
import 'package:mobile/screens/diagnostic_created_screen.dart';
import 'package:mobile/screens/diagnostic_evidences_screen.dart';

const _lockedDetail =
    'No se pueden modificar las evidencias porque el diagnóstico ya tiene un análisis de IA.';

Map<String, dynamic> _evidence(
  int id,
  String fileName, {
  String type = 'IMAGE',
  String mimeType = 'image/jpeg',
  int size = 2048,
  String? description,
}) =>
    {
      'id': id,
      'diagnostic_id': 5,
      'evidence_type': type,
      'file_name': fileName,
      'mime_type': mimeType,
      'file_size': size,
      'description': description,
      'created_at': '2026-09-26T10:00:00Z',
    };

const _analysis = {
  'summary': 'Posible falla de encendido; se requiere verificación mecánica.',
  'vehicle_state': 'en_uso',
  'observations': {'audio': [], 'image': []},
  'possible_causes': [],
  'recommended_tests': [],
  'safety_warnings': [],
  'limitations': ['La evaluación es preliminar y requiere confirmación física por un mecánico.'],
};

http.Response _json(Object body, [int status = 200]) => http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

/// In-memory stand-in for the evidence and analysis endpoints of diagnostic #5.
class _FakeBackend {
  _FakeBackend({List<Map<String, dynamic>> evidences = const [], this.analyzed = false})
      : evidences = [...evidences] {
    apiHttpClient = MockClient((request) async {
      requests.add(request);
      return _handle(request);
    });
  }

  final List<Map<String, dynamic>> evidences;
  bool analyzed;
  http.Response? listError;
  http.Response? uploadError;
  http.Response? deleteError;
  Completer<void>? listGate;
  final requests = <http.Request>[];

  Iterable<String> get calls => requests.map((r) => '${r.method} ${r.url.path}');

  Future<http.Response> _handle(http.Request request) async {
    final path = request.url.path;
    switch ((request.method, path)) {
      case ('GET', '/diagnostics/5/evidences'):
        await listGate?.future;
        return listError ?? _json(evidences);
      case ('GET', '/diagnostics/5/analysis'):
        return analyzed
            ? _json({'provider': 'stub', 'model': null, 'result': _analysis})
            : _json({'detail': 'AI analysis not found'}, 404);
      case ('POST', '/diagnostics/5/evidences'):
        if (uploadError != null) return uploadError!;
        final body = latin1.decode(request.bodyBytes);
        final name = RegExp(r'filename="([^"]+)"').firstMatch(body)!.group(1)!;
        final description =
            RegExp(r'name="description"\r\n\r\n([^\r]*)\r\n').firstMatch(body)?.group(1);
        final created = _evidence(100 + evidences.length, name, description: description);
        evidences.add(created);
        return _json(created, 201);
      case ('POST', '/diagnostics/5/analyze'):
        analyzed = true;
        return _json(_analysis);
    }
    if (request.method == 'DELETE' && path.startsWith('/evidences/')) {
      if (deleteError != null) return deleteError!;
      final id = int.parse(path.split('/').last);
      evidences.removeWhere((e) => e['id'] == id);
      return http.Response('', 204);
    }
    return _json({'detail': 'Not Found'}, 404);
  }
}

final _jpeg = PickedEvidenceFile(
  name: 'motor.jpg',
  bytes: Uint8List.fromList([0xff, 0xd8, 0xff, 0x00]),
  mimeType: 'image/jpeg',
);

/// Uses a tall surface so the whole screen is visible.
Future<void> _pumpEvidences(WidgetTester tester, {PickedEvidenceFile? picked}) {
  tester.view.physicalSize = const Size(800, 1600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  return tester.pumpWidget(MaterialApp(
    home: DiagnosticEvidencesScreen(diagnosticId: 5, pickFile: (_) async => picked),
  ));
}

Future<void> _selectAndUpload(WidgetTester tester, {String? description}) async {
  await tester.tap(find.text('Agregar imagen'));
  await tester.pumpAndSettle();
  if (description != null) {
    await tester.enterText(find.widgetWithText(TextField, 'Descripción (opcional)'), description);
  }
  await tester.tap(find.text('Subir evidencia'));
  await tester.pumpAndSettle();
}

Future<void> _deleteFirst(WidgetTester tester) async {
  await tester.tap(find.byTooltip('Eliminar').first);
  await tester.pumpAndSettle();
  await tester.tap(find.widgetWithText(TextButton, 'Eliminar'));
  await tester.pumpAndSettle();
}

void _expectReadOnly() {
  expect(find.text('Agregar imagen'), findsNothing);
  expect(find.text('Agregar audio'), findsNothing);
  expect(find.byTooltip('Eliminar'), findsNothing);
  expect(find.textContaining('ya tiene un análisis de IA'), findsWidgets);
  expect(find.text('Ver análisis de IA'), findsOneWidget);
}

void main() {
  tearDown(() => apiHttpClient = http.Client());

  group('lista', () {
    testWidgets('muestra un indicador mientras carga', (tester) async {
      final backend = _FakeBackend()..listGate = Completer<void>();
      await _pumpEvidences(tester);
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      backend.listGate!.complete();
      await tester.pumpAndSettle();

      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('muestra tipo, nombre, tamaño y descripción', (tester) async {
      _FakeBackend(evidences: [
        _evidence(1, 'motor.jpg', size: 2048, description: 'Zona del motor'),
        _evidence(2, 'ruido.mp3', type: 'AUDIO', mimeType: 'audio/mpeg', size: 3 * 1024 * 1024),
      ]);
      await _pumpEvidences(tester);
      await tester.pumpAndSettle();

      expect(find.text('motor.jpg'), findsOneWidget);
      expect(find.text('Imagen · 2.0 KB\nZona del motor'), findsOneWidget);
      expect(find.text('ruido.mp3'), findsOneWidget);
      expect(find.text('Audio · 3.0 MB'), findsOneWidget);
      expect(find.byTooltip('Eliminar'), findsNWidgets(2));
      expect(find.text('Analizar con IA'), findsOneWidget);
    });

    testWidgets('estado vacío', (tester) async {
      _FakeBackend();
      await _pumpEvidences(tester);
      await tester.pumpAndSettle();

      expect(find.textContaining('Aún no hay evidencias'), findsOneWidget);
      expect(find.text('Agregar imagen'), findsOneWidget);
      expect(find.text('Agregar audio'), findsOneWidget);
    });

    testWidgets('un error al cargar (5xx) se muestra legible y se puede reintentar', (tester) async {
      final backend = _FakeBackend()..listError = _json({'detail': 'Internal Server Error'}, 500);
      await _pumpEvidences(tester);
      await tester.pumpAndSettle();

      expect(find.textContaining('Error del servidor'), findsOneWidget);
      expect(find.textContaining('Error HTTP 500: Internal Server Error'), findsOneWidget);

      backend.listError = null;
      await tester.tap(find.text('Reintentar'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Aún no hay evidencias'), findsOneWidget);
      expect(backend.calls.where((c) => c == 'GET /diagnostics/5/evidences'), hasLength(2));
    });
  });

  group('subir', () {
    testWidgets('selección y subida exitosa: aparece en la lista y se limpia la selección',
        (tester) async {
      final backend = _FakeBackend();
      await _pumpEvidences(tester, picked: _jpeg);
      await tester.pumpAndSettle();

      await tester.tap(find.text('Agregar imagen'));
      await tester.pumpAndSettle();
      expect(find.text('Seleccionado: motor.jpg (4 B)'), findsOneWidget);

      await tester.enterText(find.widgetWithText(TextField, 'Descripción (opcional)'), 'Zona del motor');
      await tester.tap(find.text('Subir evidencia'));
      await tester.pumpAndSettle();

      final upload = backend.requests.singleWhere((r) => r.method == 'POST');
      expect(upload.headers['content-type'], startsWith('multipart/form-data'));
      final body = latin1.decode(upload.bodyBytes);
      expect(body, contains('filename="motor.jpg"'));
      expect(body, contains('content-type: image/jpeg'));
      expect(body, contains('Zona del motor'));

      expect(find.text('motor.jpg'), findsOneWidget);
      expect(find.text('Imagen · 2.0 KB\nZona del motor'), findsOneWidget);
      expect(find.textContaining('Seleccionado:'), findsNothing);
      expect(find.text('Subir evidencia'), findsNothing);
      expect(backend.calls.where((c) => c == 'GET /diagnostics/5/evidences'), hasLength(2));
    });

    testWidgets('un archivo con formato no admitido no se sube', (tester) async {
      final backend = _FakeBackend();
      await _pumpEvidences(
        tester,
        picked: PickedEvidenceFile(name: 'nota.m4a', bytes: Uint8List(4), mimeType: null),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Agregar audio'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Formato no admitido: "nota.m4a"'), findsOneWidget);
      expect(find.text('Subir evidencia'), findsNothing);
      expect(backend.requests.where((r) => r.method == 'POST'), isEmpty);
    });

    testWidgets('413: archivo demasiado grande', (tester) async {
      _FakeBackend().uploadError = _json({'detail': 'File exceeds size limit'}, 413);
      await _pumpEvidences(tester, picked: _jpeg);
      await tester.pumpAndSettle();

      await _selectAndUpload(tester);

      expect(find.textContaining('supera el tamaño máximo'), findsOneWidget);
      expect(find.textContaining('Error HTTP 413: File exceeds size limit'), findsOneWidget);
      // The selection is kept so the user can cancel it or pick another file.
      expect(find.text('Seleccionado: motor.jpg (4 B)'), findsOneWidget);
      expect(find.text('motor.jpg'), findsNothing);
    });

    testWidgets('415: formato rechazado por el backend', (tester) async {
      _FakeBackend().uploadError = _json({'detail': 'File content does not match type'}, 415);
      await _pumpEvidences(tester, picked: _jpeg);
      await tester.pumpAndSettle();

      await _selectAndUpload(tester);

      expect(find.textContaining('Formato no admitido o el contenido no corresponde'), findsOneWidget);
      expect(find.textContaining('Error HTTP 415: File content does not match type'), findsOneWidget);
    });

    testWidgets('409: el diagnóstico ya fue analizado y la pantalla pasa a solo lectura',
        (tester) async {
      _FakeBackend().uploadError = _json({'detail': _lockedDetail}, 409);
      await _pumpEvidences(tester, picked: _jpeg);
      await tester.pumpAndSettle();

      await _selectAndUpload(tester);

      expect(find.text('Error HTTP 409: $_lockedDetail'), findsOneWidget);
      expect(find.textContaining('Seleccionado:'), findsNothing);
      _expectReadOnly();
    });
  });

  group('eliminar', () {
    testWidgets('eliminación exitosa tras confirmar', (tester) async {
      final backend = _FakeBackend(evidences: [_evidence(1, 'motor.jpg')]);
      await _pumpEvidences(tester);
      await tester.pumpAndSettle();

      await _deleteFirst(tester);

      expect(backend.calls, contains('DELETE /evidences/1'));
      expect(find.text('motor.jpg'), findsNothing);
      expect(find.textContaining('Aún no hay evidencias'), findsOneWidget);
    });

    testWidgets('cancelar la confirmación no elimina nada', (tester) async {
      final backend = _FakeBackend(evidences: [_evidence(1, 'motor.jpg')]);
      await _pumpEvidences(tester);
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Eliminar'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancelar'));
      await tester.pumpAndSettle();

      expect(backend.requests.where((r) => r.method == 'DELETE'), isEmpty);
      expect(find.text('motor.jpg'), findsOneWidget);
    });

    testWidgets('409: la evidencia se conserva y la pantalla pasa a solo lectura', (tester) async {
      _FakeBackend(evidences: [_evidence(1, 'motor.jpg')]).deleteError =
          _json({'detail': _lockedDetail}, 409);
      await _pumpEvidences(tester);
      await tester.pumpAndSettle();

      await _deleteFirst(tester);

      expect(find.text('Error HTTP 409: $_lockedDetail'), findsOneWidget);
      expect(find.text('motor.jpg'), findsOneWidget);
      _expectReadOnly();
    });
  });

  testWidgets('con análisis existente la pantalla es de solo lectura', (tester) async {
    _FakeBackend(evidences: [_evidence(1, 'motor.jpg')], analyzed: true);
    await _pumpEvidences(tester, picked: _jpeg);
    await tester.pumpAndSettle();

    expect(find.text('motor.jpg'), findsOneWidget);
    _expectReadOnly();
    expect(find.text('Analizar con IA'), findsNothing);
    final viewAnalysis = tester.widget<ButtonStyleButton>(
      find.ancestor(of: find.text('Ver análisis de IA'), matching: find.bySubtype<ButtonStyleButton>()),
    );
    expect(viewAnalysis.onPressed, isNotNull);
  });

  group('navegación', () {
    testWidgets('diagnóstico creado → evidencias (sin lanzar el análisis)', (tester) async {
      final backend = _FakeBackend();
      await tester.pumpWidget(
        const MaterialApp(home: DiagnosticCreatedScreen(diagnosticId: 5, status: 'CREATED')),
      );

      await tester.tap(find.text('Continuar a evidencias'));
      await tester.pumpAndSettle();

      expect(find.byType(DiagnosticEvidencesScreen), findsOneWidget);
      expect(find.text('Evidencias · Diagnóstico #5'), findsOneWidget);
      expect(backend.calls, isNot(contains('POST /diagnostics/5/analyze')));
    });

    testWidgets('evidencias → análisis, y al volver queda en solo lectura', (tester) async {
      final backend = _FakeBackend(evidences: [_evidence(1, 'motor.jpg')]);
      await _pumpEvidences(tester);
      await tester.pumpAndSettle();
      expect(backend.calls, isNot(contains('POST /diagnostics/5/analyze')));

      await tester.tap(find.text('Analizar con IA'));
      await tester.pumpAndSettle();

      expect(find.byType(DiagnosticAnalysisScreen), findsOneWidget);
      expect(backend.calls, contains('POST /diagnostics/5/analyze'));
      expect(find.textContaining('Posible falla de encendido'), findsOneWidget);

      await tester.pageBack();
      await tester.pumpAndSettle();

      expect(find.byType(DiagnosticEvidencesScreen), findsOneWidget);
      _expectReadOnly();
    });
  });

  test('describeEvidenceError explica 404, 5xx y errores de conexión sin ocultar el detalle', () {
    expect(
      describeEvidenceError(ApiException(404, 'Evidence not found')),
      'El diagnóstico o la evidencia ya no existe.\nError HTTP 404: Evidence not found',
    );
    expect(
      describeEvidenceError(ApiException(503, 'Service Unavailable')),
      startsWith('Error del servidor.'),
    );
    expect(
      describeEvidenceError(ApiException(409, _lockedDetail)),
      'Error HTTP 409: $_lockedDetail',
    );
    expect(
      describeEvidenceError(ApiException(null, 'No se pudo conectar a http://localhost:8000')),
      'No se pudo conectar a http://localhost:8000',
    );
  });
}
