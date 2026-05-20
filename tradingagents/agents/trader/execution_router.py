from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.agents.utils.structured import invoke_structured_or_freetext
from pydantic import BaseModel, Field

class ExecutionPlan(BaseModel):
    algo_type: str = Field(
        description="The hypothetical manual execution algorithm to discuss (e.g., VWAP, TWAP, Limit, Market, Implementation Shortfall). If the decision is Hold, use 'None'."
    )
    routing_logic: str = Field(
        description="Human-reviewed advisory explanation of how the order could be staged over time to minimize slippage, taking into account the Volatility Analyst's report. Two to three sentences."
    )
    urgency: str = Field(
        description="High, Medium, or Low urgency for manual handling. High suggests closer human monitoring; Low suggests patient staging."
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

        prompt = f"""As the Execution Router, produce a hypothetical manual execution plan for research and human review only.

Do not assume broker connectivity, auto-routing, or live order submission. Your output must stay advisory and describe what a human operator could consider if they later chose to act.

**Portfolio Manager's Decision:**
{final_trade_decision}

**Volatility Context:**
{volatility_report}

Based on the required action and current market volatility, choose the best execution algorithm concept (e.g., VWAP, TWAP, Limit) and determine the urgency of the trade.{get_language_instruction()}"""

        execution_plan = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_execution_plan,
            "Execution Router"
        )

        return {"execution_plan": execution_plan}

    return execution_router_node
