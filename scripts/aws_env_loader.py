"""
Load and merge .env files from backend/ and backend/services/<svc>/.
Returns per-service env dicts, a global (backend) env dict, and the list of
endpoint keys that will be overwritten for AWS deployment.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Keys that hold endpoint URLs and will be replaced with AWS values (ALB, RDS, etc.)
ENDPOINT_KEYS: List[str] = [
    "POSTGRES_HOST",
    "AGENT_GATEWAY_AI_TEXT_DETECTOR_URL",
    "AGENT_GATEWAY_MEDIA_CHECKING_URL",
    "AGENT_GATEWAY_FACT_CHECKING_URL",
    "AGENT_GATEWAY_INFO_GRAPH_URL",
    "AGENT_GATEWAY_CONTENT_SAFETY_URL",
    "AGENT_GATEWAY_MEDIA_EXPLANATION_URL",
    "AGENT_GATEWAY_PORTAL_BASE_URL",
    "GATEWAY_fact_check_base_url",
    "GATEWAY_media_check_base_url",
]

# Service names under backend/services/ that have .env or .env.example (order = merge order)
SERVICE_NAMES: List[str] = [
    "agent_gateway",
    "content_safety",
    "media_checking",
    "media_explanation",
    "fact_checking",
    "ai_text_detector",
    "info_graph",
]


def _parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a .env file into key=value dict. Skips comments and empty lines."""
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and (
            (value.startswith('"') and value.endswith('"'))
            or (value.startswith("'") and value.endswith("'"))
        ):
            value = value[1:-1].replace("\\n", "\n").replace("\\'", "'").replace('\\"', '"')
        out[key] = value
    return out


def _merge_env(base: Dict[str, str], override: Dict[str, str]) -> Dict[str, str]:
    merged = dict(base)
    for k, v in override.items():
        if v is not None and v != "":
            merged[k] = v
    return merged


def load_all_env(repo_root: Path) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str], List[str]]:
    """
    Load env from backend/.env and backend/services/<svc>/.env (or .env.example).

    Returns:
        - per_service: service_name -> env dict (e.g. "agent_gateway" -> {...})
        - global_env: merged backend env (POSTGRES_*, etc.)
        - endpoint_keys: list of keys that should be overwritten with AWS endpoints
    """
    backend_dir = repo_root / "backend"
    services_dir = backend_dir / "services"

    global_env: Dict[str, str] = {}
    backend_env_path = backend_dir / ".env"
    if backend_env_path.exists():
        global_env = _parse_env_file(backend_env_path)
    backend_example = backend_dir / ".env.example"
    if backend_example.exists():
        example = _parse_env_file(backend_example)
        for k, v in example.items():
            if k not in global_env:
                global_env[k] = v

    per_service: Dict[str, Dict[str, str]] = {}
    for name in SERVICE_NAMES:
        svc_dir = services_dir / name
        env_path = svc_dir / ".env"
        example_path = svc_dir / ".env.example"
        if env_path.exists():
            per_service[name] = _parse_env_file(env_path)
        elif example_path.exists():
            per_service[name] = _parse_env_file(example_path)
        else:
            per_service[name] = {}

    # Merge order: global first, then each service (later overrides)
    merged_global = dict(global_env)
    for name in SERVICE_NAMES:
        if name in per_service:
            merged_global = _merge_env(merged_global, per_service[name])

    return per_service, merged_global, ENDPOINT_KEYS


def get_env_for_service(
    service_name: str,
    per_service: Dict[str, Dict[str, str]],
    global_env: Dict[str, str],
) -> Dict[str, str]:
    """Build a single env dict for a given service (global + service-specific)."""
    base = dict(global_env)
    if service_name in per_service:
        base = _merge_env(base, per_service[service_name])
    return base
