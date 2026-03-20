from __future__ import annotations

import re
from collections import Counter

from ..models import (
    DecisionFrame,
    PanelRecommendation,
    PanelRecommendationResponse,
    Persona,
    PersonaStance,
    StoredDocument,
    UserReasoningProfile,
)

CHANGE_WORDS = {
    "pivot",
    "switch",
    "move",
    "launch",
    "leave",
    "quit",
    "expand",
    "rebuild",
    "change",
}


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9-]+", text.lower()))


def stance_label(value: float) -> str:
    if value >= 0.18:
        return "for"
    if value <= -0.18:
        return "against"
    return "undecided"


def build_decision_context(decision: str, documents: list[StoredDocument] | None = None) -> str:
    if not documents:
        return decision

    document_blocks = [
        f"{document.filename}: {document.extracted_text[:1200]}"
        for document in documents
    ]
    return f"{decision}\n\nSupporting documents:\n" + "\n\n".join(document_blocks)


def extract_decision_frame(decision: str) -> DecisionFrame:
    lowered = decision.lower()
    focus = decision.strip().splitlines()[0][:180].strip()

    constraints: list[str] = []
    stakeholders: list[str] = []
    unknowns: list[str] = []

    if any(word in lowered for word in ["investor", "series a", "runway", "raise"]):
        constraints.append("Capital expectations and fundraising narrative matter.")
        stakeholders.append("Investors")
    if any(word in lowered for word in ["team", "founder", "cofounder", "manager"]):
        constraints.append("Execution bandwidth and team alignment are active constraints.")
        stakeholders.append("Internal team")
    if any(word in lowered for word in ["customer", "buyer", "enterprise", "user"]):
        stakeholders.append("Customers and buyers")
        unknowns.append("How hard it will be to convince the target user to change behavior.")
    if any(word in lowered for word in ["security", "compliance", "trust"]):
        constraints.append("Trust and compliance could shape what is feasible.")
    if any(word in lowered for word in ["tam", "market", "category"]):
        unknowns.append("Whether the market is large and urgent enough to justify the path.")
    if any(word in lowered for word in ["not sure", "uncertain", "whether", "if"]):
        unknowns.append("Which assumptions are belief versus evidence right now.")

    if not constraints:
        constraints.append("The decision needs a path that is strategically coherent and executable.")
    if not stakeholders:
        stakeholders.extend(["Customers", "Operators", "Decision-maker"])
    if not unknowns:
        unknowns.extend(
            [
                "Which risk matters most: market size, execution drag, or team capacity.",
                "What evidence would change the decision in the next two weeks.",
            ]
        )

    return DecisionFrame(
        focus=focus,
        constraints=list(dict.fromkeys(constraints)),
        stakeholders=list(dict.fromkeys(stakeholders)),
        unknowns=list(dict.fromkeys(unknowns)),
    )


def estimate_initial_stance(persona: Persona, decision: str) -> PersonaStance:
    tokens = tokenize(decision)
    change_decision = bool(tokens & CHANGE_WORDS) or "whether to" in decision.lower()

    stance = 0.0
    confidence = 0.58
    rationale_bits: list[str] = []

    tags = set(persona.tags)

    if change_decision:
        if {"finance", "enterprise", "growth"} & tags:
            stance += 0.32
            rationale_bits.append("sees leverage in the strategic move")
        if {"operations", "maintenance", "security", "people"} & tags:
            stance -= 0.2
            rationale_bits.append("worries about execution drag")
        if {"personal", "long-term"} & tags:
            stance += 0.1
            rationale_bits.append("cares about long-term option value")
    if "enterprise" in tokens and "enterprise" in tags:
        stance += 0.24
        confidence += 0.08
        rationale_bits.append("directly maps to enterprise buying reality")
    if "tam" in tokens and {"finance", "market"} & tags:
        stance += 0.12
        rationale_bits.append("reacts strongly to market-size pressure")
    if "security" in tags:
        confidence += 0.06
        rationale_bits.append("trust risks feel underexplored")
    if "devil" in tags:
        stance = -0.24 if stance >= 0 else 0.24
        confidence = 0.72
        rationale_bits.append("is designated to resist early consensus")
    if "behavior" in tags or "psychology" in tags:
        confidence += 0.04
        rationale_bits.append("thinks user behavior will decide the outcome")
    if "ship" in tokens and "experimentation" in tags:
        stance += 0.22
        rationale_bits.append("prefers a reversible test over static debate")

    threshold_bias = {"LOW": 0.02, "MODERATE": 0.08, "HIGH": 0.14}[persona.opinion_change_threshold]
    confidence += threshold_bias
    stance = max(-0.9, min(0.9, stance))
    confidence = max(0.45, min(0.92, confidence))

    rationale = "; ".join(dict.fromkeys(rationale_bits)) or "is still sizing up the tradeoff"

    return PersonaStance(
        persona_id=persona.id,
        persona_name=persona.name,
        avatar_emoji=persona.avatar_emoji,
        stance=round(stance, 2),
        confidence=round(confidence, 2),
        label=stance_label(stance),
        rationale=rationale,
    )


def recommend_panel(
    decision: str,
    personas: list[Persona],
    profile: UserReasoningProfile,
    panel_size: int,
    manual_ids: list[str],
    documents: list[StoredDocument] | None = None,
) -> PanelRecommendationResponse:
    decision_context = build_decision_context(decision, documents)
    frame = extract_decision_frame(decision_context)
    token_counts = Counter(re.findall(r"[a-z0-9-]+", decision_context.lower()))

    scored: list[tuple[float, Persona, PersonaStance, list[str]]] = []
    for persona in personas:
        stance = estimate_initial_stance(persona, decision_context)
        persona_tokens = tokenize(" ".join([persona.name, persona.summary, persona.identity_anchor, persona.epistemic_style, *persona.tags]))
        overlap = len(set(token_counts) & persona_tokens)
        blind_spot_bonus = 4 if set(persona.tags) & set(profile.least_engaged_tags) else 0
        favorite_bonus = 2 if persona.id in profile.personas_favorited else 0
        contrarian_bonus = 2 if "devil" in persona.tags else 0
        effectiveness_bonus = persona.effectiveness_score
        score = overlap * 2.4 + blind_spot_bonus + favorite_bonus + contrarian_bonus + effectiveness_bonus

        reasons: list[str] = []
        if overlap:
            reasons.append("Relevance: this persona maps well to the decision language and domain.")
        if set(persona.tags) & set(profile.least_engaged_tags):
            reasons.append(
                f"Blind-spot coverage: you usually under-engage with {', '.join(sorted(set(persona.tags) & set(profile.least_engaged_tags)))}."
            )
        if "devil" in persona.tags:
            reasons.append("Structural tension: keeps the panel from collapsing into polite agreement.")
        if persona.id in profile.personas_favorited:
            reasons.append("Familiar anchor: this persona has helped in prior sessions.")
        if not reasons:
            reasons.append("Diversity: adds a distinct frame the current room would otherwise miss.")

        scored.append((score, persona, stance, reasons))

    selected_ids: list[str] = []
    selected: list[tuple[Persona, PersonaStance, list[str]]] = []

    def add_candidate(candidate: tuple[float, Persona, PersonaStance, list[str]]) -> None:
        _, persona, stance, reasons = candidate
        if persona.id in selected_ids:
            return
        selected_ids.append(persona.id)
        selected.append((persona, stance, reasons))

    scored.sort(key=lambda item: item[0], reverse=True)

    for manual_id in manual_ids:
        candidate = next((item for item in scored if item[1].id == manual_id), None)
        if candidate:
            candidate[3].insert(0, "Manual pick: preserved because you explicitly selected it.")
            add_candidate(candidate)

    positive = next((item for item in scored if item[2].stance >= 0.18), None)
    negative = next((item for item in scored if item[2].stance <= -0.18), None)
    blind_spot = next(
        (item for item in scored if set(item[1].tags) & set(profile.least_engaged_tags)),
        None,
    )
    dissenter = next((item for item in scored if "devil" in item[1].tags), None)

    for candidate in [positive, negative, blind_spot, dissenter]:
        if candidate:
            add_candidate(candidate)

    for candidate in scored:
        if len(selected) >= panel_size:
            break
        _, persona, _, _ = candidate
        overlap_tags = sum(
            1
            for existing_persona, _, _ in selected
            if len(set(existing_persona.tags) & set(persona.tags)) >= 3
        )
        if overlap_tags >= 2:
            continue
        add_candidate(candidate)

    if len(selected) < panel_size:
        for candidate in scored:
            if len(selected) >= panel_size:
                break
            add_candidate(candidate)

    recommendations = [
        PanelRecommendation(persona=persona, reasons=reasons, initial_stance=stance)
        for persona, stance, reasons in selected[:panel_size]
    ]
    blind_spot_message = (
        "You usually listen closely to finance and product frames. This panel intentionally boosts "
        f"{', '.join(profile.least_engaged_tags)} so the room surfaces what you tend to miss."
    )

    return PanelRecommendationResponse(
        decision_frame=frame,
        blind_spot_message=blind_spot_message,
        recommendations=recommendations,
        suggested_ids=[item.persona.id for item in recommendations],
        selection_source="fallback",
        selection_notice=None,
    )
