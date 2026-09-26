import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'api_client.dart';
import 'screens/select_customer_screen.dart';

void main() {
  runApp(const TallerAIApp());
}

class TallerAIApp extends StatelessWidget {
  const TallerAIApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TallerAI',
      theme: ThemeData(colorSchemeSeed: Colors.blue, useMaterial3: true),
      home: const ConnectionTestScreen(),
    );
  }
}

class ConnectionTestScreen extends StatefulWidget {
  const ConnectionTestScreen({super.key});

  @override
  State<ConnectionTestScreen> createState() => _ConnectionTestScreenState();
}

class _ConnectionTestScreenState extends State<ConnectionTestScreen> {
  bool _loading = false;
  String? _resultText;
  bool _resultIsError = false;

  Future<void> _testConnection() async {
    setState(() {
      _loading = true;
      _resultText = null;
      _resultIsError = false;
    });

    final uri = Uri.parse('$backendBaseUrl/health');
    try {
      final response = await http.get(uri).timeout(const Duration(seconds: 10));
      if (response.statusCode == 200) {
        setState(() {
          _resultText = 'Conexión exitosa (${response.statusCode})\n${response.body}';
          _resultIsError = false;
        });
      } else {
        setState(() {
          _resultText =
              'Respuesta con error HTTP ${response.statusCode}\n${response.body}';
          _resultIsError = true;
        });
      }
    } catch (error) {
      setState(() {
        _resultText = 'Error al conectar con $uri:\n$error';
        _resultIsError = true;
      });
    } finally {
      setState(() {
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('TallerAI - Prueba de conexión')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Backend: $backendBaseUrl'),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: _loading ? null : _testConnection,
                child: _loading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Probar conexión con backend'),
              ),
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const SelectCustomerScreen()),
                  );
                },
                child: const Text('Crear nuevo diagnóstico'),
              ),
              const SizedBox(height: 24),
              if (_resultText != null)
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: _resultIsError
                        ? Colors.red.withValues(alpha: 0.1)
                        : Colors.green.withValues(alpha: 0.1),
                    border: Border.all(
                      color: _resultIsError ? Colors.red : Colors.green,
                    ),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: SelectableText(
                    _resultText!,
                    style: TextStyle(
                      color: _resultIsError ? Colors.red.shade900 : Colors.green.shade900,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
