from pathlib import Path
from typing import ClassVar
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models import Diagnostic, DiagnosticEvidence
from app.models.enums import DiagnosticEvidenceType
from app.repositories.diagnostic_evidence import DiagnosticEvidenceRepository
from app.services.storage_service import StorageService

EVIDENCES_LOCKED_DETAIL = (
    "No se pueden modificar las evidencias porque el diagnóstico ya tiene un análisis de IA."
)


class DiagnosticEvidenceService:
    _ALLOWED: ClassVar[dict[str, tuple[DiagnosticEvidenceType, set[str], int]]] = {
        ".jpg": (DiagnosticEvidenceType.IMAGE, {"image/jpeg"}, 10 * 1024 * 1024),
        ".jpeg": (DiagnosticEvidenceType.IMAGE, {"image/jpeg"}, 10 * 1024 * 1024),
        ".png": (DiagnosticEvidenceType.IMAGE, {"image/png"}, 10 * 1024 * 1024),
        ".webp": (DiagnosticEvidenceType.IMAGE, {"image/webp"}, 10 * 1024 * 1024),
        ".mp3": (DiagnosticEvidenceType.AUDIO, {"audio/mpeg"}, 25 * 1024 * 1024),
        ".wav": (DiagnosticEvidenceType.AUDIO, {"audio/wav", "audio/x-wav"}, 25 * 1024 * 1024),
        ".m4a": (DiagnosticEvidenceType.AUDIO, {"audio/mp4", "audio/x-m4a", "audio/m4a"}, 25 * 1024 * 1024),
        ".mp4": (DiagnosticEvidenceType.VIDEO, {"video/mp4"}, 100 * 1024 * 1024),
        ".mov": (DiagnosticEvidenceType.VIDEO, {"video/quicktime"}, 100 * 1024 * 1024),
        ".webm": (DiagnosticEvidenceType.VIDEO, {"video/webm"}, 100 * 1024 * 1024),
    }

    def __init__(
        self,
        repository: DiagnosticEvidenceRepository | None = None,
        storage: StorageService | None = None,
    ) -> None:
        self.repository = repository or DiagnosticEvidenceRepository()
        self.storage = storage or StorageService()

    def create(
        self, db: Session, diagnostic_id: int, upload: UploadFile, description: str | None
    ) -> DiagnosticEvidence:
        diagnostic = db.get(Diagnostic, diagnostic_id)
        if not diagnostic:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic not found")
        self._ensure_evidences_editable(diagnostic)
        original_name = Path(upload.filename or "").name
        extension = Path(original_name).suffix.lower()
        allowed = self._ALLOWED.get(extension)
        mime_type = (upload.content_type or "").lower().split(";", 1)[0].strip()
        if not original_name or allowed is None or mime_type not in (allowed[1] if allowed else set()):
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")
        evidence_type, _, max_size = allowed
        content = upload.file.read(max_size + 1)
        if len(content) > max_size:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File exceeds size limit")
        detected_mime_type = self._detect_mime_type(content)
        if detected_mime_type not in allowed[1]:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File content does not match type")
        stored_name = f"{uuid4().hex}{extension}"
        relative_path = self.storage.save_file(diagnostic_id, stored_name, content)
        evidence = DiagnosticEvidence(
            diagnostic_id=diagnostic_id,
            evidence_type=evidence_type,
            file_name=original_name,
            file_path=relative_path,
            mime_type=mime_type,
            file_size=len(content),
            description=description,
        )
        try:
            db.add(evidence)
            db.commit()
            db.refresh(evidence)
        except Exception:
            db.rollback()
            self.storage.delete_file(relative_path)
            raise
        return evidence

    @staticmethod
    def _detect_mime_type(content: bytes) -> str | None:
        """Recognize the supported formats' signatures; do not trust an upload header alone."""
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            return "image/webp"
        if content.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3")):
            return "audio/mpeg"
        if content.startswith(b"RIFF") and content[8:12] == b"WAVE":
            return "audio/wav"
        if content.startswith(b"\x1aE\xdf\xa3") and b"webm" in content[:64].lower():
            return "video/webm"
        if len(content) >= 12 and content[4:8] == b"ftyp":
            brand = content[8:16]
            if brand.startswith(b"qt"):
                return "video/quicktime"
            if b"M4A" in brand:
                return "audio/mp4"
            return "video/mp4"
        return None

    @staticmethod
    def _ensure_evidences_editable(diagnostic: Diagnostic) -> None:
        """The persisted AI analysis was generated from the current evidences and is never
        regenerated, so they are frozen once it exists."""
        if diagnostic.analysis is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EVIDENCES_LOCKED_DETAIL)

    def delete(self, db: Session, evidence: DiagnosticEvidence) -> None:
        self._ensure_evidences_editable(evidence.diagnostic)
        # A missing file is intentionally harmless: the database record still must be removable.
        self.storage.delete_file(evidence.file_path)
        db.delete(evidence)
        db.commit()
