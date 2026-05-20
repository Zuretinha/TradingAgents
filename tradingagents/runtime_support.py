"""Helpers for governed TradingAgents runtime configuration and exports."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from tradingagents.dataflows.utils import safe_ticker_component

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ADVISORY_DISCLAIMER = (
    "Research/advisory output only. No live execution or tax filing action performed."
)


def project_path(*parts: str) -> Path:
    """Return a path rooted at the governed trading_agents project."""
    return PROJECT_ROOT.joinpath(*parts)


def governed_default_paths() -> Dict[str, str]:
    """Return the project-governed default storage locations."""
    return {
        "results_dir": str(project_path("05_exports", "runtime_logs")),
        "data_cache_dir": str(project_path("06_data", "cache")),
        "memory_log_path": str(project_path("06_data", "memory", "trading_memory.md")),
    }


def utc_now_iso() -> str:
    """Return a compact UTC timestamp suitable for audit records."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def build_runtime_config(
    base_config: Dict[str, Any],
    ticker: str,
    *,
    max_debate_rounds: Optional[int] = None,
    read_only: bool = False,
) -> Dict[str, Any]:
    """Copy a base config and apply ticker-specific runtime policy."""
    config = copy.deepcopy(base_config)
    ticker_upper = ticker.upper()

    if max_debate_rounds is not None:
        config["max_debate_rounds"] = max_debate_rounds

    if ticker_upper.endswith(".AX"):
        config["global_news_queries"] = [
            "Reserve Bank of Australia RBA interest rates inflation",
            "ASX 200 earnings Australian economic outlook",
            "geopolitical risk trade China Australia",
            "iron ore copper gold mining commodities",
        ]
    elif ticker_upper.endswith(("-USD", "-AUD", "-EUR")):
        config["global_news_queries"] = [
            "cryptocurrency market regulatory sec etf",
            "federal reserve interest rates inflation",
            f"{ticker_upper.split('-')[0]} crypto news analysis",
            "crypto on-chain whale accumulation",
        ]

    if read_only:
        config["filesystem_write_enabled"] = False
        config["state_logging_enabled"] = False
        config["memory_log_enabled"] = False
        config["checkpoint_enabled"] = False
        config["tax_casework_api_enabled"] = False

    return config


def build_runtime_summary(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return the runtime controls that matter for auditability."""
    return {
        "llm_provider": config.get("llm_provider"),
        "deep_think_llm": config.get("deep_think_llm"),
        "quick_think_llm": config.get("quick_think_llm"),
        "backend_url": config.get("backend_url"),
        "max_debate_rounds": config.get("max_debate_rounds"),
        "checkpoint_enabled": bool(config.get("checkpoint_enabled", False)),
        "filesystem_write_enabled": bool(config.get("filesystem_write_enabled", True)),
        "state_logging_enabled": bool(config.get("state_logging_enabled", True)),
        "memory_log_enabled": bool(config.get("memory_log_enabled", True)),
        "tax_casework_api_enabled": bool(config.get("tax_casework_api_enabled", False)),
        "tax_casework_api_url": config.get("tax_casework_api_url"),
        "results_dir": config.get("results_dir"),
        "data_cache_dir": config.get("data_cache_dir"),
        "memory_log_path": config.get("memory_log_path"),
    }


def _detect_live_execution_terms(text: str) -> list[str]:
    lowered = text.lower()
    candidates = [
        "submit to broker",
        "send order to broker",
        "execute in the live market",
        "auto-execute",
        "place the order automatically",
    ]
    return [term for term in candidates if term in lowered]


def build_validation_snapshot(
    state: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Return a compact validation summary for persisted outputs."""
    execution_plan = str(state.get("execution_plan", "") or "")
    tax_signal = str(state.get("tax_event_signal", "") or "")

    return {
        "advisory_disclaimer_included": True,
        "execution_plan_present": bool(execution_plan.strip()),
        "tax_signal_present": bool(tax_signal.strip()),
        "filesystem_write_enabled": bool(config.get("filesystem_write_enabled", True)),
        "state_logging_enabled": bool(config.get("state_logging_enabled", True)),
        "memory_log_enabled": bool(config.get("memory_log_enabled", True)),
        "checkpoint_enabled": bool(config.get("checkpoint_enabled", False)),
        "tax_casework_api_enabled": bool(config.get("tax_casework_api_enabled", False)),
        "live_execution_terms_detected": _detect_live_execution_terms(execution_plan),
    }


def build_export_record(
    ticker: str,
    trade_date: str,
    state: Dict[str, Any],
    decision: Any,
    config: Dict[str, Any],
    *,
    export_kind: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a governed export record for scripts and API responses."""
    record: Dict[str, Any] = {
        "ticker": ticker,
        "trade_date": trade_date,
        "generated_at_utc": utc_now_iso(),
        "export_kind": export_kind,
        "decision": decision,
        "full_report": state.get("final_trade_decision", ""),
        "execution_plan": state.get("execution_plan", "Not generated"),
        "tax_event_signal": state.get(
            "tax_event_signal", "No tax analysis performed"
        ),
        "advisory_disclaimer": ADVISORY_DISCLAIMER,
        "runtime": build_runtime_summary(config),
    }
    record["validation_snapshot"] = build_validation_snapshot(state, config)
    if extra:
        record.update(extra)
    return record


def export_json(record: Dict[str, Any], *relative_parts: str) -> str:
    """Write a JSON export under the governed project root."""
    export_path = project_path(*relative_parts)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return str(export_path)


def ticker_filename(ticker: str, suffix: str) -> str:
    """Return a safe filename stem for the given ticker and suffix."""
    safe_ticker = safe_ticker_component(ticker).replace("/", "_")
    return f"{safe_ticker}_{suffix}"
