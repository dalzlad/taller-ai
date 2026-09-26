import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

/// Base URL of the TallerAI backend. Change this when testing against a
/// physical device or a deployed environment.
const String backendBaseUrl = 'http://localhost:8000';

const Duration _requestTimeout = Duration(seconds: 10);

/// Timeout for `POST /diagnostics/{id}/analyze`. The backend gives up on
/// Gemini after GEMINI_TIMEOUT_SECONDS (30 s by default); waiting three times
/// that long means the user sees the backend's own readable 502 instead of a
/// client-side timeout. Raise it if GEMINI_TIMEOUT_SECONDS goes above ~75 s.
const Duration aiAnalysisTimeout = Duration(seconds: 90);

/// HTTP client used by [getJson], [getJsonList] and [postJson]. Tests replace
/// it with a `MockClient` from `package:http/testing.dart`.
http.Client apiHttpClient = http.Client();

/// Raised when the backend responds with a non-2xx status or the request
/// could not be completed at all. [message] is always derived from the
/// backend's real response body (or the raw transport error) so it can be
/// shown to the user as-is.
class ApiException implements Exception {
  ApiException(this.statusCode, this.message);

  final int? statusCode;
  final String message;

  @override
  String toString() =>
      statusCode != null ? 'Error HTTP $statusCode: $message' : message;
}

/// GET returning a single JSON object.
Future<Map<String, dynamic>> getJson(String path) async {
  final uri = Uri.parse('$backendBaseUrl$path');
  final body = await _send(uri, () => apiHttpClient.get(uri));
  return jsonDecode(body) as Map<String, dynamic>;
}

/// GET returning a JSON array of objects. [query] values are sent as URL
/// query parameters (e.g. `{'q': 'ana'}` → `?q=ana`).
Future<List<Map<String, dynamic>>> getJsonList(
  String path, {
  Map<String, String>? query,
}) async {
  final uri = Uri.parse('$backendBaseUrl$path').replace(queryParameters: query);
  final body = await _send(uri, () => apiHttpClient.get(uri));
  return (jsonDecode(body) as List).cast<Map<String, dynamic>>();
}

Future<Map<String, dynamic>> postJson(
  String path,
  Map<String, dynamic> body, {
  Duration timeout = _requestTimeout,
}) async {
  final uri = Uri.parse('$backendBaseUrl$path');
  final responseBody = await _send(
    uri,
    () => apiHttpClient.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    ),
    timeout: timeout,
  );
  return jsonDecode(responseBody) as Map<String, dynamic>;
}

/// Runs [request] and returns the body of a 2xx response; anything else is
/// turned into an [ApiException] with a readable message.
Future<String> _send(
  Uri uri,
  Future<http.Response> Function() request, {
  Duration timeout = _requestTimeout,
}) async {
  final http.Response response;
  try {
    response = await request().timeout(timeout);
  } on TimeoutException {
    throw ApiException(
      null,
      'El servidor no respondió en ${timeout.inSeconds} s ($uri). Intenta de nuevo.',
    );
  } catch (error) {
    throw ApiException(null, 'No se pudo conectar a $uri:\n$error');
  }

  if (response.statusCode >= 200 && response.statusCode < 300) {
    return response.body;
  }
  throw ApiException(response.statusCode, _formatErrorBody(response.body));
}

/// FastAPI errors are `{"detail": "..."}` for HTTPException or
/// `{"detail": [{"loc": [...], "msg": "...", ...}, ...]}` for 422 validation
/// errors. Both are unwrapped into plain, readable text.
String _formatErrorBody(String body) {
  try {
    final decoded = jsonDecode(body);
    final detail = decoded is Map ? decoded['detail'] : null;
    if (detail is String) {
      return detail;
    }
    if (detail is List) {
      return detail.map((item) {
        if (item is Map) {
          final loc = (item['loc'] as List?)?.join(' -> ') ?? '';
          final msg = item['msg'] ?? item.toString();
          return loc.isEmpty ? '$msg' : '$loc: $msg';
        }
        return item.toString();
      }).join('\n');
    }
    return body;
  } catch (_) {
    return body;
  }
}
