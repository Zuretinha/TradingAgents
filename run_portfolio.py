"""
Portfolio Orchestrator — WP-01
Reads a portfolio JSON, runs the trading agent pipeline per holding,
and produces an aggregated portfolio-level report.
"""
import os
import json
import sys
from datetime import datetime

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.runtime_support import (
    ADVISORY_DISCLAIMER,
    build_export_record,
    build_runtime_config,
    export_json,
    ticker_filename,
    utc_now_iso,
)


def load_portfolio(account_name: str) -> dict:
    """Load a portfolio JSON file by account name."""
    portfolio_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "06_data", "portfolios")
    )
    filepath = os.path.join(portfolio_dir, f"{account_name.lower()}.json")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Portfolio file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def build_config(ticker: str) -> dict:
    """Build a config dict with ASX overrides if needed."""
    return build_runtime_config(DEFAULT_CONFIG, ticker, max_debate_rounds=2)


def calculate_holding_context(holding: dict, portfolio: dict) -> str:
    """Build a context string describing the holding within the portfolio."""
    account_name = portfolio["account_name"]
    account_type = portfolio["account_type"]
    total_value = portfolio.get("total_value_aud")
    realised_ytd = portfolio.get("realised_gains_ytd_aud", 0)
    fy_end = portfolio.get("financial_year_end", "2026-06-30")

    units = holding.get("units", 0)
    cost_basis = holding.get("cost_basis_per_unit", 0)
    acq_date = holding.get("acquisition_date", "unknown")
    total_cost = units * cost_basis

    # Calculate holding period
    holding_period = "unknown"
    cgt_discount = False
    if acq_date != "unknown":
        try:
            acq = datetime.strptime(acq_date, "%Y-%m-%d")
            days_held = (datetime.now() - acq).days
            holding_period = f"{days_held} days"
            cgt_discount = days_held >= 365 and account_type == "personal"
        except ValueError:
            pass

    # Calculate allocation percentage
    allocation_pct = "unknown"
    if total_value and total_value > 0:
        current_value = units * holding.get("current_price", cost_basis)
        allocation_pct = f"{(current_value / total_value) * 100:.1f}%"

    context = (
        f"\n--- PORTFOLIO CONTEXT ---\n"
        f"Account: {account_name} ({account_type})\n"
        f"Units held: {units} | Cost basis: ${cost_basis:.2f}/unit | Total cost: ${total_cost:.2f}\n"
        f"Acquisition date: {acq_date} | Holding period: {holding_period}\n"
        f"CGT 50% discount eligible: {'Yes' if cgt_discount else 'No'}\n"
        f"Portfolio allocation: {allocation_pct}\n"
        f"Realised capital gains YTD: ${realised_ytd:,.2f}\n"
        f"Financial year end: {fy_end}\n"
    )

    if account_type == "smsf":
        constraints = portfolio.get("smsf_constraints", {})
        context += (
            f"SMSF in-house asset limit: {constraints.get('in_house_asset_limit_pct', 5)}%\n"
            f"Related-party acquisitions restricted: {constraints.get('related_party_acquisitions_restricted', True)}\n"
            f"Sole purpose test applies: {constraints.get('sole_purpose_test', True)}\n"
            f"NOTE: SMSF does NOT receive the 50% CGT discount.\n"
        )

    # Days until FY end
    try:
        fy = datetime.strptime(fy_end, "%Y-%m-%d")
        days_to_fy = (fy - datetime.now()).days
        if 0 < days_to_fy <= 45:
            context += f"⚠️ ONLY {days_to_fy} DAYS UNTIL FY END — consider gain/loss timing.\n"
    except ValueError:
        pass

    context += "--- END PORTFOLIO CONTEXT ---\n"
    return context


def run_portfolio_analysis(account_name: str, trade_date: str = None):
    """Run the full pipeline for every holding in a portfolio."""
    trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")

    portfolio = load_portfolio(account_name)
    holdings = portfolio.get("holdings", [])

    if not holdings:
        print(f"⚠️  Portfolio '{account_name}' has no holdings. Please populate {account_name.lower()}.json first.")
        return

    print(f"\n{'='*60}")
    print(f"PORTFOLIO ANALYSIS: {portfolio['account_name']} ({portfolio['account_type']})")
    print(f"Date: {trade_date} | Holdings: {len(holdings)}")
    print(f"{'='*60}\n")

    results = []

    for i, holding in enumerate(holdings, 1):
        ticker = holding["ticker"]
        print(f"\n[{i}/{len(holdings)}] Analysing {ticker}...")

        config = build_config(ticker)
        portfolio_context = calculate_holding_context(holding, portfolio)
        portfolio_record = {
            "account": {
                key: value
                for key, value in portfolio.items()
                if key != "holdings"
            },
            "holding": holding,
        }

        try:
            ta = TradingAgentsGraph(debug=False, config=config)
            state, decision = ta.propagate(
                ticker,
                trade_date,
                portfolio_context=portfolio_context,
                portfolio_record=portfolio_record,
            )

            result = build_export_record(
                ticker,
                trade_date,
                state,
                decision,
                config,
                export_kind="portfolio_holding",
                extra={
                    "portfolio_context": portfolio_context,
                    "portfolio_record": portfolio_record,
                    "units": holding.get("units", 0),
                    "cost_basis": holding.get("cost_basis_per_unit", 0),
                    "acquisition_date": holding.get("acquisition_date", ""),
                },
            )
            results.append(result)
            print(f"    → Decision: {decision}")
        except Exception as e:
            print(f"    ✗ Error analysing {ticker}: {e}")
            results.append({"ticker": ticker, "decision": "ERROR", "error": str(e)})

    report = {
        "account_name": portfolio["account_name"],
        "account_type": portfolio["account_type"],
        "trade_date": trade_date,
        "generated_at_utc": utc_now_iso(),
        "advisory_disclaimer": ADVISORY_DISCLAIMER,
        "total_holdings_analysed": len(results),
        "summary": {
            "buy": sum(1 for r in results if r.get("decision", "").lower() in ["buy", "overweight"]),
            "hold": sum(1 for r in results if r.get("decision", "").lower() == "hold"),
            "sell": sum(1 for r in results if r.get("decision", "").lower() in ["sell", "underweight"]),
            "error": sum(1 for r in results if r.get("decision", "").lower() == "error"),
        },
        "validation_summary": {
            "write_enabled_holdings": sum(
                1
                for r in results
                if r.get("runtime", {}).get("filesystem_write_enabled") is True
            ),
            "tax_dispatch_enabled_holdings": sum(
                1
                for r in results
                if r.get("runtime", {}).get("tax_casework_api_enabled") is True
            ),
        },
        "holdings": results,
    }

    safe_name = account_name.lower().replace(" ", "_")
    export_file = export_json(
        report,
        "05_exports",
        "portfolio_reports",
        f"{safe_name}_portfolio_{trade_date.replace('-', '_')}.json",
    )

    print(f"\n{'='*60}")
    print(f"PORTFOLIO REPORT SAVED: {export_file}")
    print(f"Summary: {report['summary']}")
    print(f"{'='*60}")

    return report


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        account = sys.argv[1]
        date = sys.argv[2] if len(sys.argv) >= 3 else None
        run_portfolio_analysis(account, date)
    else:
        print("Usage: python run_portfolio.py <account_name> [YYYY-MM-DD]")
        print("  account_name: clayton | adriana | smsf")
