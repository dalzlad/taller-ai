import 'dart:async';

import 'package:flutter/material.dart';

import '../api_client.dart';
import 'create_customer_screen.dart';
import 'select_vehicle_screen.dart';

/// Minimum search length accepted by `GET /customers?q=`.
const int minCustomerQueryLength = 2;

class SelectCustomerScreen extends StatefulWidget {
  const SelectCustomerScreen({super.key});

  @override
  State<SelectCustomerScreen> createState() => _SelectCustomerScreenState();
}

class _SelectCustomerScreenState extends State<SelectCustomerScreen> {
  final _searchController = TextEditingController();
  Timer? _debounce;

  // Only the response of the latest search is shown, even if an older one
  // arrives later.
  int _searchId = 0;
  bool _loading = false;
  String? _errorText;
  List<Map<String, dynamic>>? _results;

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _onQueryChanged(String value) {
    _debounce?.cancel();
    final query = value.trim();
    if (query.length < minCustomerQueryLength) {
      _searchId++;
      setState(() {
        _loading = false;
        _errorText = null;
        _results = null;
      });
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 300), () => _search(query));
  }

  Future<void> _search(String query) async {
    final searchId = ++_searchId;
    setState(() {
      _loading = true;
      _errorText = null;
    });

    try {
      final results = await getJsonList('/customers', query: {'q': query});
      if (!mounted || searchId != _searchId) return;
      setState(() => _results = results);
    } on ApiException catch (error) {
      if (!mounted || searchId != _searchId) return;
      setState(() {
        _results = null;
        _errorText = error.toString();
      });
    } finally {
      if (mounted && searchId == _searchId) setState(() => _loading = false);
    }
  }

  void _openCustomer(Map<String, dynamic> customer) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => SelectVehicleScreen(
          customerId: customer['id'] as int,
          customerName: customer['name'] as String,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final results = _results;
    return Scaffold(
      appBar: AppBar(title: const Text('1. Seleccionar cliente')),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _searchController,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: 'Buscar cliente',
                hintText: 'Nombre, teléfono o email',
                prefixIcon: Icon(Icons.search),
              ),
              onChanged: _onQueryChanged,
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const CreateCustomerScreen()),
                );
              },
              icon: const Icon(Icons.person_add),
              label: const Text('Nuevo cliente'),
            ),
            const SizedBox(height: 16),
            if (_loading) const LinearProgressIndicator(),
            if (_errorText != null)
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
            Expanded(
              child: results == null
                  ? Center(
                      child: Text(
                        _errorText == null && !_loading
                            ? 'Escribe al menos $minCustomerQueryLength caracteres para buscar.'
                            : '',
                        textAlign: TextAlign.center,
                      ),
                    )
                  : results.isEmpty
                      ? const Center(
                          child: Text(
                            'No se encontraron clientes. Puedes crear uno nuevo.',
                            textAlign: TextAlign.center,
                          ),
                        )
                      : ListView.separated(
                          itemCount: results.length,
                          separatorBuilder: (_, _) => const Divider(height: 1),
                          itemBuilder: (context, index) {
                            final customer = results[index];
                            return ListTile(
                              leading: const Icon(Icons.person),
                              title: Text(customer['name'] as String),
                              subtitle: Text('${customer['phone']} · ${customer['email']}'),
                              trailing: const Icon(Icons.chevron_right),
                              onTap: () => _openCustomer(customer),
                            );
                          },
                        ),
            ),
          ],
        ),
      ),
    );
  }
}
