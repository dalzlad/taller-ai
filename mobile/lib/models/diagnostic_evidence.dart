/// A file attached to a diagnostic, as returned by
/// `POST /diagnostics/{id}/evidences` and `GET /diagnostics/{id}/evidences`
/// (the backend's `DiagnosticEvidenceRead`).
class DiagnosticEvidence {
  const DiagnosticEvidence({
    required this.id,
    required this.diagnosticId,
    required this.evidenceType,
    required this.fileName,
    required this.mimeType,
    required this.fileSize,
    required this.description,
    required this.createdAt,
  });

  factory DiagnosticEvidence.fromJson(Map<String, dynamic> json) => DiagnosticEvidence(
        id: json['id'] as int,
        diagnosticId: json['diagnostic_id'] as int,
        evidenceType: json['evidence_type'] as String,
        fileName: json['file_name'] as String,
        mimeType: json['mime_type'] as String,
        fileSize: json['file_size'] as int,
        description: json['description'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  final int id;
  final int diagnosticId;

  /// `IMAGE`, `AUDIO` or `VIDEO`.
  final String evidenceType;

  /// Original file name; the backend stores the file under a generated name.
  final String fileName;
  final String mimeType;

  /// In bytes.
  final int fileSize;
  final String? description;
  final DateTime createdAt;
}
