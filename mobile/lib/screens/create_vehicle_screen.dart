import 'package:flutter/material.dart';

import '../api_client.dart';
import 'create_diagnostic_screen.dart';

class CreateVehicleScreen extends StatefulWidget {
  const CreateVehicleScreen({super.key, required this.customerId});

  final int customerId;

  @override
  State<CreateVehicleScreen> createState() => _CreateVehicleScreenState();
}

class _CreateVehicleScreenState extends State<CreateVehicleScreen> {
  final _formKey = GlobalKey<FormState>();
  final _plateController = TextEditingController();
  final _vinController = TextEditingController();
  final _brandController = TextEditingController();
  final _modelController = TextEditingController();
  final _yearController = TextEditingController();
  final _engineController = TextEditingController();
  final _mileageController = TextEditingController();

  bool _loading = false;
  String? _errorText;

  @override
  void dispose() {
    _plateController.dispose();
    _vinController.dispose();
    _brandController.dispose();
    _modelController.dispose();
    _yearController.dispose();
    _engineController.dispose();
    _mileageController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _loading = true;
      _errorText = null;
    });

    try {
      final vin = _vinController.text.trim();
      final engine = _engineController.text.trim();
      final vehicle = await postJson('/vehicles', {
        'customer_id': widget.customerId,
        'plate': _plateController.text.trim(),
        if (vin.isNotEmpty) 'vin': vin,
        'brand': _brandController.text.trim(),
        'model': _modelController.text.trim(),
        'year': int.parse(_yearController.text.trim()),
        if (engine.isNotEmpty) 'engine': engine,
        'mileage': int.parse(_mileageController.text.trim()),
      });

      if (!mounted) return;
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => CreateDiagnosticScreen(vehicleId: vehicle['id'] as int),
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
      appBar: AppBar(title: const Text('2. Crear vehículo')),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Form(
          key: _formKey,
          child: ListView(
            children: [
              Text('Cliente #${widget.customerId}'),
              const SizedBox(height: 16),
              TextFormField(
                controller: _plateController,
                decoration: const InputDecoration(labelText: 'Placa'),
                textCapitalization: TextCapitalization.characters,
                validator: (value) {
                  final v = value?.trim() ?? '';
                  if (v.length < 3 || v.length > 15) {
                    return 'La placa debe tener entre 3 y 15 caracteres';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _vinController,
                decoration: const InputDecoration(
                  labelText: 'VIN (opcional)',
                  hintText: 'Exactamente 17 caracteres',
                ),
                textCapitalization: TextCapitalization.characters,
                validator: (value) {
                  final v = value?.trim() ?? '';
                  if (v.isNotEmpty && v.length != 17) {
                    return 'El VIN debe tener exactamente 17 caracteres';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _brandController,
                decoration: const InputDecoration(labelText: 'Marca'),
                validator: (value) {
                  final v = value?.trim() ?? '';
                  if (v.isEmpty || v.length > 80) {
                    return 'La marca es obligatoria (máx. 80 caracteres)';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _modelController,
                decoration: const InputDecoration(labelText: 'Modelo'),
                validator: (value) {
                  final v = value?.trim() ?? '';
                  if (v.isEmpty || v.length > 100) {
                    return 'El modelo es obligatorio (máx. 100 caracteres)';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _yearController,
                decoration: const InputDecoration(labelText: 'Año'),
                keyboardType: TextInputType.number,
                validator: (value) {
                  final n = int.tryParse(value?.trim() ?? '');
                  if (n == null || n < 1886 || n > 2100) {
                    return 'Año inválido (1886-2100)';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _engineController,
                decoration: const InputDecoration(labelText: 'Motor (opcional)'),
                validator: (value) {
                  final v = value?.trim() ?? '';
                  if (v.length > 100) {
                    return 'Máximo 100 caracteres';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _mileageController,
                decoration: const InputDecoration(labelText: 'Kilometraje'),
                keyboardType: TextInputType.number,
                validator: (value) {
                  final n = int.tryParse(value?.trim() ?? '');
                  if (n == null || n < 0) {
                    return 'Kilometraje inválido';
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
                    : const Text('Siguiente'),
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
