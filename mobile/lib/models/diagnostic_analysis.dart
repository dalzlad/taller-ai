/// Preliminary AI analysis returned by `POST /diagnostics/{id}/analyze`
/// (the backend's `PreliminaryDiagnosticAnalysis`).
class DiagnosticAnalysis {
  const DiagnosticAnalysis({
    required this.summary,
    required this.vehicleState,
    required this.audioObservations,
    required this.imageObservations,
    required this.possibleCauses,
    required this.recommendedTests,
    required this.safetyWarnings,
    required this.limitations,
  });

  factory DiagnosticAnalysis.fromJson(Map<String, dynamic> json) {
    final observations = json['observations'] as Map<String, dynamic>? ?? const {};
    return DiagnosticAnalysis(
      summary: json['summary'] as String,
      vehicleState: json['vehicle_state'] as String? ?? 'indeterminado',
      audioObservations: _strings(observations['audio']),
      imageObservations: _strings(observations['image']),
      possibleCauses: (json['possible_causes'] as List? ?? const [])
          .map((item) => PossibleCause.fromJson(item as Map<String, dynamic>))
          .toList(),
      recommendedTests: _strings(json['recommended_tests']),
      safetyWarnings: _strings(json['safety_warnings']),
      limitations: _strings(json['limitations']),
    );
  }

  final String summary;

  /// `en_uso`, `en_reparacion` or `indeterminado`.
  final String vehicleState;
  final List<String> audioObservations;
  final List<String> imageObservations;
  final List<PossibleCause> possibleCauses;
  final List<String> recommendedTests;
  final List<String> safetyWarnings;
  final List<String> limitations;
}

class PossibleCause {
  const PossibleCause({
    required this.cause,
    required this.confidence,
    required this.reasoning,
    required this.basedOn,
  });

  factory PossibleCause.fromJson(Map<String, dynamic> json) => PossibleCause(
        cause: json['cause'] as String,
        confidence: (json['confidence'] as num).toDouble(),
        reasoning: json['reasoning'] as String,
        basedOn: _strings(json['based_on']),
      );

  final String cause;

  /// Between 0.0 and 1.0.
  final double confidence;
  final String reasoning;

  /// `audio`, `image` and/or `ambos`.
  final List<String> basedOn;
}

/// Who produced a persisted analysis, from `GET /diagnostics/{id}/analysis`.
class AnalysisMetadata {
  const AnalysisMetadata({required this.provider, required this.model});

  factory AnalysisMetadata.fromJson(Map<String, dynamic> json) => AnalysisMetadata(
        provider: json['provider'] as String,
        model: json['model'] as String?,
      );

  /// `stub`, `gemini`, ...
  final String provider;
  final String? model;
}

List<String> _strings(Object? value) =>
    (value as List? ?? const []).map((item) => item as String).toList();
