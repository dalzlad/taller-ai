from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes.evidences import evidence_service
from app.services.storage_service import StorageService


def _create_diagnostic(client: TestClient) -> int:
    customer = client.post(
        "/customers", json={"name": "Luis Perez", "phone": "+57 300 555 1234", "email": "luis@example.com"}
    ).json()
    vehicle = client.post(
        "/vehicles",
        json={"customer_id": customer["id"], "plate": "ABC123", "brand": "Mazda", "model": "3", "year": 2020, "mileage": 0},
    ).json()
    response = client.post(
        "/diagnostics", json={"vehicle_id": vehicle["id"], "reported_symptoms": "Ruido al frenar"}
    )
    assert response.status_code == 201
    return response.json()["id"]


def _content_for(mime_type: str) -> bytes:
    return {
        "image/jpeg": b"\xff\xd8\xffsample",
        "image/png": b"\x89PNG\r\n\x1a\nsample",
        "audio/mpeg": b"ID3sample",
        "video/mp4": b"\x00\x00\x00\x18ftypisomsample",
    }[mime_type]


def _upload(client: TestClient, diagnostic_id: int, name: str, mime_type: str, content: bytes | None = None):
    content = content if content is not None else _content_for(mime_type)
    return client.post(
        f"/diagnostics/{diagnostic_id}/evidences",
        files={"file": (name, content, mime_type)},
        data={"description": "Evidencia de prueba"},
    )


def test_upload_list_get_download_and_delete_evidences(client: TestClient, tmp_path: Path) -> None:
    original_storage = evidence_service.storage
    evidence_service.storage = StorageService(tmp_path)
    try:
        diagnostic_id = _create_diagnostic(client)
        image = _upload(client, diagnostic_id, "motor.jpg", "image/jpeg")
        assert image.status_code == 201
        evidence_id = image.json()["id"]
        assert client.get(f"/evidences/{evidence_id}").json()["file_name"] == "motor.jpg"
        downloaded = client.get(f"/evidences/{evidence_id}/file")
        assert downloaded.status_code == 200
        assert downloaded.content == _content_for("image/jpeg")

        stored_path = next((tmp_path / "diagnostics" / str(diagnostic_id)).iterdir())
        assert stored_path and stored_path.exists()
        assert client.delete(f"/evidences/{evidence_id}").status_code == 204
        assert not stored_path.exists()
        assert client.get(f"/evidences/{evidence_id}").status_code == 404

        audio = _upload(client, diagnostic_id, "cliente.mp3", "audio/mpeg")
        video = _upload(client, diagnostic_id, "motor.mp4", "video/mp4")
        assert [response.status_code for response in (audio, video)] == [201, 201]
        assert [response.json()["evidence_type"] for response in (audio, video)] == ["AUDIO", "VIDEO"]
        evidences = client.get(f"/diagnostics/{diagnostic_id}/evidences")
        assert evidences.status_code == 200
        assert len(evidences.json()) == 2
    finally:
        evidence_service.storage = original_storage


def test_evidence_validation_and_missing_diagnostic(client: TestClient, tmp_path: Path) -> None:
    original_storage = evidence_service.storage
    evidence_service.storage = StorageService(tmp_path)
    try:
        diagnostic_id = _create_diagnostic(client)
        assert _upload(client, diagnostic_id, "script.jpg.exe", "image/jpeg").status_code == 415
        assert _upload(
            client, diagnostic_id, "photo.jpg", "application/octet-stream", _content_for("image/jpeg")
        ).status_code == 415
        assert _upload(client, 999, "photo.jpg", "image/jpeg").status_code == 404
        too_large = _upload(
            client, diagnostic_id, "large.jpg", "image/jpeg", b"\xff\xd8\xff" + b"x" * (10 * 1024 * 1024)
        )
        assert too_large.status_code == 413
    finally:
        evidence_service.storage = original_storage


def test_delete_evidence_with_missing_file_still_deletes_record(client: TestClient, tmp_path: Path) -> None:
    original_storage = evidence_service.storage
    evidence_service.storage = StorageService(tmp_path)
    try:
        diagnostic_id = _create_diagnostic(client)
        created = _upload(client, diagnostic_id, "motor.png", "image/png")
        evidence_id = created.json()["id"]
        stored_file = next((tmp_path / "diagnostics" / str(diagnostic_id)).iterdir())
        stored_file.unlink()
        assert client.delete(f"/evidences/{evidence_id}").status_code == 204
        assert client.get(f"/evidences/{evidence_id}").status_code == 404
    finally:
        evidence_service.storage = original_storage
