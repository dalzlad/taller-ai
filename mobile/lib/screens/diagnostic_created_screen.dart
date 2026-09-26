import 'package:flutter/material.dart';

import 'diagnostic_evidences_screen.dart';

class DiagnosticCreatedScreen extends StatelessWidget {
  const DiagnosticCreatedScreen({
    super.key,
    required this.diagnosticId,
    required this.status,
  });

  final int diagnosticId;
  final String status;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Diagnóstico creado')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.check_circle, color: Colors.green, size: 64),
              const SizedBox(height: 16),
              Text(
                'Diagnóstico #$diagnosticId creado',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text('Estado: $status'),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => DiagnosticEvidencesScreen(diagnosticId: diagnosticId),
                    ),
                  );
                },
                icon: const Icon(Icons.attach_file),
                label: const Text('Continuar a evidencias'),
              ),
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: () =>
                    Navigator.popUntil(context, (route) => route.isFirst),
                child: const Text('Volver al inicio'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
