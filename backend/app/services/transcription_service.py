from typing import Protocol


class TranscriptionService(Protocol):
    """Interface for audio/video transcription providers."""

    def transcribe(self, media_urls: list[str]) -> list[str]: ...


class StubTranscriptionService:
    """Placeholder that makes the absence of transcription explicit."""

    def transcribe(self, media_urls: list[str]) -> list[str]:
        if not media_urls:
            return []
        return ["Audio/video was supplied, but transcription is not configured yet."]
