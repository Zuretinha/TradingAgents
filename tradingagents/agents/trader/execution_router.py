from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.agents.utils.structured import invoke_structured_or_freetext
from pydantic import BaseModel, Field

class ExecutionPlan(BaseModel):
    algo_type: str = Field(
        description="The execution algorithm to use (e.g., VWAP, TWAP, Limit, Market, Implementation Shortfall). If the decision is Hold, just use 'None'."
    )
    routing_logic: str = Field(
        description="Detailed explanation of how the order should be sliced over time to minimize slippage, taking into account the Volatility Analyst's report. Two to three sentences."
    )
    urgency: str = Field(
        description="High, Medium, or Low urgency. High urgency suggests aggressive market orders; Low suggests passive limit orders."
    )

def render_execution_plan(plan: ExecutionPlan) -> str:
    return (
        f"**Execution Algorithm**: {plan.algo_type}\n\n"
        f"**Routing Logic**: {plan.routing_logic}\n\n"
        f"**Urgency**: {plan.urgency}"
    )

def create_execution_router(llm):
    from tradingagents.agents.utils.structured import bind_structured
    structured_llm = bind_structured(llm, ExecutionPlan, "Execution Router")

    def execution_router_node(state) -> dict:
        volatility_report = state.get("volatility_report", "Not available")
        final_trade_decision = state.get("final_trade_decision", "")

        prompt = f"""As the Execution Router, your job is to take the final trading decision from the Portfolio Manager and determine HOW to execute it in the live market to minimize slippage and market impact.

**Portfolio Manager's Decision:**
{final_trade_decision}

**Volatility Context:**
{volatility_report}

Based on the required action and current market volatility, choose the best execution algorithm (e.g., VWAP, TWAP, Limit) and determine the urgency of the trade.{get_language_instruction()}"""

        execution_plan = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_execution_plan,
            "Execution Router"
        )

        return {"execution_plan": execution_plan}

    return execution_router_node
