import 'package:flutter/material.dart';

import '../api_client.dart';
import 'create_diagnostic_screen.dart';
import 'create_vehicle_screen.dart';

/// Upper bound of `GET /vehicles?limit=`; a customer's fleet is listed in full
/// up to this size.
const int maxVehiclesPerCustomer = 50;

class SelectVehicleScreen extends StatefulWidget {
  const SelectVehicleScreen({
    super.key,
    required this.customerId,
    required this.customerName,
  });

  final int customerId;
  final String customerName;

  @override
  State<SelectVehicleScreen> createState() => _SelectVehicleScreenState();
}

class _SelectVehicleScreenState extends State<SelectVehicleScreen> {
  bool _loading = true;
  String? _errorText;
  List<Map<String, dynamic>> _vehicles = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorText = null;
    });

    try {
      final vehicles = await getJsonList('/vehicles', query: {
        'customer_id': '${widget.customerId}',
        'limit': '$maxVehiclesPerCustomer',
      });
      if (!mounted) return;
      setState(() => _vehicles = vehicles);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _errorText = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _openVehicle(Map<String, dynamic> vehicle) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => CreateDiagnosticScreen(vehicleId: vehicle['id'] as int),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorText != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
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
          const SizedBox(height: 16),
          OutlinedButton(onPressed: _load, child: const Text('Reintentar')),
        ],
      );
    }
    if (_vehicles.isEmpty) {
      return const Center(
        child: Text(
          'Este cliente no tiene vehículos registrados. Puedes crear uno nuevo.',
          textAlign: TextAlign.center,
        ),
      );
    }
    return ListView.separated(
      itemCount: _vehicles.length,
      separatorBuilder: (_, _) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final vehicle = _vehicles[index];
        return ListTile(
          leading: const Icon(Icons.directions_car),
          title: Text(vehicle['plate'] as String),
          subtitle: Text(
            '${vehicle['brand']} ${vehicle['model']} ${vehicle['year']} · ${vehicle['mileage']} km',
          ),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => _openVehicle(vehicle),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('2. Seleccionar vehículo')),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Cliente: ${widget.customerName}'),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => CreateVehicleScreen(customerId: widget.customerId),
                  ),
                );
              },
              icon: const Icon(Icons.add),
              label: const Text('Nuevo vehículo'),
            ),
            const SizedBox(height: 16),
            Expanded(child: _buildBody()),
          ],
        ),
      ),
    );
  }
}
