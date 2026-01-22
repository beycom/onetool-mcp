"""Secrets loading for ot-bench.

Loads bench secrets from bench-secrets.yaml, separate from ot-serve secrets.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ot.logging import LogSpan
from ot.paths import get_effective_cwd, get_global_dir

# Cached bench secrets
_bench_secrets: dict[str, str] | None = None


def _find_bench_secrets_file() -> Path | None:
    """Find bench-secrets.yaml file.

    Resolution order:
    1. .onetool/bench-secrets.yaml (project-level)
    2. ~/.onetool/bench-secrets.yaml (global)

    Returns:
        Path to bench-secrets.yaml if found, None otherwise
    """
    # Project-level
    project_path = get_effective_cwd() / ".onetool" / "bench-secrets.yaml"
    if project_path.exists():
        return project_path

    # Global
    global_path = get_global_dir() / "bench-secrets.yaml"
    if global_path.exists():
        return global_path

    return None


def load_bench_secrets() -> dict[str, str]:
    """Load bench secrets from bench-secrets.yaml.

    Returns:
        Dictionary of secret name -> value
    """
    global _bench_secrets

    if _bench_secrets is not None:
        return _bench_secrets

    secrets_path = _find_bench_secrets_file()

    with LogSpan(
        span="bench.secrets.load",
        path=str(secrets_path) if secrets_path else "not_found",
    ) as span:
        if secrets_path is None:
            span.add(error="bench-secrets.yaml not found")
            _bench_secrets = {}
            return _bench_secrets

        try:
            with secrets_path.open() as f:
                raw_data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:
            span.add(error=str(e))
            _bench_secrets = {}
            return _bench_secrets

        if raw_data is None:
            span.add(count=0)
            _bench_secrets = {}
            return _bench_secrets

        # Convert all values to strings
        _bench_secrets = {k: str(v) for k, v in raw_data.items() if v is not None}
        span.add(count=len(_bench_secrets))
        return _bench_secrets


def get_bench_secret(name: str) -> str:
    """Get a bench secret by name.

    Args:
        name: Secret name (e.g., "OPENAI_API_KEY")

    Returns:
        Secret value, or empty string if not found
    """
    secrets = load_bench_secrets()
    return secrets.get(name, "")
