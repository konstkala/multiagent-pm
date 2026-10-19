"""The splitter as a LangGraph graph (ADR 0021):

    draft → critique ─┬─ ok, or out of rounds ─→ approve (interrupt) → END
                      └─ issues ─→ revise ─→ critique

The graph only talks to the LLM and pauses for a person. It never writes to the database: the
service does that once the graph has returned, so a re-run node can't create anything twice.
State holds plain dicts and lists so the checkpointer can store it as JSON."""

import operator
from dataclasses import asdict
from typing import Annotated, Any, Literal, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]
from langgraph.graph.state import CompiledStateGraph  # pyright: ignore[reportMissingTypeStubs]
from langgraph.types import interrupt

from app.agents.splitter.agent import SplitDraft, SplitInput, critique, draft, revise
from app.core.llm import LLMClient, RunBudget, StructuredResult

# LangGraph's overloaded generics are only partly typed; its own signatures, not our code, are
# what pyright calls unknown here.
# pyright: reportUnknownMemberType=false

MAX_ROUNDS = 2  # critiques per run: after the second, a person decides whatever the critic says


class SplitState(TypedDict):
    """Every key exists from the start (see `initial_state`); nodes return only what they change."""

    ticket: dict[str, Any]  # SplitInput as a dict
    draft: dict[str, Any]  # SplitDraft as a dict
    ok: bool  # the critic's latest verdict
    issues: list[str]
    rounds: int  # critiques done so far
    # `operator.add` makes each node's list get appended to, not replaced.
    calls: Annotated[list[dict[str, Any]], operator.add]
    kept: list[int]  # the manager's answer to the interrupt


def initial_state(data: SplitInput) -> SplitState:
    return {
        "ticket": asdict(data),
        "draft": {},
        "ok": False,
        "issues": [],
        "rounds": 0,
        "calls": [],
        "kept": [],
    }


def route_after_critique(state: SplitState) -> Literal["revise", "approve"]:
    if state["ok"] or state["rounds"] >= MAX_ROUNDS:
        return "approve"
    return "revise"


def build_graph(
    llm: LLMClient, budget: RunBudget, checkpointer: BaseCheckpointSaver[Any]
) -> CompiledStateGraph[SplitState, None, SplitState, SplitState]:
    async def draft_node(state: SplitState) -> dict[str, Any]:
        result = await draft(llm, SplitInput(**state["ticket"]), budget)
        return {"draft": result.output.model_dump(), "calls": [_call("draft", result)]}

    async def critique_node(state: SplitState) -> dict[str, Any]:
        proposal = SplitDraft.model_validate(state["draft"])
        result = await critique(llm, SplitInput(**state["ticket"]), proposal, budget)
        return {
            "ok": result.output.ok,
            "issues": result.output.issues,
            "rounds": state["rounds"] + 1,
            "calls": [_call("critique", result)],
        }

    async def revise_node(state: SplitState) -> dict[str, Any]:
        previous = SplitDraft.model_validate(state["draft"])
        result = await revise(llm, SplitInput(**state["ticket"]), previous, state["issues"], budget)
        return {"draft": result.output.model_dump(), "calls": [_call("revise", result)]}

    def approve_node(state: SplitState) -> dict[str, Any]:
        # Pauses here. The checkpoint keeps the state; the value passed to Command(resume=...)
        # comes back as the return value on resume. No side effects: this node runs again then.
        kept: list[int] = interrupt(
            {"draft": state["draft"], "issues": state["issues"], "rounds": state["rounds"]}
        )
        return {"kept": kept}

    graph = StateGraph(SplitState)
    graph.add_node("draft", draft_node)
    graph.add_node("critique", critique_node)
    graph.add_node("revise", revise_node)
    graph.add_node("approve", approve_node)
    graph.add_edge(START, "draft")
    graph.add_edge("draft", "critique")
    graph.add_conditional_edges("critique", route_after_critique)
    graph.add_edge("revise", "critique")
    graph.add_edge("approve", END)
    return graph.compile(checkpointer=checkpointer)


def _call(node: str, result: StructuredResult[Any]) -> dict[str, Any]:
    return {
        "node": node,
        "model": result.model,
        **result.usage.model_dump(),
        "cost_usd": round(result.cost_usd, 6),
        "latency_ms": result.latency_ms,
    }
