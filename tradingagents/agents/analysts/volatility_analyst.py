from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_stock_data,
    get_indicators,
)

def create_volatility_analyst(llm):

    def volatility_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [get_stock_data, get_indicators]
        
        # WP-05: Earnings Proximity Guard
        import yfinance as yf
        import datetime
        earnings_warning = ""
        try:
            cal = yf.Ticker(state["company_of_interest"]).calendar
            if cal and 'Earnings Date' in cal and cal['Earnings Date']:
                next_earnings = cal['Earnings Date'][0]
                trade_dt = datetime.datetime.strptime(current_date, "%Y-%m-%d").date()
                days_to_earnings = (next_earnings - trade_dt).days
                
                if 0 <= days_to_earnings <= 2:
                    earnings_warning = (
                        f"\n\nCRITICAL WARNING: The company reports earnings in {days_to_earnings} days on {next_earnings}. "
                        "This is an imminent binary event. You MUST penalize high-conviction Overweight/Buy recommendations "
                        "and explicitly advise risk management to remain neutral or reduce exposure ahead of earnings."
                    )
        except Exception:
            pass

        system_message = (
            "You are a Quantitative Volatility Analyst. Your role is to assess market pricing "
            "of future risk by looking at volatility indicators (like ATR, standard deviations, "
            "and historical price swings). "
            "You should fetch stock data and run volatility indicators like ATR and Bollinger Bands. "
            "Provide insights on whether the current market environment is high-volatility "
            "(suggesting smaller position sizing and wider stops) or low-volatility "
            "(suggesting potential breakouts or mean-reversion). "
            "Conclude with explicit guidance on how risk management should adjust their sizing "
            "based on the current volatility regime."
            + earnings_warning
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants.\n"
                    "You have access to the following tools: {tool_names}.\n{system_message}\n"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "volatility_report": report,
        }

    return volatility_analyst_node
