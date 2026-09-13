from pathlib import Path

from app.core.config import settings


class StorageService:
    """Local storage boundary; it can be replaced by an object-storage implementation later."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root or settings.storage_path).resolve()

    def save_file(self, diagnostic_id: int, stored_name: str, content: bytes) -> str:
        relative_path = Path("diagnostics") / str(diagnostic_id) / stored_name
        destination = self._resolve(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return relative_path.as_posix()

    def get_file(self, relative_path: str) -> Path | None:
        path = self._resolve(Path(relative_path))
        return path if path.is_file() else None

    def delete_file(self, relative_path: str) -> None:
        path = self._resolve(Path(relative_path))
        if path.is_file():
            path.unlink()

    def _resolve(self, relative_path: Path) -> Path:
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("Unsafe storage path")
        path = (self.root / relative_path).resolve()
        if self.root != path and self.root not in path.parents:
            raise ValueError("Unsafe storage path")
        return path
