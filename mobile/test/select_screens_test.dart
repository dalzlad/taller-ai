import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/api_client.dart';
import 'package:mobile/screens/select_customer_screen.dart';
import 'package:mobile/screens/select_vehicle_screen.dart';

const _ana = {
  'id': 1,
  'name': 'Ana Ruiz',
  'phone': '+57 300 111 2222',
  'email': 'ana@example.com',
  'created_at': '2026-09-25T10:00:00Z',
};

const _vehicle = {
  'id': 7,
  'customer_id': 1,
  'plate': 'ABC123',
  'vin': null,
  'brand': 'Mazda',
  'model': '2',
  'year': 2019,
  'engine': null,
  'mileage': 50000,
  'created_at': '2026-09-25T10:00:00Z',
};

http.Response _json(Object body, [int status = 200]) => http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

/// Serves [handler] and records every request made through [apiHttpClient].
List<http.Request> _mockBackend(http.Response Function(http.Request) handler) {
  final requests = <http.Request>[];
  apiHttpClient = MockClient((request) async {
    requests.add(request);
    return handler(request);
  });
  return requests;
}

Future<void> _pumpScreen(WidgetTester tester, Widget screen) =>
    tester.pumpWidget(MaterialApp(home: screen));

Future<void> _search(WidgetTester tester, String text) async {
  await tester.enterText(find.byType(TextField), text);
  await tester.pump(const Duration(milliseconds: 300)); // debounce
  await tester.pumpAndSettle();
}

void main() {
  tearDown(() => apiHttpClient = http.Client());

  group('SelectCustomerScreen', () {
    testWidgets('busca en el backend y muestra los resultados', (tester) async {
      final requests = _mockBackend((_) => _json([_ana]));
      await _pumpScreen(tester, const SelectCustomerScreen());

      await _search(tester, '  ana ');

      expect(requests, hasLength(1));
      expect(requests.single.url.path, '/customers');
      expect(requests.single.url.queryParameters, {'q': 'ana'});
      expect(find.text('Ana Ruiz'), findsOneWidget);
      expect(find.text('+57 300 111 2222 · ana@example.com'), findsOneWidget);
    });

    testWidgets('no consulta con menos de 2 caracteres', (tester) async {
      final requests = _mockBackend((_) => _json([_ana]));
      await _pumpScreen(tester, const SelectCustomerScreen());

      await _search(tester, 'a');

      expect(requests, isEmpty);
      expect(find.textContaining('al menos 2 caracteres'), findsOneWidget);
    });

    testWidgets('indica cuando no hay resultados', (tester) async {
      _mockBackend((_) => _json([]));
      await _pumpScreen(tester, const SelectCustomerScreen());

      await _search(tester, 'zzz');

      expect(find.textContaining('No se encontraron clientes'), findsOneWidget);
    });

    testWidgets('muestra el error del backend de forma legible', (tester) async {
      _mockBackend(
        (_) => _json({'detail': 'Search text must have at least 2 non-blank characters'}, 422),
      );
      await _pumpScreen(tester, const SelectCustomerScreen());

      await _search(tester, 'ana');

      expect(
        find.text('Error HTTP 422: Search text must have at least 2 non-blank characters'),
        findsOneWidget,
      );
    });

    testWidgets('al elegir un cliente abre sus vehículos', (tester) async {
      _mockBackend(
        (request) => request.url.path == '/customers' ? _json([_ana]) : _json([_vehicle]),
      );
      await _pumpScreen(tester, const SelectCustomerScreen());
      await _search(tester, 'ana');

      await tester.tap(find.text('Ana Ruiz'));
      await tester.pumpAndSettle();

      expect(find.text('2. Seleccionar vehículo'), findsOneWidget);
      expect(find.text('Cliente: Ana Ruiz'), findsOneWidget);
    });

    testWidgets('"Nuevo cliente" abre el formulario de creación', (tester) async {
      _mockBackend((_) => _json([]));
      await _pumpScreen(tester, const SelectCustomerScreen());

      await tester.tap(find.text('Nuevo cliente'));
      await tester.pumpAndSettle();

      expect(find.text('1. Crear cliente'), findsOneWidget);
    });
  });

  group('SelectVehicleScreen', () {
    const screen = SelectVehicleScreen(customerId: 1, customerName: 'Ana Ruiz');

    testWidgets('consulta los vehículos del cliente y los muestra', (tester) async {
      final requests = _mockBackend((_) => _json([_vehicle]));
      await _pumpScreen(tester, screen);
      await tester.pumpAndSettle();

      expect(requests.single.url.path, '/vehicles');
      expect(requests.single.url.queryParameters, {'customer_id': '1', 'limit': '50'});
      expect(find.text('ABC123'), findsOneWidget);
      expect(find.text('Mazda 2 2019 · 50000 km'), findsOneWidget);
    });

    testWidgets('al elegir un vehículo continúa con el diagnóstico', (tester) async {
      _mockBackend((_) => _json([_vehicle]));
      await _pumpScreen(tester, screen);
      await tester.pumpAndSettle();

      await tester.tap(find.text('ABC123'));
      await tester.pumpAndSettle();

      expect(find.text('3. Crear diagnóstico'), findsOneWidget);
      expect(find.text('Vehículo #7'), findsOneWidget);
    });

    testWidgets('sin vehículos permite crear uno nuevo', (tester) async {
      _mockBackend((_) => _json([]));
      await _pumpScreen(tester, screen);
      await tester.pumpAndSettle();

      expect(find.textContaining('no tiene vehículos'), findsOneWidget);

      await tester.tap(find.text('Nuevo vehículo'));
      await tester.pumpAndSettle();

      expect(find.text('2. Crear vehículo'), findsOneWidget);
      expect(find.text('Cliente #1'), findsOneWidget);
    });

    testWidgets('muestra el error y permite reintentar', (tester) async {
      var fail = true;
      _mockBackend(
        (_) => fail ? http.Response('Internal Server Error', 500) : _json([_vehicle]),
      );
      await _pumpScreen(tester, screen);
      await tester.pumpAndSettle();

      expect(find.text('Error HTTP 500: Internal Server Error'), findsOneWidget);

      fail = false;
      await tester.tap(find.text('Reintentar'));
      await tester.pumpAndSettle();

      expect(find.text('ABC123'), findsOneWidget);
    });
  });
}
