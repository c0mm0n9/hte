from .base import MediaProvider  # noqa: F401
from .hive_ai import HiveAIMediaProvider  # noqa: F401
from .local_sample import LocalSampleMediaProvider  # noqa: F401


def get_provider(name: str) -> MediaProvider:
    normalized = (name or "").strip().lower()
    if normalized in {"hive_ai", "hive", ""}:
        return HiveAIMediaProvider()
    if normalized in {"local_sample", "local"}:
        return LocalSampleMediaProvider()
    raise ValueError(f"Unknown media provider '{name}'")
