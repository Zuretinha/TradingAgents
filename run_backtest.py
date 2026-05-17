import os
import json
from dotenv import load_dotenv
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
import sys

def run_backtest(ticker, trade_date):
    print(f"\n--- Starting Backtest for {ticker} on {trade_date} ---")
    load_dotenv()
    
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "openai"        
    config["deep_think_llm"] = "gpt-4o" 
    config["quick_think_llm"] = "gpt-4o-mini" 
    config["max_debate_rounds"] = 2
    
    if ticker.endswith(".AX"):
        config["global_news_queries"] = [
            "Reserve Bank of Australia RBA interest rates inflation",
            "ASX 200 earnings Australian economic outlook",
            "geopolitical risk trade China Australia",
            "iron ore copper gold mining commodities",
        ]
        
    ta = TradingAgentsGraph(debug=False, config=config)
    state, decision = ta.propagate(ticker, trade_date)
    
    export_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "05_exports", "backtests"))
    os.makedirs(export_dir, exist_ok=True)
    
    safe_ticker = ticker.replace(".", "_")
    export_file = os.path.join(export_dir, f"{safe_ticker}_backtest_{trade_date.replace('-', '_')}.json")
    
    output_data = {
        "ticker": ticker,
        "date": trade_date,
        "decision": decision,
        "full_report": state.get("final_trade_decision", "")
    }
    
    with open(export_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
        
    print(f"Backtest complete. Decision saved to {export_file}")
    print(f"Decision: {decision}")
    
if __name__ == "__main__":
    if len(sys.argv) == 3:
        run_backtest(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python run_backtest.py <TICKER> <YYYY-MM-DD>")
