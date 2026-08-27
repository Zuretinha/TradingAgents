import importlib.util
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _restore_module_state_after_test():
    """Prevent dynamic-import stubs from leaking into later upstream tests."""
    prefix_names = {
        name: module
        for name, module in sys.modules.items()
        if name.startswith("tradingagents")
        or name in {"run_portfolio_under_test", "tax_event_classifier_under_test"}
    }
    yield
    current_names = {
        name
        for name in sys.modules
        if name.startswith("tradingagents")
        or name in {"run_portfolio_under_test", "tax_event_classifier_under_test"}
    }
    for name in current_names - prefix_names.keys():
        sys.modules.pop(name, None)
    for name, module in prefix_names.items():
        sys.modules[name] = module


def _load_run_portfolio_module():
    fake_graph = types.ModuleType("tradingagents.graph.trading_graph")
    fake_graph.TradingAgentsGraph = object
    fake_default_config = types.ModuleType("tradingagents.default_config")
    fake_default_config.DEFAULT_CONFIG = {}
    fake_runtime_support = types.ModuleType("tradingagents.runtime_support")
    fake_runtime_support.ADVISORY_DISCLAIMER = ""
    fake_runtime_support.build_export_record = lambda *args, **kwargs: {}
    fake_runtime_support.build_runtime_config = lambda config, ticker, max_debate_rounds=2: config
    fake_runtime_support.export_json = lambda *args, **kwargs: ""
    fake_runtime_support.ticker_filename = lambda ticker, suffix: f"{ticker}_{suffix}"
    fake_runtime_support.utc_now_iso = lambda: "2026-07-04T00:00:00Z"

    sys.modules["tradingagents.graph.trading_graph"] = fake_graph
    sys.modules["tradingagents.default_config"] = fake_default_config
    sys.modules["tradingagents.runtime_support"] = fake_runtime_support

    spec = importlib.util.spec_from_file_location("run_portfolio_under_test", PROJECT_ROOT / "run_portfolio.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_tax_event_classifier_module():
    fake_agent_utils = types.ModuleType("tradingagents.agents.utils.agent_utils")
    fake_agent_utils.get_language_instruction = lambda: ""
    sys.modules["tradingagents.agents.utils.agent_utils"] = fake_agent_utils

    spec = importlib.util.spec_from_file_location(
        "tax_event_classifier_under_test",
        PROJECT_ROOT / "tradingagents" / "agents" / "trader" / "tax_event_classifier.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_calculate_holding_context_handles_missing_cost_basis():
    module = _load_run_portfolio_module()
    holding = {
        "ticker": "BTC-USD",
        "units": 0.5,
        "cost_basis_per_unit": None,
        "current_price": 100000.0,
        "acquisition_date": "",
    }
    portfolio = {
        "account_name": "Clayton",
        "account_type": "personal",
        "financial_year_end": "2026-06-30",
    }

    context = module.calculate_holding_context(holding, portfolio)

    assert "Cost basis: unknown" in context
    assert "Total cost: unknown" in context
    assert "Acquisition date: unknown" in context


@pytest.mark.unit
def test_tax_event_classifier_fails_closed_without_cost_basis():
    module = _load_tax_event_classifier_module()
    classifier = module.create_tax_event_classifier(llm=None, config={})
    state = {
        "final_trade_decision": "Rating: Sell\nReduce exposure.",
        "company_of_interest": "BTC-USD",
        "trade_date": "2026-07-04",
        "portfolio_record": {
            "account": {
                "account_name": "Clayton",
                "account_type": "personal",
                "financial_year_end": "2026-06-30",
                "realised_gains_ytd_aud": 0,
            },
            "holding": {
                "ticker": "BTC-USD",
                "units": 0.5,
                "cost_basis_per_unit": None,
                "acquisition_date": "",
            },
        },
    }

    result = classifier(state)

    assert "cost basis is missing or unresolved" in result["tax_event_signal"]


@pytest.mark.unit
def test_build_account_snapshot_excludes_non_runtime_collections():
    module = _load_run_portfolio_module()
    snapshot = module.build_account_snapshot(
        {
            "account_name": "Clayton",
            "account_type": "personal",
            "financial_year_end": "2026-06-30",
            "analysis_watchlist": [{"ticker": "BTC-USD"}],
            "non_runtime_holdings": [{"ticker": "DOGE-USD"}],
            "holdings": [{"ticker": "ETH-USD"}],
            "evidence_gaps": ["cost basis missing"],
        }
    )

    assert snapshot == {
        "account_name": "Clayton",
        "account_type": "personal",
        "financial_year_end": "2026-06-30",
        "evidence_gaps": ["cost basis missing"],
    }
