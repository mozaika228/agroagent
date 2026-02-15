from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentStepDraft:
    agent_name: str
    step_type: str
    payload: dict[str, Any]


def run_hierarchical_debate(question: str, locale: str = "ru") -> tuple[list[AgentStepDraft], dict[str, Any]]:
    # Root plan
    root = AgentStepDraft(
        agent_name="root-agent",
        step_type="plan",
        payload={
            "goal": "generate drought-aware agronomic recommendation",
            "locale": locale,
            "question": question,
            "spawned": ["weather-agent", "soil-agent", "crop-agent"],
        },
    )

    # Sub-agent outputs (deterministic baseline logic; replace with tool-driven calls later).
    weather = AgentStepDraft(
        agent_name="weather-agent",
        step_type="analysis",
        payload={
            "drought_risk": "medium",
            "rain_forecast_14d_mm": 18,
            "temperature_trend": "above_normal",
        },
    )
    soil = AgentStepDraft(
        agent_name="soil-agent",
        step_type="analysis",
        payload={
            "soil_moisture_status": "low",
            "topsoil_condition": "dry",
            "irrigation_readiness": "required",
        },
    )
    crop = AgentStepDraft(
        agent_name="crop-agent",
        step_type="analysis",
        payload={
            "crop": "spring wheat",
            "growth_stage": "early",
            "stress_signal": "moderate",
        },
    )

    # Debate proposals
    proposal_a = AgentStepDraft(
        agent_name="debate-agent-a",
        step_type="proposal",
        payload={
            "recommendation": "Prioritize deficit irrigation and postpone nitrogen top-dressing by 5-7 days.",
            "safety_score": 0.90,
            "evidence_score": 0.78,
        },
    )
    proposal_b = AgentStepDraft(
        agent_name="debate-agent-b",
        step_type="proposal",
        payload={
            "recommendation": "Apply full nitrogen now and increase seeding density to offset expected losses.",
            "safety_score": 0.62,
            "evidence_score": 0.66,
        },
    )

    # Verifier decides winner by weighted score.
    score_a = (0.65 * proposal_a.payload["safety_score"]) + (0.35 * proposal_a.payload["evidence_score"])
    score_b = (0.65 * proposal_b.payload["safety_score"]) + (0.35 * proposal_b.payload["evidence_score"])
    winner = "A" if score_a >= score_b else "B"
    winning_payload = proposal_a.payload if winner == "A" else proposal_b.payload

    verifier = AgentStepDraft(
        agent_name="verifier-agent",
        step_type="decision",
        payload={
            "winner": winner,
            "score_a": round(score_a, 4),
            "score_b": round(score_b, 4),
            "final_recommendation": winning_payload["recommendation"],
            "justification": "Selected by weighted safety/evidence rubric.",
        },
    )

    steps = [root, weather, soil, crop, proposal_a, proposal_b, verifier]
    final = {
        "answer": verifier.payload["final_recommendation"],
        "winner": winner,
        "score_a": verifier.payload["score_a"],
        "score_b": verifier.payload["score_b"],
    }
    return steps, final
