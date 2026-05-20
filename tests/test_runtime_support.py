"""Tests for runtime helpers that enforce governed execution defaults."""

from __future__ import annotations

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.runtime_support import (
    ADVISORY_DISCLAIMER,
    build_export_record,
    build_runtime_config,
)


def test_build_runtime_config_applies_market_specific_queries():
    asx_config = build_runtime_config(DEFAULT_CONFIG, "BHP.AX", max_debate_rounds=2)
    crypto_config = build_runtime_config(DEFAULT_CONFIG, "BTC-USD")

    assert asx_config["max_debate_rounds"] == 2
    assert "Reserve Bank of Australia" in asx_config["global_news_queries"][0]
    assert "cryptocurrency market regulatory sec etf" in crypto_config["global_news_queries"][0]


def test_build_runtime_config_read_only_disables_side_effects():
    config = build_runtime_config(DEFAULT_CONFIG, "BTC-USD", read_only=True)

    assert config["filesystem_write_enabled"] is False
    assert config["state_logging_enabled"] is False
    assert config["memory_log_enabled"] is False
    assert config["checkpoint_enabled"] is False
    assert config["tax_casework_api_enabled"] is False


def test_build_export_record_contains_audit_fields():
    config = build_runtime_config(DEFAULT_CONFIG, "BHP.AX", read_only=True)
    state = {
        "final_trade_decision": "Hold",
        "execution_plan": "Manual review only. Stage passively if a human chooses to act.",
        "tax_event_signal": "No tax event — decision does not involve a disposal.",
    }

    record = build_export_record(
        "BHP.AX",
        "2026-05-20",
        state,
        "Hold",
        config,
        export_kind="analysis",
    )

    assert record["generated_at_utc"].endswith("Z")
    assert record["advisory_disclaimer"] == ADVISORY_DISCLAIMER
    assert record["runtime"]["filesystem_write_enabled"] is False
    assert record["validation_snapshot"]["advisory_disclaimer_included"] is True
    assert record["validation_snapshot"]["live_execution_terms_detected"] == []
