from abc import ABC, abstractmethod

from ..config import Settings
from ..schemas import AIDetectResponse


class TextAIProvider(ABC):
    @abstractmethod
    async def detect(self, text: str, settings: Settings) -> AIDetectResponse:
        ...


def get_provider(name: str) -> TextAIProvider:
    normalized = (name or "").strip().lower()
    if normalized in {"sapling", ""}:
        from .sapling import SaplingTextAIProvider
        return SaplingTextAIProvider()
    raise ValueError(f"Unknown AI text detector provider: {name}")
