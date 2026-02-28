import re
from typing import Literal, Optional, Tuple

# Portal-generated key format: UUID or UUID-agent or UUID-control
API_KEY_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(-agent|-control)?$",
    re.IGNORECASE,
)


def parse_api_key(key: Optional[str]) -> Tuple[bool, Optional[Literal["agent", "control"]]]:
    """Validate API key format and return (valid, mode). Mode from suffix; default 'agent'."""
    if not key or not key.strip():
        return False, None
    k = key.strip()
    if not API_KEY_PATTERN.fullmatch(k):
        return False, None
    if k.lower().endswith("-control"):
        return True, "control"
    return True, "agent"  # uuid alone or -agent
