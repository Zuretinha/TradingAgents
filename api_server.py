from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import json
from datetime import datetime
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

app = FastAPI(title="Trading Agents Integration API", description="ZuretaClaw n8n Integration Gateway")

class AnalysisRequest(BaseModel):
    ticker: str
    trade_date: str = None  # Defaults to today if not provided

class PortfolioAnalysisRequest(BaseModel):
    account_name: str
    trade_date: str = None

class AnalysisResponse(BaseModel):
    ticker: str
    date: str
    decision: str
    full_report: str
    execution_plan: str
    tax_event_signal: str

@app.post("/analyze", response_model=AnalysisResponse)
def analyze_ticker(request: AnalysisRequest):
    trade_date = request.trade_date or datetime.now().strftime("%Y-%m-%d")
    ticker = request.ticker.upper()
    
    # Configure graph
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "openai"        
    config["deep_think_llm"] = "gpt-4o" 
    config["quick_think_llm"] = "gpt-4o-mini" 
    config["max_debate_rounds"] = 2
    
    # Apply ASX rules if necessary
    if ticker.endswith(".AX"):
        config["global_news_queries"] = [
            "Reserve Bank of Australia RBA interest rates inflation",
            "ASX 200 earnings Australian economic outlook",
            "geopolitical risk trade China Australia",
            "iron ore copper gold mining commodities",
        ]
        
    try:
        # Run inference
        ta = TradingAgentsGraph(debug=False, config=config)
        state, decision = ta.propagate(ticker, trade_date)
        
        # Save exact snapshot locally for audit
        export_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "05_exports", "api_runs"))
        os.makedirs(export_dir, exist_ok=True)
        safe_ticker = ticker.replace(".", "_")
        export_file = os.path.join(export_dir, f"{safe_ticker}_{trade_date.replace('-', '_')}.json")
        
        output_data = {
            "ticker": ticker,
            "date": trade_date,
            "decision": decision,
            "full_report": state.get("final_trade_decision", ""),
            "execution_plan": state.get("execution_plan", "Not generated"),
            "tax_event_signal": state.get("tax_event_signal", "No tax analysis performed")
        }
        
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
            
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
