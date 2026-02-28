from abc import ABC, abstractmethod

from ..config import Settings
from ..schemas import FactCheckResponse


class FactChecker(ABC):
    @abstractmethod
    async def check_fact(
        self,
        fact: str,
        settings: Settings,
    ) -> FactCheckResponse:
        ...


def get_fact_checker(settings: Settings) -> FactChecker:
    # For now we only support Exa, but this is where
    # additional providers can be registered.
    from .exa import ExaFactChecker

    if settings.provider == "exa":
        return ExaFactChecker()

    raise ValueError(f"Unsupported fact checking provider: {settings.provider}")

