from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


@dataclass
class AgentStepDraft:
    agent_name: str
    step_type: str
    payload: dict[str, Any]


def _hash_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _spawn_agents(question: str) -> list[str]:
    q = question.lower()
    spawned = ["weather-agent", "soil-agent", "crop-agent"]
    if any(token in q for token in ["drought", "dry", "irrigation", "water", "засух", "полив"]):
        spawned.append("irrigation-agent")
    if any(token in q for token in ["pest", "disease", "fung", "вред", "болезн"]):
        spawned.append("pest-agent")
    if any(token in q for token in ["cattle", "livestock", "cow", "sheep", "скот", "животн"]):
        spawned.append("livestock-agent")
    return spawned


def run_hierarchical_debate(question: str, locale: str = "ru", rounds: int = 2) -> tuple[list[AgentStepDraft], dict[str, Any]]:
    rounds = max(1, min(rounds, 4))
    spawned_agents = _spawn_agents(question)

    # Root plan with dynamic spawn list.
    root = AgentStepDraft(
        agent_name="root-agent",
        step_type="plan",
        payload={
            "goal": "generate drought-aware agronomic recommendation",
            "locale": locale,
            "question": question,
            "spawned": spawned_agents,
            "rounds": rounds,
        },
    )

    analyses: list[AgentStepDraft] = []
    tool_evidence: list[AgentStepDraft] = []
    for agent_name in spawned_agents:
        if agent_name == "weather-agent":
            tool_input = {"lat": 51.23, "lon": 51.37, "window_days": 14}
            tool_output = {"drought_risk": "medium", "rain_forecast_14d_mm": 18, "temperature_trend": "above_normal"}
        elif agent_name == "soil-agent":
            tool_input = {"region": "WKO", "depth_cm": [0, 20]}
            tool_output = {"soil_moisture_status": "low", "topsoil_condition": "dry", "irrigation_readiness": "required"}
        elif agent_name == "crop-agent":
            tool_input = {"crop": "spring wheat", "stage_source": "field_log"}
            tool_output = {"growth_stage": "early", "stress_signal": "moderate", "yield_risk": "medium"}
        elif agent_name == "irrigation-agent":
            tool_input = {"canal_access": True, "pump_capacity_m3h": 42}
            tool_output = {"window_days": 5, "target_mm": 12, "priority": "high"}
        elif agent_name == "pest-agent":
            tool_input = {"last_scouting_days": 4, "humidity_flag": True}
            tool_output = {"disease_risk": "low", "pest_pressure": "medium", "spray_now": False}
        else:
            tool_input = {"species": "mixed", "head_count": 120}
            tool_output = {"heat_stress_risk": "medium", "water_need_lpd": 55, "action": "increase watering points"}

        io_hash = _hash_json({"input": tool_input, "output": tool_output})
        tool_evidence.append(
            AgentStepDraft(
                agent_name=agent_name,
                step_type="tool_evidence",
                payload={"tool_input": tool_input, "tool_output": tool_output, "io_hash": io_hash},
            )
        )
        analyses.append(
            AgentStepDraft(
                agent_name=agent_name,
                step_type="analysis",
                payload={**tool_output, "evidence_hash": io_hash},
            )
        )

    score_a = 0.0
    score_b = 0.0
    debate_rounds: list[AgentStepDraft] = []
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

    # Verifier decides winner by weighted rubric.
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

    steps = [root, *tool_evidence, *analyses, *debate_rounds, verifier]
    final = {
        "answer": verifier.payload["final_recommendation"],
        "winner": winner,
        "score_a": verifier.payload["score_a"],
        "score_b": verifier.payload["score_b"],
        "rounds": rounds,
        "spawned_agents": spawned_agents,
    }
    return steps, final
