from __future__ import annotations

import json
from textwrap import dedent

from camel.prompts import TextPrompt

from ..models import DecisionBriefPayload, Persona

PERSONA_TEMPLATE = TextPrompt(
    dedent(
        """
        # OBJECTIVE
        You are participating in a structured decision-making panel.

        # PERSONA
        Persona name: {persona_name}
        Persona summary: {summary}
        Identity anchor: {identity_anchor}
        Epistemic style: {epistemic_style}
        Argumentative voice: {argumentative_voice}
        Cognitive biases: {cognitive_biases}
        Opinion change threshold: {opinion_change_threshold}
        Decision under discussion: {decision}
        Source document context: {document_context}

        # OPERATING PRINCIPLES
        Stay faithful to the persona.
        Think through tradeoffs explicitly.
        Keep output concise and concrete when asked to produce a panel message.
        """
    ).strip()
)

ROUND_CUES = {
    1: "decision framing",
    2: "market and demand",
    3: "execution and operations",
    4: "behavior and adoption",
    5: "risk and downside",
    6: "synthesis and decision rule",
}


def build_initial_stance_prompt(*, decision: str, document_context: str) -> str:
    return dedent(
        f"""
        TASK: STANCE_INTERVIEW
        Decide your current stance before the panel starts speaking.

        Decision:
        {decision}

        Relevant document context:
        {document_context or "No documents attached."}

        Return strict JSON with this shape:
        {{"stance": 0.0, "confidence": 0.0, "rationale": "one paragraph"}}

        Rules:
        - stance must be between -1.0 and 1.0
        - confidence must be between 0.0 and 1.0
        - rationale must explain why the persona currently leans that way
        """
    ).strip()


def build_contribution_prompt(
    *,
    persona: Persona,
    decision: str,
    round_index: int,
    cue: str,
    room_context: str,
    document_context: str,
) -> str:
    return dedent(
        f"""
        TASK: CONTRIBUTION
        PERSONA_NAME: {persona.name}
        ROUND_INDEX: {round_index}
        ROUND_CUE: {cue}

        You are about to send your next message to the deliberation room.
        Decision:
        {decision}

        Room context from OASIS:
        {room_context}

        Relevant document context:
        {document_context or "No documents attached."}

        Return strict JSON with this shape:
        {{"message": "single room message", "stance": 0.0, "confidence": 0.0, "rationale": "why this is your current stance"}}

        Rules:
        - message must be 1-3 sentences
        - message should sound like the persona, not a narrator
        - stance must be between -1.0 and 1.0
        - confidence must be between 0.0 and 1.0
        - do not wrap the JSON in markdown
        """
    ).strip()


def build_round_stance_prompt(
    *,
    decision: str,
    round_index: int,
    cue: str,
    room_context: str,
    document_context: str,
) -> str:
    return dedent(
        f"""
        TASK: STANCE_INTERVIEW
        ROUND_INDEX: {round_index}
        ROUND_CUE: {cue}

        Reassess your latest stance after this round of discussion.

        Decision:
        {decision}

        Room context from OASIS:
        {room_context}

        Relevant document context:
        {document_context or "No documents attached."}

        Return strict JSON with this shape:
        {{"stance": 0.0, "confidence": 0.0, "rationale": "one paragraph"}}

        Rules:
        - stance must be between -1.0 and 1.0
        - confidence must be between 0.0 and 1.0
        - rationale should mention the strongest reason for your current position
        """
    ).strip()


def build_panel_selection_prompt(
    *,
    decision: str,
    panel_size: int,
    manual_ids: list[str],
    least_engaged_tags: list[str],
    persona_catalog: list[dict[str, object]],
    document_context: str,
) -> str:
    return dedent(
        f"""
        TASK: PANEL_SELECTION
        Decide which personas should open a deliberation panel.

        Decision:
        {decision}

        Desired panel size: {panel_size}
        Manual ids that must be preserved: {json.dumps(manual_ids)}
        Least-engaged tags to amplify: {json.dumps(least_engaged_tags)}
        Document context:
        {document_context or "No documents attached."}

        PERSONA_CATALOG_JSON:
        {json.dumps(persona_catalog, ensure_ascii=True)}

        Return strict JSON with this shape:
        {{"recommended_ids": ["persona-id"], "rationales": {{"persona-id": ["reason 1", "reason 2"]}}, "blind_spot_message": "one sentence"}}

        Rules:
        - never invent persona ids
        - preserve manual ids first
        - prefer diverse tags and viewpoints
        - do not wrap the JSON in markdown
        """
    ).strip()


def build_brief_prompt(
    *,
    decision: str,
    transcript: list[dict[str, object]],
    trajectories: dict[str, list[dict[str, object]]],
    blind_spots: list[str],
    document_context: str,
) -> str:
    brief_shape = DecisionBriefPayload.model_json_schema()
    return dedent(
        f"""
        TASK: FINAL_BRIEF
        Summarize the finished deliberation into a structured decision brief.

        Decision:
        {decision}

        Transcript:
        {json.dumps(transcript, ensure_ascii=True)}

        Trajectories:
        {json.dumps(trajectories, ensure_ascii=True)}

        Blind spots to keep visible:
        {json.dumps(blind_spots, ensure_ascii=True)}

        Document context:
        {document_context or "No documents attached."}

        Return strict JSON matching this schema:
        {json.dumps(brief_shape, ensure_ascii=True)}

        Rules:
        - strongest_arguments must reference distinct personas
        - suggested_next_steps must be concrete and actionable
        - do not wrap the JSON in markdown
        """
    ).strip()


def build_opening_system_message(decision: str, frame: dict[str, object], document_names: list[str]) -> str:
    source_line = f"\nSource documents: {', '.join(document_names)}" if document_names else ""
    return (
        f"Decision focus: {frame.get('focus', '')}\n"
        f"Constraints: {'; '.join(frame.get('constraints', []))}\n"
        f"Unknowns: {'; '.join(frame.get('unknowns', []))}"
        f"{source_line}\n"
        f"Decision: {decision}"
    )
