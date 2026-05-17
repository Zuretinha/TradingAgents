from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_global_news,
)

def create_macro_analyst(llm):

    def macro_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [get_global_news]

        system_message = (
            "You are a Macroeconomic Strategist. Your role is to analyze broader economic "
            "conditions, central bank policies (e.g., Fed rate decisions), inflation data, "
            "employment numbers, and geopolitical events that could impact the market "
            "as a whole, regardless of the specific stock. "
            "Use the provided global news tools to fetch recent macroeconomic developments. "
            "Provide a concise, highly actionable summary of the macro regime and its "
            "implications for risk assets (equities). Do not focus too much on the specific "
            "company, but rather on the overall market climate. "
            "Make sure to append a Markdown table at the end of your report summarizing "
            "the key macroeconomic risks and tailwinds."
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
            "macro_report": report,
        }

    return macro_analyst_node
