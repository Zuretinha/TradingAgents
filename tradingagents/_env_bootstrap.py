from __future__ import annotations

import importlib.util
import os
import warnings
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

_HUB_DIRECTORY_NAME = "00_master_hub"
_ROUTER_RELATIVE_PATH = (
    Path("04_operations")
    / "Antigravity"
    / "01_projects"
    / "zuretaclaw"
    / "05_runtime"
    / "master_secrets.py"
)


def _candidate_router_paths() -> list[Path]:
    candidates: list[Path] = []
    override = str(os.environ.get("ZURETACLAW_MASTER_SECRETS_MODULE") or "").strip()
    if override:
        candidates.append(Path(override).expanduser())

    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        if parent.name == _HUB_DIRECTORY_NAME:
            candidates.append(parent / _ROUTER_RELATIVE_PATH)
            break

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(candidate)
    return deduped


def _load_router_module(module_path: Path):
    spec = importlib.util.spec_from_file_location("zuretaclaw_master_secrets_runtime", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_project_local_env() -> None:
    local_env = find_dotenv(usecwd=True)
    if local_env:
        load_dotenv(local_env, override=False)

    enterprise_env = find_dotenv(".env.enterprise", usecwd=True)
    if enterprise_env:
        load_dotenv(enterprise_env, override=False)


def bootstrap_runtime_env() -> None:
    for candidate in _candidate_router_paths():
        if not candidate.exists():
            continue
        try:
            module = _load_router_module(candidate)
            init_fn = getattr(module, "init_master_secrets", None)
            if callable(init_fn):
                init_fn()
                return
            warnings.warn(f"Secrets router at {candidate} does not expose init_master_secrets().")
        except Exception as exc:
            warnings.warn(f"Failed to load secrets router {candidate}: {exc}")
        break

    _load_project_local_env()
