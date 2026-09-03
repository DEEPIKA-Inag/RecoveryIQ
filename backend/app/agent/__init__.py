"""
agent/graph.py

Recovery IQ's agent, built on LangGraph. Three nodes, one direction:

    detect -> determine -> execute

Each node is a plain Python function -- no LLM sits inside the graph.
This is a deliberate choice: LangGraph is used here purely as the
orchestration/state layer for a deterministic, auditable pipeline, not
as a wrapper around free-form LLM reasoning. Every ₹ decision made in
the "determine" node is still pure arithmetic (engine.py) plus a trained
ML model's probability output (predictor.py) plus hard-coded compliance
rules (guardrails.py) -- none of that logic changed. What changed is
HOW it's invoked: instead of the router calling three functions directly
in sequence, it now calls run_agent(), which invokes a compiled
StateGraph that makes the pipeline's structure explicit, inspectable,
and independently testable node-by-node.

Nodes:
  - detect_node: normalizes/validates the incoming transaction + customer
    state. Trivial today (detection already happened at the API layer
    when the transaction was created) but exists as its own node so the
    detect step is a real, separately-invokable unit of the graph, not
    an implicit assumption.
  - determine_node: calls evaluate_transaction() (guardrails -> ML ->
    EV engine, unchanged) and stores the result on state.
  - execute_node: calls execute_action() (the mock executor, unchanged)
    using the determine node's chosen action, and stores the execution
    record on state.
"""

from datetime import datetime
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from ..decision_engine.engine import evaluate_transaction
from ..decision_engine.executor import execute_action


class AgentState(TypedDict, total=False):
    transaction: dict          # amount, failure_reason, days_since_failure
    customer: dict              # engine-shaped customer history + guardrail flags
    customer_name: str
    payment_channel: str
    now: Optional[datetime]     # override for quiet-hours testing; None = real IST time
    detected_at: str
    result: dict                 # output of evaluate_transaction()
    execution: dict              # output of execute_action()


def detect_node(state: AgentState) -> dict:
    """
    DETECT step. The transaction already exists (created via the API before
    the agent runs) -- this node's job is to mark the moment the agent
    picked it up and confirm the state has what downstream nodes need.
    """
    if "transaction" not in state or "customer" not in state:
        raise ValueError("detect_node requires 'transaction' and 'customer' in state")
    return {"detected_at": datetime.utcnow().isoformat()}


def determine_node(state: AgentState) -> dict:
    """
    DETERMINE step. Runs the real decision engine: guardrails filter which
    active actions are even allowed, the ML model predicts a recovery
    probability for each remaining option, and the EV formula picks the
    highest-net-value action -- including WAIT/DO_NOTHING as first-class
    options. No changes to engine.py; this node just calls it.
    """
    result = evaluate_transaction(state["transaction"], state["customer"], state.get("now"))
    return {"result": result}


def execute_node(state: AgentState) -> dict:
    """
    EXECUTE step. Carries out (in simulated/mock form) whatever action
    determine_node chose. No changes to executor.py; this node just calls it.
    """
    result = state["result"]
    execution = execute_action(
        action=result["recommended_action"],
        amount=result["amount"],
        customer_name=state.get("customer_name", "customer"),
        payment_channel=state.get("payment_channel", "unknown"),
    )
    return {"execution": execution}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("detect", detect_node)
    graph.add_node("determine", determine_node)
    graph.add_node("execute", execute_node)

    graph.add_edge(START, "detect")
    graph.add_edge("detect", "determine")
    graph.add_edge("determine", "execute")
    graph.add_edge("execute", END)

    return graph.compile()


# Compiled once at import time, reused across requests.
_compiled_graph = build_graph()


def run_agent(
    transaction: dict,
    customer: dict,
    customer_name: str,
    payment_channel: str,
    now: Optional[datetime] = None,
) -> AgentState:
    """
    Runs the full detect -> determine -> execute graph for one transaction.
    Returns the final state, which includes both `result` (the decision
    engine's output) and `execution` (the executor's output) -- everything
    routers/analyze.py and routers/simulate.py need to persist and return.
    """
    initial_state: AgentState = {
        "transaction": transaction,
        "customer": customer,
        "customer_name": customer_name,
        "payment_channel": payment_channel,
        "now": now,
    }
    return _compiled_graph.invoke(initial_state)