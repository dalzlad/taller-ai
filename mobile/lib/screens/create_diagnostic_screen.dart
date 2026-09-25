import 'package:flutter/material.dart';

import '../api_client.dart';
import 'diagnostic_created_screen.dart';

class CreateDiagnosticScreen extends StatefulWidget {
  const CreateDiagnosticScreen({super.key, required this.vehicleId});

  final int vehicleId;

  @override
  State<CreateDiagnosticScreen> createState() => _CreateDiagnosticScreenState();
}

class _CreateDiagnosticScreenState extends State<CreateDiagnosticScreen> {
  final _formKey = GlobalKey<FormState>();
  final _symptomsController = TextEditingController();
  final _notesController = TextEditingController();

  bool _loading = false;
  String? _errorText;

  @override
  void dispose() {
    _symptomsController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _loading = true;
      _errorText = null;
    });

    try {
      final notes = _notesController.text.trim();
      final diagnostic = await postJson('/diagnostics', {
        'vehicle_id': widget.vehicleId,
        'reported_symptoms': _symptomsController.text.trim(),
        if (notes.isNotEmpty) 'mechanic_notes': notes,
      });

      if (!mounted) return;
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => DiagnosticCreatedScreen(
            diagnosticId: diagnostic['id'] as int,
            status: diagnostic['status'] as String,
          ),
        ),
      );
    } on ApiException catch (error) {
      setState(() => _errorText = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('3. Crear diagnóstico')),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Form(
          key: _formKey,
          child: ListView(
            children: [
              Text('Vehículo #${widget.vehicleId}'),
              const SizedBox(height: 16),
              TextFormField(
                controller: _symptomsController,
                decoration: const InputDecoration(
                  labelText: 'Síntomas reportados',
                  alignLabelWithHint: true,
                ),
                maxLines: 5,
                validator: (value) {
                  final v = value?.trim() ?? '';
                  if (v.length < 3 || v.length > 10000) {
                    return 'Describe los síntomas (mínimo 3 caracteres)';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _notesController,
                decoration: const InputDecoration(
                  labelText: 'Notas del mecánico (opcional)',
                  alignLabelWithHint: true,
                ),
                maxLines: 4,
                validator: (value) {
                  final v = value?.trim() ?? '';
                  if (v.length > 10000) {
                    return 'Máximo 10000 caracteres';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: _loading ? null : _submit,
                child: _loading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Crear diagnóstico'),
              ),
              if (_errorText != null) ...[
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.red.withValues(alpha: 0.1),
                    border: Border.all(color: Colors.red),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: SelectableText(
                    _errorText!,
                    style: TextStyle(color: Colors.red.shade900),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
