from typing import Protocol


class VisionService(Protocol):
    """Interface for an image analysis provider. No provider key is stored here."""

    def analyze_images(self, image_urls: list[str]) -> list[str]: ...


class StubVisionService:
    """Safe placeholder until a configured vision provider is integrated."""

    def analyze_images(self, image_urls: list[str]) -> list[str]:
        return [f"Photo supplied for mechanic review: {url}" for url in image_urls]
