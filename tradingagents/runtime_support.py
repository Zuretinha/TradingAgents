"""Helpers for governed TradingAgents runtime configuration and exports."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from tradingagents.dataflows.utils import safe_ticker_component

PROJECT_ROOT = Path(__file__).resolve().parents[4]
EXPORT_SCHEMA_VERSION = "2.0"
SIGNAL_HANDOFF_SCHEMA_VERSION = "1.0"
EXPERIMENT_RECORD_SCHEMA_VERSION = "1.0"
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


def _normalize_decision_payload(decision: Any) -> Dict[str, Any]:
    """Return a mapping view of the decision payload when possible."""
    if isinstance(decision, dict):
        return decision
    if hasattr(decision, "model_dump"):
        return decision.model_dump()  # type: ignore[no-any-return]
    if isinstance(decision, str):
        return {"rating": decision}
    return {}


def _as_text(value: Any) -> str:
    """Return a stripped string representation or an empty string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _first_text(*values: Any) -> str:
    """Return the first non-empty string candidate."""
    for value in values:
        text = _as_text(value)
        if text:
            return text
    return ""


def _extract_markdown_field(report: str, heading: str) -> str:
    """Extract a markdown field written as ``**Heading**: value``."""
    pattern = re.compile(
        rf"\*\*{re.escape(heading)}\*\*:\s*(.+?)(?:\n\n\*\*|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(report)
    if not match:
        return ""
    return match.group(1).strip()


def detect_asset_class(ticker: str) -> str:
    """Return a coarse asset-class label for the ticker."""
    ticker_upper = ticker.upper()
    if ticker_upper.endswith(("-USD", "-AUD", "-EUR")):
        return "crypto"
    if ticker_upper.endswith(".AX"):
        return "australian_equity"
    if ticker_upper.endswith((".HK", ".T", ".NS", ".L")):
        return "international_equity"
    return "us_equity_or_etf"


def _prompt_context_id(ticker: str) -> str:
    """Return the governed prompt context identifier for the ticker."""
    ticker_upper = ticker.upper()
    if ticker_upper.endswith(".AX"):
        return "asx_context_prompt"
    if ticker_upper.endswith(("-USD", "-AUD", "-EUR")):
        return "crypto_context_prompt"
    return "default_equity_context"


def _extract_rating(
    decision_payload: Dict[str, Any],
    full_report: str,
    fallback_decision: Any,
) -> str:
    """Return the best available position-rating string."""
    for key in ("rating", "decision", "action"):
        value = decision_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    report_rating = _extract_markdown_field(full_report, "Rating")
    if report_rating:
        return report_rating

    return _as_text(fallback_decision) or "Unspecified"


def _extract_price_target(decision_payload: Dict[str, Any], full_report: str) -> Optional[float]:
    """Return the best available numeric price target."""
    raw_value = decision_payload.get("price_target")
    if isinstance(raw_value, (int, float)):
        return float(raw_value)

    report_value = _extract_markdown_field(full_report, "Price Target")
    if not report_value:
        return None
    try:
        return float(str(report_value).replace(",", "").strip())
    except ValueError:
        return None


def _extract_time_horizon(decision_payload: Dict[str, Any], full_report: str) -> str:
    """Return the configured or reported time horizon."""
    return _first_text(
        decision_payload.get("time_horizon"),
        _extract_markdown_field(full_report, "Time Horizon"),
    )


def _extract_investment_thesis(decision_payload: Dict[str, Any], full_report: str) -> str:
    """Return the current thesis text."""
    return _first_text(
        decision_payload.get("investment_thesis"),
        decision_payload.get("thesis"),
        _extract_markdown_field(full_report, "Investment Thesis"),
    )


def _extract_executive_summary(decision_payload: Dict[str, Any], full_report: str) -> str:
    """Return the current executive summary text."""
    return _first_text(
        decision_payload.get("summary"),
        decision_payload.get("executive_summary"),
        _extract_markdown_field(full_report, "Executive Summary"),
    )


def _extract_stop_loss(decision_payload: Dict[str, Any], execution_plan: str) -> Optional[float]:
    """Return an invalidation or stop-loss level when present."""
    raw_value = decision_payload.get("stop_loss")
    if isinstance(raw_value, (int, float)):
        return float(raw_value)

    match = re.search(r"stop loss(?: at|:)?\s*\$?([0-9]+(?:\.[0-9]+)?)", execution_plan, re.I)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def build_research_summary(
    ticker: str,
    trade_date: str,
    full_report: str,
    execution_plan: str,
    decision_payload: Dict[str, Any],
    fallback_decision: Any,
) -> Dict[str, Any]:
    """Build the research summary block used by governed exports."""
    rating = _extract_rating(decision_payload, full_report, fallback_decision)
    investment_thesis = _extract_investment_thesis(decision_payload, full_report)
    executive_summary = _extract_executive_summary(decision_payload, full_report)
    stop_loss = _extract_stop_loss(decision_payload, execution_plan)
    risk_summary = _first_text(
        decision_payload.get("risk_summary"),
        f"Execution plan review required. Proposed stop loss: {stop_loss}"
        if stop_loss is not None
        else "",
        "Execution plan review required before any paper-routing action.",
    )

    return {
        "artifact_version": "1.0",
        "ticker": ticker,
        "trade_date": trade_date,
        "asset_class": detect_asset_class(ticker),
        "rating": rating,
        "executive_summary": executive_summary,
        "investment_thesis": investment_thesis,
        "risk_summary": risk_summary,
        "price_target": _extract_price_target(decision_payload, full_report),
        "time_horizon": _extract_time_horizon(decision_payload, full_report),
        "invalidation_condition": (
            f"Stop loss at {stop_loss}" if stop_loss is not None else "Human review required"
        ),
    }


def build_review_status(generated_at_utc: str) -> Dict[str, Any]:
    """Return the default review gate for governed exports."""
    checkpoints = [
        {
            "checkpoint_id": "research_note_review",
            "description": "Confirm the research note is internally coherent and source-aligned.",
            "status": "pending",
        },
        {
            "checkpoint_id": "signal_handoff_review",
            "description": "Approve or reject downstream paper-routing eligibility.",
            "status": "pending",
        },
        {
            "checkpoint_id": "experiment_log_review",
            "description": "Confirm the run is suitable for experiment-matrix comparison.",
            "status": "pending",
        },
    ]
    return {
        "review_required": True,
        "review_state": "pending_human_review",
        "approval_required_before_dispatch": True,
        "last_updated_utc": generated_at_utc,
        "checkpoints": checkpoints,
    }


def build_research_artifacts(
    ticker: str,
    trade_date: str,
    research_summary: Dict[str, Any],
    review_status: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the structured research-artifact bundle."""
    title_base = f"{ticker} {trade_date}"
    return {
        "market_research_note": {
            "title": f"{title_base} Market Research Note",
            "summary": research_summary.get("executive_summary"),
            "thesis": research_summary.get("investment_thesis"),
            "rating": research_summary.get("rating"),
            "asset_class": research_summary.get("asset_class"),
        },
        "investment_memo": {
            "title": f"{title_base} Investment Memo",
            "position_rating": research_summary.get("rating"),
            "thesis_summary": research_summary.get("investment_thesis"),
            "risk_summary": research_summary.get("risk_summary"),
            "time_horizon": research_summary.get("time_horizon"),
        },
        "thesis_tracker": {
            "status": "active",
            "current_rating": research_summary.get("rating"),
            "current_thesis": research_summary.get("investment_thesis"),
            "next_review_state": review_status.get("review_state"),
        },
        "catalyst_calendar": {
            "status": "manual_enrichment_required",
            "items": [],
        },
        "review_checkpoints": review_status.get("checkpoints", []),
    }


def build_signal_handoff(
    ticker: str,
    trade_date: str,
    generated_at_utc: str,
    research_summary: Dict[str, Any],
    config: Dict[str, Any],
    review_status: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the bounded downstream handoff contract."""
    return {
        "schema_version": SIGNAL_HANDOFF_SCHEMA_VERSION,
        "dispatch_ready": False,
        "ticker": ticker,
        "asset_class": research_summary.get("asset_class"),
        "timestamp_utc": generated_at_utc,
        "trade_date": trade_date,
        "rating": research_summary.get("rating"),
        "confidence": "unscored",
        "thesis_summary": research_summary.get("investment_thesis"),
        "risk_summary": research_summary.get("risk_summary"),
        "price_target": research_summary.get("price_target"),
        "time_horizon": research_summary.get("time_horizon"),
        "invalidation_condition": research_summary.get("invalidation_condition"),
        "model_provider": config.get("llm_provider"),
        "deep_reasoning_model": config.get("deep_think_llm"),
        "quick_reasoning_model": config.get("quick_think_llm"),
        "prompt_context_id": _prompt_context_id(ticker),
        "data_provenance": {
            "contract_reference": "12_docs/2026-05-19_governed_data_source_contract_v1.0.md",
            "default_vendor": "yfinance",
            "controlled_fallback_vendor": "alpha_vantage",
        },
        "human_review_status": review_status.get("review_state"),
    }


def build_experiment_context(
    ticker: str,
    trade_date: str,
    generated_at_utc: str,
    export_kind: str,
    config: Dict[str, Any],
    research_summary: Dict[str, Any],
    review_status: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the experiment-observation metadata used for matrix rebuilds."""
    return {
        "schema_version": EXPERIMENT_RECORD_SCHEMA_VERSION,
        "record_type": "experiment_observation",
        "ticker": ticker,
        "trade_date": trade_date,
        "generated_at_utc": generated_at_utc,
        "export_kind": export_kind,
        "asset_class": research_summary.get("asset_class"),
        "rating": research_summary.get("rating"),
        "provider": config.get("llm_provider"),
        "deep_think_llm": config.get("deep_think_llm"),
        "quick_think_llm": config.get("quick_think_llm"),
        "max_debate_rounds": config.get("max_debate_rounds"),
        "prompt_context_id": _prompt_context_id(ticker),
        "data_contract_reference": "12_docs/2026-05-19_governed_data_source_contract_v1.0.md",
        "review_state": review_status.get("review_state"),
    }


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
        "human_review_required": True,
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
    generated_at_utc = utc_now_iso()
    full_report = _as_text(state.get("final_trade_decision", ""))
    execution_plan = _as_text(state.get("execution_plan", "Not generated"))
    decision_payload = _normalize_decision_payload(decision)
    research_summary = build_research_summary(
        ticker,
        trade_date,
        full_report,
        execution_plan,
        decision_payload,
        decision,
    )
    review_status = build_review_status(generated_at_utc)
    research_artifacts = build_research_artifacts(
        ticker,
        trade_date,
        research_summary,
        review_status,
    )
    signal_handoff = build_signal_handoff(
        ticker,
        trade_date,
        generated_at_utc,
        research_summary,
        config,
        review_status,
    )
    experiment_context = build_experiment_context(
        ticker,
        trade_date,
        generated_at_utc,
        export_kind,
        config,
        research_summary,
        review_status,
    )
    record: Dict[str, Any] = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "ticker": ticker,
        "trade_date": trade_date,
        "generated_at_utc": generated_at_utc,
        "export_kind": export_kind,
        "decision": decision,
        "full_report": full_report,
        "execution_plan": execution_plan,
        "tax_event_signal": state.get(
            "tax_event_signal", "No tax analysis performed"
        ),
        "advisory_disclaimer": ADVISORY_DISCLAIMER,
        "runtime": build_runtime_summary(config),
        "research_summary": research_summary,
        "research_artifacts": research_artifacts,
        "signal_handoff": signal_handoff,
        "review_status": review_status,
        "experiment_context": experiment_context,
    }
    record["validation_snapshot"] = build_validation_snapshot(state, config)
    record["validation_snapshot"]["signal_dispatch_ready"] = signal_handoff["dispatch_ready"]
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
