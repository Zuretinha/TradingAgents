from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from datetime import datetime
from typing import Any, Dict
from dotenv import load_dotenv

# Execute ZuretaClaw master secrets router dynamically
_ms_path = r"C:\cloud_files\OneDrive - Safe Working Solutions Pty Ltd\00_master_hub\04_operations\Antigravity\01_projects\zuretaclaw\05_runtime\master_secrets.py"
if os.path.exists(_ms_path):
    exec(open(_ms_path).read())
    init_master_secrets()
else:
    load_dotenv()

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.runtime_support import (
    build_export_record,
    build_runtime_config,
    export_json,
    ticker_filename,
)

app = FastAPI(title="Trading Agents Integration API", description="ZuretaClaw n8n Integration Gateway")

class AnalysisRequest(BaseModel):
    ticker: str
    trade_date: str = None  # Defaults to today if not provided

class PortfolioAnalysisRequest(BaseModel):
    account_name: str
    trade_date: str = None

class AnalysisResponse(BaseModel):
    ticker: str
    trade_date: str
    generated_at_utc: str
    decision: Any
    full_report: str
    execution_plan: str
    tax_event_signal: str
    advisory_disclaimer: str
    runtime: Dict[str, Any]
    validation_snapshot: Dict[str, Any]
    research_summary: Dict[str, Any]
    research_artifacts: Dict[str, Any]
    signal_handoff: Dict[str, Any]
    review_status: Dict[str, Any]
    experiment_context: Dict[str, Any]

@app.post("/analyze", response_model=AnalysisResponse)
def analyze_ticker(request: AnalysisRequest):
    trade_date = request.trade_date or datetime.now().strftime("%Y-%m-%d")
    ticker = request.ticker.upper()
    
    config = build_runtime_config(DEFAULT_CONFIG, ticker, max_debate_rounds=2)
        
    try:
        # Run inference
        ta = TradingAgentsGraph(debug=False, config=config)
        state, decision = ta.propagate(ticker, trade_date)

        output_data = build_export_record(
            ticker,
            trade_date,
            state,
            decision,
            config,
            export_kind="api_run",
        )
        export_json(
            output_data,
            "05_exports",
            "api_runs",
            f"{ticker_filename(ticker, trade_date.replace('-', '_'))}.json",
        )

        return AnalysisResponse(**output_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-portfolio")
def analyze_portfolio(request: PortfolioAnalysisRequest):
    trade_date = request.trade_date or datetime.now().strftime("%Y-%m-%d")
    from run_portfolio import run_portfolio_analysis
    try:
        report = run_portfolio_analysis(request.account_name, trade_date)
        if not report:
            raise HTTPException(status_code=404, detail="Portfolio not found or empty.")
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Expose on 8000 for local n8n to reach via http://localhost:8000 or docker bridge
    uvicorn.run(app, host="0.0.0.0", port=8000)
