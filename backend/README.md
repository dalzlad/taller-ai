# TallerAI backend

Base backend for TallerAI, an assistant for mechanical workshops. This first phase provides only the API foundation: configuration, PostgreSQL connectivity, SQLAlchemy, Alembic, Docker, and a liveness endpoint. It deliberately contains no business features or AI implementation.

## Requirements

- Python 3.11 or newer
- PostgreSQL 16 (only when running without Docker)
- Docker Desktop (optional, recommended)

## Run locally

1. Create and activate a virtual environment.
2. Install the package and development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

3. Copy `.env.example` to `.env` and adjust `DATABASE_URL` if necessary. The repository includes a local development `.env` for convenience; do not commit real secrets.
4. Start PostgreSQL and then run the API:

```powershell
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/health. Expected response:

```json
{"status": "ok"}
```

Interactive documentation is available at http://127.0.0.1:8000/docs.

## Docker

The compose configuration starts the API and PostgreSQL together:

```powershell
docker compose up --build
```

The API is exposed on port `8000` and PostgreSQL on `5432`. Stop the stack with `docker compose down`; add `-v` only if you explicitly want to delete the database volume.

## Migrations

Alembic is configured to use `DATABASE_URL` from `.env`:

```powershell
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

The initial domain migration creates customers, vehicles, diagnostics, diagnostic media,
findings, and work orders. Apply it before using the domain endpoints:

```powershell
alembic upgrade head
```

Docker Compose applies migrations automatically before starting the API.

## Preliminary diagnostic agent

`POST /diagnostics/{id}/analyze` builds a provider-neutral `DiagnosticContext` with vehicle data,
reported symptoms, mechanic notes, history and multimedia file references (never file bytes). The
agent delegates generation exclusively to `AIProvider`, selected through `AIProviderFactory` from
`AI_PROVIDER`. `AI_PROVIDER=stub` remains the default and runs offline. `AI_PROVIDER=openai` now
constructs an adapter boundary and an internal request representation, but its analysis method
deliberately returns a controlled "integration is not enabled yet" error; no external API or credential
is used. Unsupported provider names return a controlled configuration error.

`AISafety` validates every provider result before it is returned. It rejects language that presents
a fault as confirmed or definitive and ensures the limitation "La evaluación es preliminar y requiere
confirmación física por un mecánico." is present. When the analysis reports `vehicle_state:
"en_reparacion"`, `AISafety` also guarantees the limitation explaining that a disassembled-engine
photo was not used as evidence of the audio symptom's cause, and a safety warning against starting or
handling that engine, even if the provider's own output omitted them.

### Persisted analysis

The first successful analysis of a diagnostic is stored in `diagnostic_ai_analyses` (at most one row
per diagnostic) together with the provider name (`stub`, `gemini`, ...), its model and the analysis
contract version, and the diagnostic moves from `CREATED` to `REVIEW`. Later `POST .../analyze` calls
return the stored analysis with the same response shape, without calling the provider again. A stored
analysis whose contract version or content no longer validates is regenerated. Failed analyses (422,
502, 503) persist nothing. `GET /diagnostics/{id}/analysis` returns the stored analysis with its
metadata and never calls the provider (404 if there is none). There is no analysis history yet.

`GEMINI_TIMEOUT_SECONDS` (default `30`, maximum `300`) sets the timeout of the Gemini HTTP call.

### Analysis output shape

`PreliminaryDiagnosticAnalysis` (`app/schemas/ai_analysis.py`) is:

- `summary`: short case summary, stating whether the vehicle appears to be in normal use or
  already under repair.
- `vehicle_state`: `"en_uso"`, `"en_reparacion"`, or `"indeterminado"`.
- `observations.audio` / `observations.image`: findings kept separate by evidence channel, so an
  audio-only or image-only finding is never presented as corroborated by the other channel.
- `possible_causes[]`: each with `cause`, `confidence` (0.0–1.0), `reasoning`, and `based_on`
  (`"audio"`, `"image"` and/or `"ambos"`) naming which evidence supports it.
- `recommended_tests`, `safety_warnings`, `limitations`: as before.

The `gemini` provider's system prompt walks the model through classifying each image
(`vehiculo_exterior`, `motor_capo_abierto`, `motor_desarmado_reparacion`, `componente_especifico`,
`otro`) before reasoning about causes, and forbids using a `motor_desarmado_reparacion` image as
evidence of the audio symptom's cause — that image is context only, proving the vehicle is already
being serviced. If the vehicle's state is ambiguous or contradictory between audio and image, the
model must set `vehicle_state: "indeterminado"` and lower every cause's confidence accordingly.

`OpenAIRequestBuilder` separates system instructions, textual context, evidence metadata and storage
references. It does not load files, encode base64, access the database or perform HTTP calls. The
future OpenAI adapter can therefore be enabled without changing the agent, endpoint, models or storage.

## Domain API

The current REST API exposes the initial workshop workflow:

- `POST`, `GET /customers`
- `POST`, `GET /vehicles`; `GET /vehicles/{id}`
- `POST`, `GET /diagnostics`; `GET /diagnostics/{id}`
- `POST`, `GET /diagnostics/{id}/media`
- `POST`, `GET /diagnostics/{id}/evidences`; `GET`, `DELETE /evidences/{id}`
- `GET /evidences/{id}/file`
- `POST`, `GET /diagnostics/{id}/findings`
- `POST`, `GET /work-orders`

Creation validates parent resources, vehicle identifiers and dates, media type, finding
confidence, money values, and the defined diagnostic/work-order states. API documentation is
available at `/docs` while the server is running.

## Diagnostic evidence files

Upload a multipart file with `POST /diagnostics/{diagnostic_id}/evidences`. The `file` field is required and
`description` is optional. For example:

```powershell
curl.exe -X POST http://127.0.0.1:8000/diagnostics/15/evidences -F "file=@foto_motor.jpg;type=image/jpeg" -F "description=Ruido en el motor"
```

Supported types are JPG/JPEG, PNG and WEBP images (maximum 10 MB); MP3, WAV and M4A audio (25 MB); and
MP4, MOV and WEBM video (100 MB). Both extension and MIME type must match. Files are stored locally under
`storage/diagnostics/{diagnostic_id}/` using a generated UUID filename; the original filename is metadata only.
`GET /evidences/{id}/file` serves the file, and deleting an evidence also removes its local file when present.
The `STORAGE_PATH` setting can relocate the local storage root. This boundary is intentionally encapsulated in
`StorageService` so it can later be replaced by external storage without changing the routes.

## Tests

```powershell
pytest
```

## Structure

```text
app/
  api/           HTTP routes
  core/          settings and future cross-cutting concerns
  db/            SQLAlchemy base, engine and session dependency
  models/        future ORM models
  schemas/       future Pydantic schemas
  repositories/  future persistence layer
  services/      future application services
  agents/        reserved for future AI integrations
tests/           pytest suite
alembic/         migration environment
```
