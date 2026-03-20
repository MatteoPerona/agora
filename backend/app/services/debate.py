from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from statistics import mean
from typing import Iterable
from uuid import uuid4

from ..models import (
    ArgumentHighlight,
    DecisionBrief,
    Message,
    NetworkEdge,
    Persona,
    PersonaStance,
    SessionSnapshot,
    TrajectoryPoint,
    TrajectorySeries,
    UserReasoningProfile,
)
from .panel import estimate_initial_stance, extract_decision_frame, stance_label, tokenize


@dataclass
class RuntimePersona:
    persona: Persona
    stance: float
    confidence: float
    initial_stance: float
    history: list[TrajectoryPoint] = field(default_factory=list)


@dataclass
class RuntimeSession:
    session_id: str
    decision: str
    decision_context: str
    document_names: list[str]
    round_goal: int
    profile: UserReasoningProfile
    personas: dict[str, RuntimePersona]
    messages: list[Message]
    network_edges: list[NetworkEdge]
    current_round: int = 0
    status: str = "running"
    brief: DecisionBrief | None = None
    pending_user_messages: list[str] = field(default_factory=list)


SESSIONS: dict[str, RuntimeSession] = {}

ROUND_CUES = {
    1: "decision framing",
    2: "market and demand",
    3: "execution and operations",
    4: "behavior and adoption",
    5: "risk and downside",
    6: "synthesis and decision rule",
}


def create_session(
    *,
    decision: str,
    personas: list[Persona],
    profile: UserReasoningProfile,
    round_goal: int,
    document_context: str = "",
    document_names: list[str] | None = None,
) -> SessionSnapshot:
    session_id = str(uuid4())
    contextual_decision = decision if not document_context else f"{decision}\n\nSupporting documents:\n{document_context}"
    runtime_personas: dict[str, RuntimePersona] = {}
    for persona in personas:
        initial = estimate_initial_stance(persona, contextual_decision)
        runtime_personas[persona.id] = RuntimePersona(
            persona=persona,
            stance=initial.stance,
            confidence=initial.confidence,
            initial_stance=initial.stance,
            history=[TrajectoryPoint(round_index=0, stance=initial.stance, confidence=initial.confidence)],
        )

    frame = extract_decision_frame(contextual_decision)
    source_line = ""
    if document_names:
        source_line = f"\nSource documents: {', '.join(document_names)}"
    opening_message = Message(
        id=str(uuid4()),
        author_id="orchestrator",
        author_name="Deliberation Engine",
        avatar_emoji="🛰️",
        role="system",
        round_index=0,
        cue="frame",
        content=(
            f"Decision focus: {frame.focus}\n"
            f"Constraints: {'; '.join(frame.constraints)}\n"
            f"Unknowns: {'; '.join(frame.unknowns)}"
            f"{source_line}"
        ),
        timestamp=_timestamp(),
    )
    session = RuntimeSession(
        session_id=session_id,
        decision=decision,
        decision_context=contextual_decision,
        document_names=document_names or [],
        round_goal=round_goal,
        profile=profile,
        personas=runtime_personas,
        messages=[opening_message],
        network_edges=_build_network(list(personas)),
    )
    SESSIONS[session_id] = session
    return snapshot_session(session)


def add_interjection(session_id: str, content: str) -> SessionSnapshot:
    session = SESSIONS[session_id]
    session.pending_user_messages.append(content)
    session.messages.append(
        Message(
            id=str(uuid4()),
            author_id="user",
            author_name="You",
            avatar_emoji="✍️",
            role="user",
            round_index=session.current_round,
            content=content,
            cue="user interjection",
            timestamp=_timestamp(),
        )
    )
    return snapshot_session(session)


def advance_session(session_id: str) -> SessionSnapshot:
    session = SESSIONS[session_id]
    if session.status == "complete":
        return snapshot_session(session)

    session.current_round += 1
    cue = ROUND_CUES.get(session.current_round, "deliberation")
    active_ids = _active_persona_ids(session.personas.values(), session.current_round)
    consensus = mean(runtime.stance for runtime in session.personas.values())
    spread = max(runtime.stance for runtime in session.personas.values()) - min(
        runtime.stance for runtime in session.personas.values()
    )

    for persona_id in active_ids:
        runtime = session.personas[persona_id]
        peer_names = _peer_names(session, persona_id)
        content = _compose_message(
            runtime=runtime,
            decision=session.decision_context,
            round_index=session.current_round,
            cue=cue,
            peer_names=peer_names,
            user_messages=session.pending_user_messages,
            spread=spread,
        )
        new_stance, new_confidence = _update_state(
            runtime=runtime,
            session=session,
            consensus=consensus,
            spread=spread,
        )
        runtime.stance = new_stance
        runtime.confidence = new_confidence
        runtime.history.append(
            TrajectoryPoint(
                round_index=session.current_round,
                stance=round(new_stance, 2),
                confidence=round(new_confidence, 2),
            )
        )
        session.messages.append(
            Message(
                id=str(uuid4()),
                author_id=runtime.persona.id,
                author_name=runtime.persona.name,
                avatar_emoji=runtime.persona.avatar_emoji,
                role="persona",
                round_index=session.current_round,
                content=content,
                cue=cue,
                stance=round(new_stance, 2),
                confidence=round(new_confidence, 2),
                timestamp=_timestamp(),
            )
        )

    session.pending_user_messages.clear()

    if session.current_round >= session.round_goal:
        session.status = "complete"

    return snapshot_session(session)


def finish_session(session_id: str) -> SessionSnapshot:
    session = SESSIONS[session_id]
    if session.brief is None:
        session.brief = _build_brief(session)
    session.status = "complete"
    return snapshot_session(session)


def get_session_snapshot(session_id: str) -> SessionSnapshot:
    session = SESSIONS[session_id]
    return snapshot_session(session)


def snapshot_session(session: RuntimeSession) -> SessionSnapshot:
    roster = [
        PersonaStance(
            persona_id=runtime.persona.id,
            persona_name=runtime.persona.name,
            avatar_emoji=runtime.persona.avatar_emoji,
            stance=round(runtime.stance, 2),
            confidence=round(runtime.confidence, 2),
            label=stance_label(runtime.stance),
            rationale=_roster_rationale(runtime),
        )
        for runtime in session.personas.values()
    ]
    trajectories = [
        TrajectorySeries(
            persona_id=runtime.persona.id,
            persona_name=runtime.persona.name,
            avatar_emoji=runtime.persona.avatar_emoji,
            points=runtime.history,
        )
        for runtime in session.personas.values()
    ]
    return SessionSnapshot(
        session_id=session.session_id,
        decision=session.decision,
        current_round=session.current_round,
        round_goal=session.round_goal,
        status="complete" if session.status == "complete" else "running",
        messages=session.messages,
        roster=roster,
        trajectories=trajectories,
        network_edges=session.network_edges,
        brief=session.brief,
    )


def _build_network(personas: list[Persona]) -> list[NetworkEdge]:
    edges: list[NetworkEdge] = []
    total = len(personas)
    for index, persona in enumerate(personas):
        neighbor = personas[(index + 1) % total]
        edges.append(NetworkEdge(source_id=persona.id, target_id=neighbor.id))
        bridge = personas[(index + 2) % total]
        if bridge.id != neighbor.id:
            edges.append(NetworkEdge(source_id=persona.id, target_id=bridge.id))
    return edges


def _active_persona_ids(personas: Iterable[RuntimePersona], round_index: int) -> list[str]:
    ordered = list(personas)
    if round_index == 1:
        return [runtime.persona.id for runtime in ordered]
    parity = round_index % 2
    active = [runtime.persona.id for index, runtime in enumerate(ordered) if index % 2 == parity]
    if len(active) < 3:
        active = [runtime.persona.id for runtime in ordered[:3]]
    return active


def _peer_names(session: RuntimeSession, persona_id: str) -> list[str]:
    neighbors = [
        edge.target_id
        for edge in session.network_edges
        if edge.source_id == persona_id
    ]
    return [
        session.personas[neighbor].persona.name
        for neighbor in neighbors
        if neighbor in session.personas
    ]


def _compose_message(
    *,
    runtime: RuntimePersona,
    decision: str,
    round_index: int,
    cue: str,
    peer_names: list[str],
    user_messages: list[str],
    spread: float,
) -> str:
    tags = set(runtime.persona.tags)
    tokens = tokenize(decision)
    mentions_user = ""
    if user_messages:
        mentions_user = f"You just raised: '{user_messages[-1]}'. From my seat, that changes the weighting but not the core frame. "

    if {"finance", "market", "enterprise"} & tags:
        angle = "The market story has to survive contact with budgets, buying cycles, and a credible wedge."
    elif {"engineering", "maintenance", "security"} & tags:
        angle = "The real question is what hidden complexity gets imported the moment this becomes real."
    elif {"operations", "team", "people"} & tags:
        angle = "A strategy that looks elegant but overloads the team is not actually a strategy."
    elif {"psychology", "behavior"} & tags:
        angle = "The user behavior change required here may be the whole game."
    elif {"personal", "long-term", "reflection"} & tags:
        angle = "This should be judged by the future options it creates, not just the next narrative beat."
    else:
        angle = "The strongest argument is usually hiding behind the assumption nobody is naming."

    if runtime.stance >= 0.18:
        posture = "I still lean toward the move."
    elif runtime.stance <= -0.18:
        posture = "I still lean against the move."
    else:
        posture = "I am still near the middle, but the burden of proof is shifting."

    cross_reference = ""
    if peer_names:
        cross_reference = f" {peer_names[0]} is pressing on one side of this, but the room is still underpricing the opposite failure mode."

    convergence_line = ""
    if spread < 0.35 and "devil" in tags:
        convergence_line = " The room is converging too neatly, which usually means we are compressing the risk surface into a story we like."

    decision_hint = ""
    if "enterprise" in tokens and "enterprise" in tags:
        decision_hint = " Enterprise fit is not a slogan here; it lives or dies on implementation pain and who signs."
    elif "tam" in tokens and {"finance", "market"} & tags:
        decision_hint = " If the TAM concern is real, everything else becomes decoration."
    elif "pivot" in tokens and {"product", "experimentation"} & tags:
        decision_hint = " If you pivot, make it testable before you make it total."

    return f"{mentions_user}{posture} {angle}{decision_hint}{cross_reference}{convergence_line}"


def _update_state(
    *,
    runtime: RuntimePersona,
    session: RuntimeSession,
    consensus: float,
    spread: float,
) -> tuple[float, float]:
    threshold_multiplier = {
        "LOW": 1.0,
        "MODERATE": 0.72,
        "HIGH": 0.48,
    }[runtime.persona.opinion_change_threshold]
    delta = (consensus - runtime.stance) * 0.22
    delta = max(-0.2, min(0.2, delta))

    if runtime.initial_stance == 0 or (runtime.initial_stance > 0) == (delta > 0):
        commitment_penalty = 1.0
    else:
        commitment_penalty = 0.55

    if "devil" in runtime.persona.tags and spread < 0.4:
        delta = -0.16 if consensus >= 0 else 0.16

    if session.pending_user_messages:
        delta *= 0.85

    new_stance = runtime.stance + delta * threshold_multiplier * commitment_penalty
    new_stance = max(-0.95, min(0.95, new_stance))

    confidence_shift = 0.02 if abs(new_stance) >= abs(runtime.stance) else -0.03
    if session.pending_user_messages:
        confidence_shift -= 0.02
    new_confidence = max(0.42, min(0.94, runtime.confidence + confidence_shift))
    return round(new_stance, 4), round(new_confidence, 4)


def _roster_rationale(runtime: RuntimePersona) -> str:
    movement = runtime.stance - runtime.initial_stance
    if abs(movement) < 0.05:
        return "holding close to the opening stance"
    if movement > 0:
        return "has been pulled slightly toward change"
    return "has become more cautious over time"


def _build_brief(session: RuntimeSession) -> DecisionBrief:
    positives = [runtime for runtime in session.personas.values() if runtime.stance >= 0.18]
    negatives = [runtime for runtime in session.personas.values() if runtime.stance <= -0.18]
    middle = [runtime for runtime in session.personas.values() if abs(runtime.stance) < 0.18]

    headline = (
        f"{len(positives)} personas end pro-move, {len(negatives)} stay cautious, "
        f"and {len(middle)} remain undecided."
    )
    landscape_summary = (
        "The panel does not collapse into consensus. Finance and market lenses lean toward the move, "
        "while operations, people, and risk-oriented lenses keep pressing on the hidden cost of execution."
    )

    persona_lookup = session.personas
    strongest_arguments = [
        ArgumentHighlight(
            persona_name=runtime.persona.name,
            title=_highlight_title(runtime),
            explanation=_highlight_explanation(runtime),
        )
        for runtime in sorted(
            persona_lookup.values(),
            key=lambda item: abs(item.stance) * item.confidence,
            reverse=True,
        )[:3]
    ]

    frame = extract_decision_frame(session.decision_context)
    blind_spots = [
        f"You still tend to under-engage with {tag} perspectives, so this brief keeps that lens visible."
        for tag in session.profile.least_engaged_tags[:2]
    ]
    if not any("operations" in runtime.persona.tags for runtime in session.personas.values()):
        blind_spots.append("No true operator lens made the panel, so execution risk may still be under-modeled.")

    suggested_next_steps = _suggest_next_steps(session.decision_context)

    return DecisionBrief(
        headline=headline,
        landscape_summary=landscape_summary,
        strongest_arguments=strongest_arguments,
        key_uncertainties=frame.unknowns[:3],
        blind_spots=blind_spots,
        suggested_next_steps=suggested_next_steps,
    )


def _highlight_title(runtime: RuntimePersona) -> str:
    if "enterprise" in runtime.persona.tags:
        return "Enterprise readiness is the real wedge"
    if "operations" in runtime.persona.tags or "team" in runtime.persona.tags:
        return "Execution load can quietly kill a good strategy"
    if "psychology" in runtime.persona.tags or "behavior" in runtime.persona.tags:
        return "Behavior change is a bigger bet than the roadmap"
    if "engineering" in runtime.persona.tags:
        return "Hidden complexity sets the real cost curve"
    if "devil" in runtime.persona.tags:
        return "Consensus formed faster than the evidence justified"
    return "The long-term option value matters more than the moment"


def _highlight_explanation(runtime: RuntimePersona) -> str:
    if runtime.stance >= 0.18:
        return f"{runtime.persona.name} kept arguing that the upside is real only if the move becomes concrete and testable."
    if runtime.stance <= -0.18:
        return f"{runtime.persona.name} kept surfacing the downside paths the optimistic case was hand-waving away."
    return f"{runtime.persona.name} stayed in the middle and kept translating the debate into sharper decision criteria."


def _suggest_next_steps(decision: str) -> list[str]:
    tokens = tokenize(decision)
    steps = [
        "Write the two competing theses in one paragraph each and list the assumptions that would falsify them.",
        "Run one bounded experiment that creates new signal inside two weeks instead of debating abstractions longer.",
        "Ask one operator or buyer to react to the plan before you commit the whole team.",
    ]
    if "enterprise" in tokens:
        steps[1] = "Line up 3-5 enterprise buyer interviews and test whether the pain is urgent enough to survive procurement reality."
    if "pivot" in tokens:
        steps[0] = "Define the minimum viable pivot: what changes now, what stays, and what proof would justify going all in."
    return steps


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()
