import os
import json
from dotenv import load_dotenv
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# Load the environment variables from the .env file
load_dotenv()

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        
config["deep_think_llm"] = "gpt-4o" # or another available openai model, using 4o for safety since gpt-5.4 may not exist yet
config["quick_think_llm"] = "gpt-4o-mini" 
config["max_debate_rounds"] = 2
import sys
from datetime import datetime

ticker = sys.argv[1] if len(sys.argv) > 1 else "BTC-USD"
trade_date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")

if ticker.endswith(".AX"):
    config["global_news_queries"] = [
        "Reserve Bank of Australia RBA interest rates inflation",
        "ASX 200 earnings Australian economic outlook",
        "geopolitical risk trade China Australia",
        "iron ore copper gold mining commodities",
    ]
elif ticker.endswith("-USD") or ticker.endswith("-AUD") or ticker.endswith("-EUR"):
    config["global_news_queries"] = [
        "cryptocurrency market regulatory sec etf",
        "federal reserve interest rates inflation",
        f"{ticker.split('-')[0]} crypto news analysis",
        "crypto on-chain whale accumulation",
    ]

ta = TradingAgentsGraph(debug=True, config=config)
state, decision = ta.propagate(ticker, trade_date)

output_data = {
    "decision": decision,
    "full_report": state.get("final_trade_decision", "")
}

# The state dictionary might contain objects not easily serializable,
# so we'll just save the final decision string or dict.
# We will save it to the exports directory.

export_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "05_exports"))
os.makedirs(export_dir, exist_ok=True)
export_file = os.path.join(export_dir, f"{ticker.replace('.', '_').replace('-', '_')}_analysis_{trade_date.replace('-', '_')}.json")

with open(export_file, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2)

print(f"Analysis complete. Decision saved to {export_file}")
print("Final Decision:")
print(json.dumps(decision, indent=2))
