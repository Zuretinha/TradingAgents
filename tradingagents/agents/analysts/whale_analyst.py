from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_insider_transactions,
    get_global_news,
)

def create_whale_analyst(llm):

    def whale_analyst_node(state):
        ticker = state["company_of_interest"]
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(ticker)

        # WP-04: Crypto Expansion
        is_crypto = ticker.endswith("-USD") or ticker.endswith("-AUD") or ticker.endswith("-EUR")

        if is_crypto:
            tools = [get_global_news]
            system_message = (
                "You are a Crypto Whale & On-Chain Tracker. Your role is to track 'smart money' and whale movements. "
                "Since SEC insider filings do not exist for cryptocurrencies, use the `get_global_news` tool to search for "
                f"news regarding large on-chain transfers, exchange outflows, and whale accumulation for {ticker}. "
                "Write a detailed report on whether large holders (whales) are accumulating or distributing. "
                "Make sure to append a Markdown table summarizing any reported whale movements."
                + get_language_instruction()
            )
        else:
            tools = [get_insider_transactions]
            system_message = (
                "You are a Whale / Insider Tracker. Your role is to track 'smart money' movements, "
                "including corporate insider buying/selling and institutional holder behavior. "
                "Use the provided tools to fetch insider transaction data for the target company. "
                "Look for clusters of insider buying (which is a strong bullish signal) or heavy "
                "insider selling (which could be a warning sign, though often done for tax reasons). "
                "Write a detailed report on whether the smart money is accumulating or distributing "
                "shares. "
                "Make sure to append a Markdown table at the end of the report summarizing the "
                "most significant insider trades."
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
            "whale_report": report,
        }

    return whale_analyst_node
