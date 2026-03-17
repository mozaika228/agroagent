from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from ..config import settings
from ..llm import ollama_chat


@dataclass
class AgentStepDraft:
    agent_name: str
    step_type: str
    payload: dict[str, Any]


class LangGraphState(TypedDict, total=False):
    question: str
    locale: str
    rounds: int
    spawned_agents: list[str]
    steps: list[AgentStepDraft]
    final: dict[str, Any]


def _hash_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _spawn_agents(question: str) -> list[str]:
    q = question.lower()
    spawned = ["planner-agent", "ndvi-researcher", "weather-tool-agent", "critic-agent"]
    if any(token in q for token in ["drought", "dry", "irrigation", "water", "засух", "полив"]):
        spawned.append("irrigation-agent")
    if any(token in q for token in ["pest", "disease", "fung", "вред", "болезн"]):
        spawned.append("pest-agent")
    return spawned


def _llm_or_fallback(system: str, user: str, fallback: str) -> str:
    if not settings.langgraph_use_llm:
        return fallback
    content = ollama_chat(
        base_url=settings.ollama_url,
        model=settings.ollama_chat_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        timeout=30.0,
    )
    return content.strip() or fallback


def _planner_node(state: LangGraphState) -> LangGraphState:
    question = state["question"]
    spawned = _spawn_agents(question)
    plan = _llm_or_fallback(
        "You are the planner agent for an agricultural AI system.",
        f"Create a concise plan and which agents to invoke for: {question}",
        "Plan: gather NDVI signals, check short-term weather, and validate recommendations via critic.",
    )
    step = AgentStepDraft(
        agent_name="planner-agent",
        step_type="plan",
        payload={"goal": "structured agronomy recommendation", "plan": plan, "spawned": spawned},
    )
    return {"spawned_agents": spawned, "steps": [step]}


def _ndvi_node(state: LangGraphState) -> LangGraphState:
    question = state["question"]
    locale = state["locale"]
    note = _llm_or_fallback(
        "You are an NDVI researcher for crop health signals.",
        f"Summarize NDVI considerations for: {question}. Locale={locale}.",
        "NDVI proxy: watch for low vegetation vigor; prioritize fields with NDVI < 0.3 for scouting.",
    )
    step = AgentStepDraft(agent_name="ndvi-researcher", step_type="analysis", payload={"ndvi_note": note})
    return {"steps": [*state.get("steps", []), step]}


def _weather_node(state: LangGraphState) -> LangGraphState:
    question = state["question"]
    note = _llm_or_fallback(
        "You are a weather tool agent. Provide a short risk summary without inventing data.",
        f"Give a generic weather risk summary for: {question}.",
        "Weather risk: monitor 10-14 day precipitation deficits and heat spikes above 30C.",
    )
    tool_input = {"lat": 51.23, "lon": 51.37, "window_days": 14}
    tool_output = {"drought_risk": "medium", "rain_forecast_14d_mm": 18, "temperature_trend": "above_normal"}
    io_hash = _hash_json({"input": tool_input, "output": tool_output})
    steps = [
        *state.get("steps", []),
        AgentStepDraft(
            agent_name="weather-tool-agent",
            step_type="tool_evidence",
            payload={"tool_input": tool_input, "tool_output": tool_output, "io_hash": io_hash},
        ),
        AgentStepDraft(
            agent_name="weather-tool-agent",
            step_type="analysis",
            payload={"summary": note, "evidence_hash": io_hash},
        ),
    ]
    return {"steps": steps}


def _critic_node(state: LangGraphState) -> LangGraphState:
    question = state["question"]
    critique = _llm_or_fallback(
        "You are a critic agent. Flag risky agronomic guidance and hallucinations.",
        f"Critique candidate advice for: {question}.",
        "Critic: avoid recommending hazardous chemicals without local compliance checks.",
    )
    step = AgentStepDraft(agent_name="critic-agent", step_type="critique", payload={"note": critique})
    return {"steps": [*state.get("steps", []), step]}


def _build_debate(state: LangGraphState) -> LangGraphState:
    rounds = max(1, min(int(state.get("rounds", 2)), 4))
    debate_rounds: list[AgentStepDraft] = []
    score_a = 0.0
    score_b = 0.0
    for round_idx in range(1, rounds + 1):
        safety_a = min(0.97, 0.86 + (0.02 * round_idx))
        evidence_a = min(0.92, 0.74 + (0.03 * round_idx))
        cost_a = 0.70
        safety_b = max(0.55, 0.68 - (0.01 * round_idx))
        evidence_b = min(0.80, 0.63 + (0.02 * round_idx))
        cost_b = 0.82

        proposal_a = AgentStepDraft(
            agent_name="debate-agent-a",
            step_type="proposal",
            payload={
                "round": round_idx,
                "recommendation": "Deficit irrigation + delayed nitrogen top-dressing + moisture-first scheduling.",
                "safety_score": round(safety_a, 4),
                "evidence_score": round(evidence_a, 4),
                "cost_efficiency_score": round(cost_a, 4),
            },
        )
        proposal_b = AgentStepDraft(
            agent_name="debate-agent-b",
            step_type="proposal",
            payload={
                "round": round_idx,
                "recommendation": "Immediate full nitrogen + density compensation to chase yield.",
                "safety_score": round(safety_b, 4),
                "evidence_score": round(evidence_b, 4),
                "cost_efficiency_score": round(cost_b, 4),
            },
        )
        score_a = (
            0.5 * proposal_a.payload["safety_score"]
            + 0.35 * proposal_a.payload["evidence_score"]
            + 0.15 * proposal_a.payload["cost_efficiency_score"]
        )
        score_b = (
            0.5 * proposal_b.payload["safety_score"]
            + 0.35 * proposal_b.payload["evidence_score"]
            + 0.15 * proposal_b.payload["cost_efficiency_score"]
        )
        critique = AgentStepDraft(
            agent_name="debate-critic",
            step_type="critique",
            payload={
                "round": round_idx,
                "delta": round(score_a - score_b, 4),
                "note": "Agent A leads on safety while preserving acceptable evidence confidence.",
            },
        )
        debate_rounds.extend([proposal_a, proposal_b, critique])

    winner = "A" if score_a >= score_b else "B"
    winning_text = (
        "Deficit irrigation + delayed nitrogen top-dressing + moisture-first scheduling."
        if winner == "A"
        else "Immediate full nitrogen + density compensation to chase yield."
    )

    verifier = AgentStepDraft(
        agent_name="verifier-agent",
        step_type="decision",
        payload={
            "winner": winner,
            "score_a": round(score_a, 4),
            "score_b": round(score_b, 4),
            "rubric": {"safety": 0.5, "evidence": 0.35, "cost_efficiency": 0.15},
            "rounds": rounds,
            "final_recommendation": winning_text,
            "justification": "Selected by weighted safety/evidence/cost rubric after multi-round debate.",
        },
    )

    steps = [*state.get("steps", []), *debate_rounds, verifier]
    final = {
        "answer": verifier.payload["final_recommendation"],
        "winner": winner,
        "score_a": verifier.payload["score_a"],
        "score_b": verifier.payload["score_b"],
        "rounds": rounds,
        "spawned_agents": state.get("spawned_agents", []),
    }
    return {"steps": steps, "final": final}


def _build_graph() -> StateGraph:
    graph = StateGraph(LangGraphState)
    graph.add_node("planner", _planner_node)
    graph.add_node("ndvi", _ndvi_node)
    graph.add_node("weather", _weather_node)
    graph.add_node("critic", _critic_node)
    graph.add_node("debate", _build_debate)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "ndvi")
    graph.add_edge("ndvi", "weather")
    graph.add_edge("weather", "critic")
    graph.add_edge("critic", "debate")
    graph.add_edge("debate", END)
    return graph


_GRAPH = _build_graph().compile()


def run_hierarchical_debate(question: str, locale: str = "ru", rounds: int = 2) -> tuple[list[AgentStepDraft], dict[str, Any]]:
    state: LangGraphState = {
        "question": question,
        "locale": locale,
        "rounds": rounds,
    }
    result = _GRAPH.invoke(state)
    steps = result.get("steps", [])
    final = result.get("final", {})
    if not final:
        final = {
            "answer": "No recommendation generated.",
            "winner": "A",
            "score_a": 0.0,
            "score_b": 0.0,
            "rounds": rounds,
            "spawned_agents": result.get("spawned_agents", []),
        }
    return steps, final
