import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../api_client.dart';
import '../models/diagnostic_evidence.dart';
import 'diagnostic_analysis_screen.dart';

enum EvidenceKind { image, audio }

/// Extensions the backend accepts and the MIME type sent for each one. Audio is
/// limited to MP3 and WAV, the formats the AI analysis can actually listen to.
const Map<EvidenceKind, Map<String, String>> evidenceMimeTypes = {
  EvidenceKind.image: {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'webp': 'image/webp',
  },
  EvidenceKind.audio: {
    'mp3': 'audio/mpeg',
    'wav': 'audio/wav',
  },
};

const _formatsHint = 'Imágenes: JPG, PNG o WEBP (máx. 10 MB). Audio: MP3 o WAV (máx. 25 MB).';

/// A file chosen by the user, held in memory as bytes (Flutter Web has no file
/// paths). [mimeType] is null when the extension is not supported.
class PickedEvidenceFile {
  const PickedEvidenceFile({required this.name, required this.bytes, required this.mimeType});

  final String name;
  final Uint8List bytes;
  final String? mimeType;
}

/// Opens a file chooser for [kind]; returns null if the user cancels.
typedef EvidenceFilePicker = Future<PickedEvidenceFile?> Function(EvidenceKind kind);

Future<PickedEvidenceFile?> pickEvidenceFile(EvidenceKind kind) async {
  final mimeTypes = evidenceMimeTypes[kind]!;
  final result = await FilePicker.pickFiles(
    type: FileType.custom,
    allowedExtensions: mimeTypes.keys.toList(),
    withData: true,
  );
  final file = result?.files.singleOrNull;
  if (file == null) return null;
  final bytes = file.bytes;
  if (bytes == null) {
    throw StateError('No se pudo leer el contenido de "${file.name}".');
  }
  return PickedEvidenceFile(
    name: file.name,
    bytes: bytes,
    mimeType: mimeTypes[file.extension?.toLowerCase()],
  );
}

/// Lists, adds and deletes a diagnostic's evidences before its AI analysis.
/// Once the diagnostic has an analysis the list becomes read-only, because the
/// backend rejects any change with 409; a 409 received anyway (e.g. analyzed
/// from another device) switches the screen to read-only as well.
class DiagnosticEvidencesScreen extends StatefulWidget {
  const DiagnosticEvidencesScreen({super.key, required this.diagnosticId, this.pickFile});

  final int diagnosticId;

  /// Replaceable in tests; defaults to [pickEvidenceFile].
  final EvidenceFilePicker? pickFile;

  @override
  State<DiagnosticEvidencesScreen> createState() => _DiagnosticEvidencesScreenState();
}

class _DiagnosticEvidencesScreenState extends State<DiagnosticEvidencesScreen> {
  final _descriptionController = TextEditingController();

  bool _loading = true;
  String? _loadErrorText;
  List<DiagnosticEvidence> _evidences = [];
  bool _analyzed = false;

  PickedEvidenceFile? _selected;
  bool _uploading = false;
  int? _deletingId;
  String? _actionErrorText;

  bool get _busy => _uploading || _deletingId != null;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _descriptionController.dispose();
    super.dispose();
  }

  /// Loads the evidences and whether an analysis exists. With [quiet] the
  /// current list stays on screen while it refreshes.
  Future<void> _load({bool quiet = false}) async {
    setState(() {
      _loading = !quiet;
      _loadErrorText = null;
    });

    try {
      final results = await Future.wait([
        getJsonList('/diagnostics/${widget.diagnosticId}/evidences'),
        _hasAnalysis(),
      ]);
      if (!mounted) return;
      setState(() {
        _evidences = (results[0] as List<Map<String, dynamic>>)
            .map(DiagnosticEvidence.fromJson)
            .toList();
        _analyzed = results[1] as bool;
        if (_analyzed) _clearSelection();
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _loadErrorText = describeEvidenceError(error));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<bool> _hasAnalysis() async {
    try {
      await getJson('/diagnostics/${widget.diagnosticId}/analysis');
      return true;
    } on ApiException catch (error) {
      if (error.statusCode == 404) return false;
      rethrow;
    }
  }

  Future<void> _pick(EvidenceKind kind) async {
    setState(() => _actionErrorText = null);
    final PickedEvidenceFile? file;
    try {
      file = await (widget.pickFile ?? pickEvidenceFile)(kind);
    } catch (error) {
      if (!mounted) return;
      setState(() => _actionErrorText = 'No se pudo seleccionar el archivo: $error');
      return;
    }
    if (file == null || !mounted) return;
    if (file.mimeType == null) {
      setState(() => _actionErrorText = 'Formato no admitido: "${file!.name}". $_formatsHint');
      return;
    }
    setState(() {
      _selected = file;
      _descriptionController.clear();
    });
  }

  void _clearSelection() {
    _selected = null;
    _descriptionController.clear();
  }

  Future<void> _upload() async {
    final file = _selected!;
    setState(() {
      _uploading = true;
      _actionErrorText = null;
    });

    try {
      await uploadEvidence(
        widget.diagnosticId,
        bytes: file.bytes,
        fileName: file.name,
        mimeType: file.mimeType!,
        description: _descriptionController.text,
      );
      if (!mounted) return;
      setState(_clearSelection);
      await _load(quiet: true);
    } on ApiException catch (error) {
      _handleActionError(error);
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  Future<void> _delete(DiagnosticEvidence evidence) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Eliminar evidencia'),
        content: Text('¿Eliminar "${evidence.fileName}"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Eliminar')),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() {
      _deletingId = evidence.id;
      _actionErrorText = null;
    });
    try {
      await deleteEvidence(evidence.id);
      if (!mounted) return;
      await _load(quiet: true);
    } on ApiException catch (error) {
      _handleActionError(error);
      // A 404 means it was already gone; refresh so the list matches the backend.
      if (error.statusCode == 404 && mounted) await _load(quiet: true);
    } finally {
      if (mounted) setState(() => _deletingId = null);
    }
  }

  void _handleActionError(ApiException error) {
    if (!mounted) return;
    setState(() {
      _actionErrorText = describeEvidenceError(error);
      if (error.statusCode == 409) {
        _analyzed = true;
        _clearSelection();
      }
    });
  }

  Future<void> _openAnalysis() async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => DiagnosticAnalysisScreen(diagnosticId: widget.diagnosticId),
      ),
    );
    // The analysis now exists (or failed); refresh to reflect the read-only state.
    if (mounted) await _load(quiet: true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Evidencias · Diagnóstico #${widget.diagnosticId}')),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_analyzed)
              const _Notice(
                text: 'Este diagnóstico ya tiene un análisis de IA: sus evidencias '
                    'no se pueden modificar.',
                color: Colors.blue,
              )
            else if (!_loading && _loadErrorText == null)
              ..._buildAddSection(),
            if (_actionErrorText != null) ...[
              const SizedBox(height: 16),
              _Notice(text: _actionErrorText!, color: Colors.red),
            ],
            const SizedBox(height: 16),
            Expanded(child: _buildList()),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _loading || _busy ? null : _openAnalysis,
              icon: const Icon(Icons.auto_awesome),
              label: Text(_analyzed ? 'Ver análisis de IA' : 'Analizar con IA'),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _buildAddSection() {
    final selected = _selected;
    return [
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          OutlinedButton.icon(
            onPressed: _busy ? null : () => _pick(EvidenceKind.image),
            icon: const Icon(Icons.image),
            label: const Text('Agregar imagen'),
          ),
          OutlinedButton.icon(
            onPressed: _busy ? null : () => _pick(EvidenceKind.audio),
            icon: const Icon(Icons.audiotrack),
            label: const Text('Agregar audio'),
          ),
        ],
      ),
      const SizedBox(height: 8),
      Text(_formatsHint, style: Theme.of(context).textTheme.bodySmall),
      if (selected != null) ...[
        const SizedBox(height: 16),
        Text('Seleccionado: ${selected.name} (${formatFileSize(selected.bytes.length)})'),
        const SizedBox(height: 8),
        TextField(
          controller: _descriptionController,
          enabled: !_uploading,
          decoration: const InputDecoration(labelText: 'Descripción (opcional)'),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            ElevatedButton(
              onPressed: _uploading ? null : _upload,
              child: _uploading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Subir evidencia'),
            ),
            const SizedBox(width: 8),
            TextButton(
              onPressed: _uploading ? null : () => setState(_clearSelection),
              child: const Text('Cancelar'),
            ),
          ],
        ),
      ],
    ];
  }

  Widget _buildList() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_loadErrorText != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _Notice(text: _loadErrorText!, color: Colors.red),
          const SizedBox(height: 16),
          OutlinedButton(onPressed: _load, child: const Text('Reintentar')),
        ],
      );
    }
    if (_evidences.isEmpty) {
      return Center(
        child: Text(
          _analyzed
              ? 'Este diagnóstico no tiene evidencias.'
              : 'Aún no hay evidencias. Agrega fotos o audios antes de analizar.',
          textAlign: TextAlign.center,
        ),
      );
    }
    return ListView.separated(
      itemCount: _evidences.length,
      separatorBuilder: (_, _) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final evidence = _evidences[index];
        final description = evidence.description;
        return ListTile(
          leading: Icon(_typeIcons[evidence.evidenceType] ?? Icons.insert_drive_file),
          title: Text(evidence.fileName),
          subtitle: Text(
            '${_typeLabels[evidence.evidenceType] ?? evidence.evidenceType}'
            ' · ${formatFileSize(evidence.fileSize)}'
            '${description == null || description.isEmpty ? '' : '\n$description'}',
          ),
          trailing: _analyzed
              ? null
              : _deletingId == evidence.id
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : IconButton(
                      tooltip: 'Eliminar',
                      icon: const Icon(Icons.delete_outline),
                      onPressed: _busy ? null : () => _delete(evidence),
                    ),
        );
      },
    );
  }
}

const _typeLabels = {'IMAGE': 'Imagen', 'AUDIO': 'Audio', 'VIDEO': 'Video'};
const _typeIcons = {'IMAGE': Icons.image, 'AUDIO': Icons.audiotrack, 'VIDEO': Icons.videocam};

/// Readable text for an evidence request error. The backend's own message (in
/// [ApiException]) is always kept; known statuses get a short explanation first.
String describeEvidenceError(ApiException error) {
  final code = error.statusCode;
  final String? hint = switch (code) {
    404 => 'El diagnóstico o la evidencia ya no existe.',
    409 => null, // The backend message already explains it.
    413 => 'El archivo supera el tamaño máximo permitido. $_formatsHint',
    415 => 'Formato no admitido o el contenido no corresponde a la extensión. $_formatsHint',
    _ when code != null && code >= 500 => 'Error del servidor. Intenta de nuevo en unos momentos.',
    _ => null, // Connection errors and timeouts already carry a readable message.
  };
  return hint == null ? error.toString() : '$hint\n$error';
}

String formatFileSize(int bytes) {
  if (bytes < 1024) return '$bytes B';
  if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
  return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
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
