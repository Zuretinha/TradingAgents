"""
FY-End Tax Optimiser — WP-06
Scans a portfolio to identify tax-loss harvesting and gain-deferral opportunities.
Designed to be run in May/June leading up to the Australian EOFY (June 30).
"""
import os
import json
import sys
from datetime import datetime
import yfinance as yf

def _load_portfolio(account_name: str) -> dict:
    portfolio_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "06_data", "portfolios")
    )
    filepath = os.path.join(portfolio_dir, f"{account_name.lower()}.json")
    if not os.path.exists(filepath):
        print(f"Error: Portfolio {filepath} not found.")
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def run_tax_optimisation(account_name: str):
    """Scan portfolio for tax-loss harvesting and gain deferral opportunities."""
    portfolio = _load_portfolio(account_name)
    holdings = portfolio.get("holdings", [])
    
    if not holdings:
        print(f"Portfolio '{account_name}' has no holdings.")
        return

    realised_gains_ytd = portfolio.get("realised_gains_ytd_aud", 0)
    fy_end_str = portfolio.get("financial_year_end", "2026-06-30")
    account_type = portfolio.get("account_type", "personal")
    
    current_date = datetime.now()
    try:
        fy_end = datetime.strptime(fy_end_str, "%Y-%m-%d")
        days_to_fy_end = (fy_end - current_date).days
    except ValueError:
        days_to_fy_end = 999

    print(f"\n{'='*60}")
    print(f"FY-END TAX OPTIMISATION REPORT: {portfolio['account_name']} ({account_type})")
    print(f"Realised Gains YTD: ${realised_gains_ytd:,.2f} | Days to FY End: {days_to_fy_end}")
    print(f"{'='*60}\n")
    
    if days_to_fy_end > 60:
        print("ℹ️ Note: It is currently more than 60 days from FY end. Tax-loss harvesting is typically most effective in May/June.\n")

    harvesting_candidates = []
    deferral_candidates = []
    
    for holding in holdings:
        ticker = holding["ticker"]
        units = holding.get("units", 0)
        cost_basis = holding.get("cost_basis_per_unit", 0)
        acq_date_str = holding.get("acquisition_date", "")
        
        # Determine if crypto
        is_crypto = ticker.endswith("-USD") or ticker.endswith("-AUD") or ticker.endswith("-EUR")
        
        # Get live price
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[0]
            else:
                current_price = holding.get("current_price", cost_basis)
        except Exception:
            current_price = holding.get("current_price", cost_basis)

        unrealised_pl = (current_price - cost_basis) * units
        unrealised_pl_pct = ((current_price - cost_basis) / cost_basis) * 100 if cost_basis > 0 else 0
        
        # Calculate holding period for CGT discount
        cgt_discount_eligible = False
        holding_period_days = 0
        if acq_date_str:
            try:
                acq_date = datetime.strptime(acq_date_str, "%Y-%m-%d")
                holding_period_days = (current_date - acq_date).days
                cgt_discount_eligible = holding_period_days >= 365
            except ValueError:
                pass

        # 1. Tax-Loss Harvesting Candidates
        if unrealised_pl < 0:
            harvesting_candidates.append({
                "ticker": ticker,
                "unrealised_loss": unrealised_pl,
                "pct_loss": unrealised_pl_pct,
                "note": "Wash sale rules apply. Ensure you wait at least 30 days before repurchasing if you harvest this loss."
            })
            
        # 2. Gain Deferral Candidates
        elif unrealised_pl > 0 and 0 < days_to_fy_end <= 45:
            # If large gain and close to FY end, defer
            if unrealised_pl > 1000:
                deferral_candidates.append({
                    "ticker": ticker,
                    "unrealised_gain": unrealised_pl,
                    "cgt_discount": cgt_discount_eligible,
                    "days_held": holding_period_days,
                    "note": f"Defer sale {days_to_fy_end} days until {fy_end_str} to push tax liability to next financial year."
                })
            # Or if approaching the 12-month discount cliff
            elif 330 <= holding_period_days < 365:
                days_to_discount = 365 - holding_period_days
                deferral_candidates.append({
                    "ticker": ticker,
                    "unrealised_gain": unrealised_pl,
                    "cgt_discount": False,
                    "days_held": holding_period_days,
                    "note": f"⚠️ HOLD: You are {days_to_discount} days away from the 12-month CGT discount cliff. Do not sell yet."
                })

    # Print Tax-Loss Harvesting Candidates
    print("[LOSS] TAX-LOSS HARVESTING CANDIDATES")
    if not harvesting_candidates:
        print("  No unrealised losses found.")
    else:
        # Sort by largest loss
        harvesting_candidates.sort(key=lambda x: x["unrealised_loss"])
        for c in harvesting_candidates:
            print(f"  {c['ticker']}: {c['unrealised_loss']:,.2f} AUD ({c['pct_loss']:.1f}%)")
            print(f"    -> {c['note']}")
            
    print("\n" + "-"*60 + "\n")
    
    # Print Gain Deferral Candidates
    print("[WARNING] GAIN DEFERRAL WARNINGS")
    if not deferral_candidates:
        print("  No imminent deferral warnings.")
    else:
        deferral_candidates.sort(key=lambda x: x["unrealised_gain"], reverse=True)
        for c in deferral_candidates:
            discount_status = "Eligible" if c['cgt_discount'] else "Not Eligible"
            print(f"  {c['ticker']}: {c['unrealised_gain']:,.2f} AUD Gain | 50% CGT: {discount_status}")
            print(f"    -> {c['note']}")
            
    print(f"\n{'='*60}")
    print("DISCLAIMER: This output is for research and reconstructive purposes only. It does NOT")
    print("constitute financial, legal, or tax advice under ASIC or TPB regulations.")
    print("Consult a registered tax agent or financial adviser before acting on these scenarios.")
    print(f"{'='*60}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tax_optimiser.py <account_name>")
        sys.exit(1)
    
    run_tax_optimisation(sys.argv[1])
