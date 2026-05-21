import json
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.runtime_support import (
    build_export_record,
    build_runtime_config,
    export_json,
    ticker_filename,
)

import sys
from datetime import datetime

ticker = sys.argv[1] if len(sys.argv) > 1 else "BTC-USD"
trade_date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")
config = build_runtime_config(DEFAULT_CONFIG, ticker, max_debate_rounds=2)

ta = TradingAgentsGraph(debug=False, config=config)
state, decision = ta.propagate(ticker, trade_date)

output_data = build_export_record(
    ticker,
    trade_date,
    state,
    decision,
    config,
    export_kind="analysis",
)
export_file = export_json(
    output_data,
    "05_exports",
    f"{ticker_filename(ticker, f'analysis_{trade_date.replace('-', '_')}')}.json",
)

print(f"Analysis complete. Decision saved to {export_file}")
print("Final Decision:")
print(json.dumps(decision, indent=2))
