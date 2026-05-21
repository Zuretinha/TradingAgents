from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.runtime_support import (
    build_export_record,
    build_runtime_config,
    export_json,
    ticker_filename,
)
import sys

def run_backtest(ticker, trade_date):
    print(f"\n--- Starting Backtest for {ticker} on {trade_date} ---")

    config = build_runtime_config(DEFAULT_CONFIG, ticker, max_debate_rounds=2)
        
    ta = TradingAgentsGraph(debug=False, config=config)
    state, decision = ta.propagate(ticker, trade_date)

    output_data = build_export_record(
        ticker,
        trade_date,
        state,
        decision,
        config,
        export_kind="backtest",
    )
    export_file = export_json(
        output_data,
        "05_exports",
        "backtests",
        f"{ticker_filename(ticker, f'backtest_{trade_date.replace('-', '_')}')}.json",
    )
        
    print(f"Backtest complete. Decision saved to {export_file}")
    print(f"Decision: {decision}")
    
if __name__ == "__main__":
    if len(sys.argv) == 3:
        run_backtest(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python run_backtest.py <TICKER> <YYYY-MM-DD>")
