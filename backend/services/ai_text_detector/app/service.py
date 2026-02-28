from .config import Settings
from .providers import get_provider
from .schemas import AIDetectResponse


async def run_detection(text: str, settings: Settings) -> AIDetectResponse:
    provider = get_provider(settings.provider)
    return await provider.detect(text, settings)
