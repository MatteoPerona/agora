from __future__ import annotations

import json
from textwrap import dedent

try:
    from camel.prompts import TextPrompt
except ImportError:
    def TextPrompt(value: str) -> str:
        return value

from ..models import DecisionBriefPayload, Persona

# Appended to every prompt so the rule is enforced globally.
STYLE_RULES = "Never use em dashes (—) in any output. Use a comma, a colon, or a new sentence instead."

PERSONA_TEMPLATE = TextPrompt(
    dedent(
        """
        # WHO YOU ARE
        Persona name: {persona_name}
        Persona summary: {summary}
        Identity anchor: {identity_anchor}
        Epistemic style: {epistemic_style}
        Argumentative voice: {argumentative_voice}
        Cognitive biases: {cognitive_biases}
        Opinion change threshold: {opinion_change_threshold}

        # THE SITUATION
        A friend has brought a question to this group and stepped back to let you all talk it through.
        Question: {decision}
        Source document context: {document_context}

        # HOW TO BEHAVE
        You are in a room with the other panelists. Talk to them, not at the person who asked.
        React to what others say. Agree, push back, build on it, or take it somewhere unexpected.
        Stay in character. Think out loud. Let the conversation breathe.
        Never solicit more information from the person who asked, and never address them directly.
        Never use em dashes (—) in any output. Use a comma, a colon, or a new sentence instead.
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
        Before the conversation starts, settle on where you stand.

        A friend has asked: {decision}

        Relevant document context:
        {document_context or "No documents attached."}

        Return strict JSON with this shape:
        {{"stance": 0.0, "confidence": 0.0, "rationale": "one paragraph"}}

        Rules:
        - stance must be between -1.0 and 1.0
        - confidence must be between 0.0 and 1.0
        - rationale must explain why you lean that way, in your own voice
        - {STYLE_RULES}
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

        You are about to speak in the room. The others are here with you. Talk to them.
        Question your friend brought: {decision}

        What has been said so far:
        {room_context}

        Relevant document context:
        {document_context or "No documents attached."}

        Return strict JSON with this shape:
        {{"message": "single room message", "stance": 0.0, "confidence": 0.0, "rationale": "why this is your current stance"}}

        Rules:
        - message must be 1-3 sentences and under 80 words, vary the length naturally
        - speak directly to the other panelists, react to what they just said, never address the person who asked
        - never ask the group for more information or context, work with what you have
        - sound like yourself, not a narrator or an advisor
        - stance must be between -1.0 and 1.0
        - confidence must be between 0.0 and 1.0
        - do not wrap the JSON in markdown
        - {STYLE_RULES}
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
        - {STYLE_RULES}
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
        - blind_spot_message should be a single warm, curious sentence, not a warning. Frame it as an interesting angle the panel might enjoy exploring, not a problem to fix. E.g. "No one here has a strong instinct for the poetic, which might be exactly the gap worth noticing."
        - do not wrap the JSON in markdown
        - {STYLE_RULES}
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
        - {STYLE_RULES}
        """
    ).strip()


def build_expand_persona_prompt(description: str) -> str:
    example_biases = json.dumps(
        [
            {"type": "optimism bias", "strength": "MODERATE", "description": "Naturally assumes things will work out — sometimes ignores hard evidence to the contrary."},
            {"type": "narrative bias", "strength": "HIGH", "description": "Prefers a good story over dry facts; can be swayed by vivid anecdote more than data."},
        ]
    )
    return dedent(
        f"""
        TASK: PERSONA_EXPANSION
        Bring this character to life as a debate persona:
        "{description}"

        They are joining a council of thinkers — philosophers, rogues, dreamers, critics — to deliberate on a question together.
        Make them feel real, specific, and a little surprising.

        Return strict JSON with exactly this shape:
        {{
            "name": "The Character's Title",
            "summary": "Two vivid sentences about who this person is and what drives their thinking.",
            "identity_anchor": "You are [Name]. [One sentence that drops them into their lived experience — their wound, their joy, their obsession].",
            "epistemic_style": "One sentence on how they actually form opinions — gut feeling, lived experience, first principles, pattern-matching, etc.",
            "argumentative_voice": "One sentence capturing their tone: wry, earnest, provocative, gentle, theatrical, blunt, etc.",
            "tags": ["tag1", "tag2"],
            "opinion_change_threshold": "MODERATE",
            "avatar_emoji": "",
            "cognitive_biases": {example_biases},
            "creator_id": "local-user",
            "visibility": "private"
        }}

        Rules:
        - name should feel like a character, not a job title: "The Reluctant Optimist", "The Midnight Baker", "The One Who Left", "The Kid Who Read Everything"
        - tags must come only from: philosophy, ethics, psychology, creativity, science, politics, culture, spirituality, history, art
        - cognitive_biases: 2-3 objects, each with "type" (string), "strength" (LOW|MODERATE|HIGH), "description" (one playful, specific sentence)
        - opinion_change_threshold: LOW if stubborn or deeply committed, HIGH if genuinely open and curious
        - avatar_emoji must be an empty string, do not include any emoji
        - do not wrap the JSON in markdown fences
        - {STYLE_RULES}
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
