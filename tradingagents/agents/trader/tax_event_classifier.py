"""
Tax Event Classifier — WP-02
Sits between Portfolio Manager and Execution Router.
Classifies every SELL/TRIM recommendation as a CGT event and injects
tax context into the execution pipeline.
"""
import json
import os
from datetime import datetime
from tradingagents.agents.utils.agent_utils import get_language_instruction


def create_tax_event_classifier(llm):
    """Create a tax event classifier node for the trading graph."""

    def tax_event_classifier_node(state) -> dict:
        final_decision = state.get("final_trade_decision", "")
        ticker = state.get("company_of_interest", "")
        trade_date_str = state.get("trade_date", datetime.now().strftime("%Y-%m-%d"))

        # Load portfolio context if available
        portfolio_context = _load_portfolio_context(ticker)

        if not portfolio_context:
            # No portfolio data — pass through without tax analysis
            return {"tax_event_signal": "No portfolio data available for tax event classification."}

        # Determine if the decision involves a sell action
        decision_lower = final_decision.lower()
        is_sell = any(word in decision_lower for word in ["sell", "underweight", "reduce", "trim", "exit"])

        if not is_sell:
            return {"tax_event_signal": "No tax event — decision does not involve a disposal."}

        # Calculate CGT details
        holding = portfolio_context["holding"]
        account = portfolio_context["account"]

        acq_date = holding.get("acquisition_date", "")
        cost_basis = holding.get("cost_basis_per_unit", 0)
        units = holding.get("units", 0)
        account_type = account.get("account_type", "personal")
        realised_ytd = account.get("realised_gains_ytd_aud", 0)
        fy_end = account.get("financial_year_end", "2026-06-30")

        # Holding period calculation
        holding_period_days = 0
        cgt_discount_eligible = False
        if acq_date:
            try:
                acq = datetime.strptime(acq_date, "%Y-%m-%d")
                trade_date = datetime.strptime(trade_date_str, "%Y-%m-%d")
                holding_period_days = (trade_date - acq).days
                # Personal accounts get 50% discount after 12 months
                # SMSF gets 33.33% discount after 12 months
                # Companies get no discount
                cgt_discount_eligible = holding_period_days >= 365
            except ValueError:
                pass

        # Build the tax event prompt
        prompt = f"""You are a Tax Event Classifier for Australian equities and crypto. Analyse the following trade recommendation and produce a structured tax event assessment.

**Trade Decision:**
{final_decision}

**Portfolio Context:**
- Account: {account.get('account_name', 'Unknown')} ({account_type})
- Ticker: {ticker}
- Units held: {units}
- Cost basis per unit: ${cost_basis:.2f}
- Acquisition date: {acq_date}
- Holding period: {holding_period_days} days
- CGT discount eligible (12+ months): {'Yes' if cgt_discount_eligible else 'No'}
- Account type discount: {'50% (personal)' if account_type == 'personal' and cgt_discount_eligible else '33.33% (SMSF)' if account_type == 'smsf' and cgt_discount_eligible else 'None'}
- Realised capital gains YTD: ${realised_ytd:,.2f}
- Financial year end: {fy_end}
- Days until FY end: {_days_until(fy_end)}

**Your task:**
1. Estimate the capital gain/loss based on a reasonable current price assumption
2. State whether the 50% CGT discount applies (personal) or 33.33% (SMSF)
3. Flag if the trade should be DEFERRED to after June 30 to shift the gain to the next FY
4. Flag any SMSF compliance concerns if this is an SMSF account
5. Provide a one-line advisory note

Format your response as a JSON object with keys: estimated_gain_aud, cgt_discount_applicable, discount_rate, recommended_deferral, smsf_flags, advisory_note

This is an estimate for research purposes only. Consult your tax agent for verified calculations.{get_language_instruction()}"""

        response = llm.invoke(prompt)
        content = response.content
        
        # Try to parse the JSON and hit the WP-03 API
        try:
            import re
            import requests
            
            # Extract JSON block if it's wrapped in markdown
            json_str = content
            match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if match:
                json_str = match.group(1)
                
            tax_data = json.loads(json_str)
            
            # Construct payload for API
            payload = {
                "account": account.get('account_name', 'Unknown'),
                "ticker": ticker,
                "action": "SELL",
                "units": float(units),
                "estimated_gain_aud": float(tax_data.get("estimated_gain_aud", 0)),
                "cgt_discount_applicable": bool(tax_data.get("cgt_discount_applicable", False)),
                "smsf_flags": str(tax_data.get("smsf_flags", "")),
                "advisory_note": str(tax_data.get("advisory_note", ""))
            }
            
            try:
                # Send to Tax Casework Intelligence API (port 8001)
                res = requests.post("http://localhost:8001/flag/tax-event", json=payload, timeout=2)
                api_result = f"\n\n*Signal successfully sent to Tax Casework Intelligence API (Status {res.status_code})*"
            except requests.exceptions.RequestException:
                api_result = "\n\n*(Tax Casework Intelligence API offline — signal not logged)*"
                
        except Exception:
            api_result = "\n\n*(Failed to parse LLM response into strict JSON for API)*"

        tax_signal = f"**Tax Event Classification for {ticker}**\n\n{content}{api_result}"

        return {"tax_event_signal": tax_signal}

    return tax_event_classifier_node


def _load_portfolio_context(ticker: str) -> dict | None:
    """Try to find this ticker in any portfolio file and return context."""
    portfolio_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "06_data", "portfolios")
    )
    if not os.path.exists(portfolio_dir):
        return None

    for filename in os.listdir(portfolio_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(portfolio_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                account = json.load(f)
            for holding in account.get("holdings", []):
                if holding.get("ticker", "").upper() == ticker.upper():
                    return {"account": account, "holding": holding}
        except (json.JSONDecodeError, KeyError):
            continue

    return None


def _days_until(date_str: str) -> str:
    """Calculate days until a given date string."""
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d")
        delta = (target - datetime.now()).days
        if delta < 0:
            return "Past"
        return str(delta)
    except ValueError:
        return "Unknown"
