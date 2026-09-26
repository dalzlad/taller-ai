import 'package:flutter/material.dart';

import '../api_client.dart';
import '../models/diagnostic_analysis.dart';

const _vehicleStateLabels = {
  'en_uso': 'En uso',
  'en_reparacion': 'En reparación',
  'indeterminado': 'Indeterminado',
};

const _basedOnLabels = {'audio': 'audio', 'image': 'imagen', 'ambos': 'audio e imagen'};

/// Requests the diagnostic's AI analysis and shows it. The backend returns the
/// persisted analysis when one exists, so this screen always calls
/// `POST /analyze` and never caches anything itself.
class DiagnosticAnalysisScreen extends StatefulWidget {
  const DiagnosticAnalysisScreen({super.key, required this.diagnosticId});

  final int diagnosticId;

  @override
  State<DiagnosticAnalysisScreen> createState() => _DiagnosticAnalysisScreenState();
}

class _DiagnosticAnalysisScreenState extends State<DiagnosticAnalysisScreen> {
  bool _loading = true;
  String? _errorText;
  DiagnosticAnalysis? _analysis;
  AnalysisMetadata? _metadata;

  @override
  void initState() {
    super.initState();
    _analyze();
  }

  Future<void> _analyze() async {
    setState(() {
      _loading = true;
      _errorText = null;
    });

    try {
      final json = await postJson(
        '/diagnostics/${widget.diagnosticId}/analyze',
        const {},
        timeout: aiAnalysisTimeout,
      );
      final analysis = DiagnosticAnalysis.fromJson(json);
      final metadata = await _loadMetadata();
      if (!mounted) return;
      setState(() {
        _analysis = analysis;
        _metadata = metadata;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _errorText = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  /// Provider and model come from the persisted analysis. They are optional:
  /// the analysis is still shown if this lookup fails.
  Future<AnalysisMetadata?> _loadMetadata() async {
    try {
      return AnalysisMetadata.fromJson(
        await getJson('/diagnostics/${widget.diagnosticId}/analysis'),
      );
    } on ApiException {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Análisis IA · Diagnóstico #${widget.diagnosticId}')),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: _buildBody(context),
      ),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text(
              'Analizando el diagnóstico con IA…\nPuede tardar hasta un minuto.',
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }
    final analysis = _analysis;
    if (_errorText != null || analysis == null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _Notice(text: _errorText ?? 'No se obtuvo el análisis.', color: Colors.red),
          const SizedBox(height: 16),
          ElevatedButton(onPressed: _analyze, child: const Text('Reintentar')),
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: () => Navigator.popUntil(context, (route) => route.isFirst),
            child: const Text('Volver al inicio'),
          ),
        ],
      );
    }
    return ListView(
      children: [
        Text(analysis.summary, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        Text(
          'Estado del vehículo: '
          '${_vehicleStateLabels[analysis.vehicleState] ?? analysis.vehicleState}',
        ),
        if (analysis.safetyWarnings.isNotEmpty) ...[
          const SizedBox(height: 16),
          for (final warning in analysis.safetyWarnings)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _Notice(text: '⚠ $warning', color: Colors.orange),
            ),
        ],
        _Section(
          title: 'Posibles causas',
          children: [
            for (final cause in analysis.possibleCauses)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('${cause.cause} · ${(cause.confidence * 100).round()} %'),
                subtitle: Text(
                  cause.basedOn.isEmpty
                      ? cause.reasoning
                      : '${cause.reasoning}\nBasado en: '
                          '${cause.basedOn.map((b) => _basedOnLabels[b] ?? b).join(', ')}',
                ),
              ),
          ],
        ),
        _Section(title: 'Observaciones de audio', items: analysis.audioObservations),
        _Section(title: 'Observaciones de imagen', items: analysis.imageObservations),
        _Section(title: 'Pruebas recomendadas', items: analysis.recommendedTests),
        _Section(title: 'Limitaciones', items: analysis.limitations),
        if (_metadata != null) ...[
          const SizedBox(height: 16),
          Text(
            _providerLabel(_metadata!),
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
        const SizedBox(height: 24),
        ElevatedButton(
          onPressed: () => Navigator.popUntil(context, (route) => route.isFirst),
          child: const Text('Volver al inicio'),
        ),
      ],
    );
  }
}

String _providerLabel(AnalysisMetadata metadata) {
  if (metadata.provider == 'stub') {
    return 'Generado con: stub (simulado, sin IA real)';
  }
  final model = metadata.model;
  return model == null
      ? 'Generado con: ${metadata.provider}'
      : 'Generado con: ${metadata.provider} · $model';
}

/// A titled block; hidden when it has nothing to show.
class _Section extends StatelessWidget {
  const _Section({required this.title, this.items = const [], this.children = const []});

  final String title;
  final List<String> items;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty && children.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 4),
          for (final item in items) Text('• $item'),
          ...children,
        ],
      ),
    );
  }
}

class _Notice extends StatelessWidget {
  const _Notice({required this.text, required this.color});

  final String text;
  final MaterialColor color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        border: Border.all(color: color),
        borderRadius: BorderRadius.circular(8),
      ),
      child: SelectableText(text, style: TextStyle(color: color.shade900)),
    );
  }
}
