import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/api_client.dart';
import 'package:mobile/models/diagnostic_analysis.dart';
import 'package:mobile/screens/diagnostic_analysis_screen.dart';

const _analysis = {
  'summary': 'Posible falla de encendido; se requiere verificación mecánica.',
  'vehicle_state': 'en_uso',
  'observations': {
    'audio': ['Golpeteo rítmico al acelerar.'],
    'image': [],
  },
  'possible_causes': [
    {
      'cause': 'Bujía en mal estado',
      'confidence': 0.62,
      'reasoning': 'El golpeteo es compatible con una falla de encendido.',
      'based_on': ['audio'],
    },
  ],
  'recommended_tests': ['Revisar bujías y bobinas.'],
  'safety_warnings': ['No operar el vehículo si hay humo.'],
  'limitations': ['La evaluación es preliminar y requiere confirmación física por un mecánico.'],
};

Map<String, Object?> _persisted({String provider = 'gemini', String? model = 'gemini-2.0-flash'}) => {
      'diagnostic_id': 5,
      'provider': provider,
      'model': model,
      'schema_version': 1,
      'generated_at': '2026-09-26T10:00:00Z',
      'result': _analysis,
    };

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

/// Serves the analysis on POST and [metadata] (or a 404) on GET.
http.Response Function(http.Request) _backend({Object? metadata}) => (request) {
      if (request.method == 'POST') return _json(_analysis);
      return metadata == null
          ? _json({'detail': 'AI analysis not found'}, 404)
          : _json(metadata);
    };

/// Uses a tall surface so the whole (lazily built) analysis list is on screen.
Future<void> _pumpAnalysis(WidgetTester tester) {
  tester.view.physicalSize = const Size(800, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  return tester.pumpWidget(
    const MaterialApp(home: DiagnosticAnalysisScreen(diagnosticId: 5)),
  );
}

void main() {
  tearDown(() => apiHttpClient = http.Client());

  test('DiagnosticAnalysis.fromJson interpreta la respuesta del backend', () {
    final analysis = DiagnosticAnalysis.fromJson(_analysis);

    expect(analysis.vehicleState, 'en_uso');
    expect(analysis.audioObservations, ['Golpeteo rítmico al acelerar.']);
    expect(analysis.imageObservations, isEmpty);
    expect(analysis.possibleCauses.single.confidence, 0.62);
    expect(analysis.possibleCauses.single.basedOn, ['audio']);
    expect(analysis.safetyWarnings, hasLength(1));

    final metadata = AnalysisMetadata.fromJson(_persisted(provider: 'stub', model: null));
    expect((metadata.provider, metadata.model), ('stub', null));
  });

  testWidgets('muestra el análisis completo y el proveedor/modelo', (tester) async {
    final requests = _mockBackend(_backend(metadata: _persisted()));
    await _pumpAnalysis(tester);
    await tester.pumpAndSettle();

    expect(requests.map((r) => '${r.method} ${r.url.path}'), [
      'POST /diagnostics/5/analyze',
      'GET /diagnostics/5/analysis',
    ]);
    expect(find.text('Estado del vehículo: En uso'), findsOneWidget);
    expect(find.text('Bujía en mal estado · 62 %'), findsOneWidget);
    expect(find.textContaining('Basado en: audio'), findsOneWidget);
    expect(find.text('• Golpeteo rítmico al acelerar.'), findsOneWidget);
    expect(find.text('• Revisar bujías y bobinas.'), findsOneWidget);
    expect(find.text('⚠ No operar el vehículo si hay humo.'), findsOneWidget);
    expect(find.textContaining('requiere confirmación física'), findsOneWidget);
    expect(find.text('Observaciones de imagen'), findsNothing); // sección vacía oculta
    expect(find.text('Generado con: gemini · gemini-2.0-flash'), findsOneWidget);
  });

  testWidgets('identifica los análisis generados con stub', (tester) async {
    _mockBackend(_backend(metadata: _persisted(provider: 'stub', model: null)));
    await _pumpAnalysis(tester);
    await tester.pumpAndSettle();

    expect(find.text('Generado con: stub (simulado, sin IA real)'), findsOneWidget);
  });

  testWidgets('si no se obtienen los metadatos, el análisis se muestra igual', (tester) async {
    _mockBackend(_backend());
    await _pumpAnalysis(tester);
    await tester.pumpAndSettle();

    expect(find.textContaining('Posible falla de encendido'), findsOneWidget);
    expect(find.textContaining('Generado con'), findsNothing);
  });

  testWidgets('muestra un indicador mientras el análisis está en curso', (tester) async {
    final pending = Completer<http.Response>();
    _mockBackend((request) => request.method == 'POST' ? pending.future : _json(_persisted()));
    await _pumpAnalysis(tester);
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.textContaining('Analizando el diagnóstico con IA'), findsOneWidget);

    pending.complete(_json(_analysis));
    await tester.pumpAndSettle();

    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(find.textContaining('Posible falla de encendido'), findsOneWidget);
  });

  testWidgets('un error del backend se muestra legible y se puede reintentar', (tester) async {
    var fail = true;
    final requests = _mockBackend((request) {
      if (request.method == 'POST' && fail) {
        return _json({'detail': 'Gemini API request failed: timeout'}, 502);
      }
      return _backend(metadata: _persisted())(request);
    });
    await _pumpAnalysis(tester);
    await tester.pumpAndSettle();

    expect(find.text('Error HTTP 502: Gemini API request failed: timeout'), findsOneWidget);

    fail = false;
    await tester.tap(find.text('Reintentar'));
    await tester.pumpAndSettle();

    expect(requests.where((r) => r.method == 'POST'), hasLength(2));
    expect(find.textContaining('Posible falla de encendido'), findsOneWidget);
  });

  testWidgets('un proveedor no configurado (503) se muestra legible', (tester) async {
    _mockBackend(
      (_) => _json({'detail': 'GEMINI_API_KEY and GEMINI_MODEL must be set'}, 503),
    );
    await _pumpAnalysis(tester);
    await tester.pumpAndSettle();

    expect(find.text('Error HTTP 503: GEMINI_API_KEY and GEMINI_MODEL must be set'), findsOneWidget);
    expect(find.text('Volver al inicio'), findsOneWidget);
  });

  testWidgets('un error de conexión se muestra legible', (tester) async {
    _mockBackend((_) => throw http.ClientException('Connection refused'));
    await _pumpAnalysis(tester);
    await tester.pumpAndSettle();

    expect(find.textContaining('No se pudo conectar a'), findsOneWidget);
    expect(find.textContaining('Connection refused'), findsOneWidget);
  });

  testWidgets('el análisis tolera respuestas lentas por encima del timeout normal', (tester) async {
    _mockBackend((request) async {
      if (request.method == 'POST') {
        await Future<void>.delayed(const Duration(seconds: 45));
        return _json(_analysis);
      }
      return _json(_persisted());
    });
    await _pumpAnalysis(tester);

    await tester.pump(const Duration(seconds: 46));
    await tester.pumpAndSettle();

    expect(find.textContaining('Posible falla de encendido'), findsOneWidget);
  });

  testWidgets('pasado el timeout del análisis se muestra un mensaje claro', (tester) async {
    _mockBackend((_) async {
      await Future<void>.delayed(const Duration(seconds: 120));
      return _json(_analysis);
    });
    await _pumpAnalysis(tester);

    await tester.pump(aiAnalysisTimeout + const Duration(seconds: 1));
    await tester.pump();

    expect(find.textContaining('El servidor no respondió en 90 s'), findsOneWidget);
    expect(find.text('Reintentar'), findsOneWidget);

    await tester.pump(const Duration(seconds: 60)); // deja terminar el temporizador simulado
  });
}
