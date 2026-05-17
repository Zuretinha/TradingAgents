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
config["global_news_queries"] = [
    "Reserve Bank of Australia RBA interest rates inflation",
    "ASX 200 earnings Australian economic outlook",
    "geopolitical risk trade China Australia",
    "iron ore copper gold mining commodities",
]

ta = TradingAgentsGraph(debug=True, config=config)
state, decision = ta.propagate("BHP.AX", "2026-05-17") # Use today's date

output_data = {
    "decision": decision,
    "full_report": state.get("final_trade_decision", "")
}

# The state dictionary might contain objects not easily serializable,
# so we'll just save the final decision string or dict.
# We will save it to the exports directory.

export_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "05_exports"))
os.makedirs(export_dir, exist_ok=True)
export_file = os.path.join(export_dir, "BHP_AX_analysis_2026_05_17.json")

with open(export_file, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2)

print(f"Analysis complete. Decision saved to {export_file}")
print("Final Decision:")
print(json.dumps(decision, indent=2))
