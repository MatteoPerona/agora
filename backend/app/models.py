from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BiasConfig(BaseModel):
    type: str
    strength: Literal["LOW", "MODERATE", "HIGH"]
    description: str


class Persona(BaseModel):
    id: str
    name: str
    creator_id: str
    forked_from: str | None = None
    visibility: Literal["public", "private"]
    summary: str
    identity_anchor: str
    epistemic_style: str
    cognitive_biases: list[BiasConfig]
    argumentative_voice: str
    opinion_change_threshold: Literal["LOW", "MODERATE", "HIGH"]
    tags: list[str]
    avatar_emoji: str
    times_used: int = 0
    effectiveness_score: float = 0.0


class UserReasoningProfile(BaseModel):
    sessions_count: int
    most_engaged_tags: list[str]
    least_engaged_tags: list[str]
    personas_favorited: list[str]
    ignored_perspective_types: list[str]
    override_frequency: float
    avg_rounds_before_ending: float
    position_change_rate: float


class DecisionFrame(BaseModel):
    focus: str
    constraints: list[str]
    stakeholders: list[str]
    unknowns: list[str]


class UploadedDocument(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int
    extraction_status: Literal["ready", "failed"]
    extracted_text_preview: str
    extracted_char_count: int
    created_at: str


class StoredDocument(UploadedDocument):
    storage_path: str
    extracted_text: str
    chunks: list[str] = Field(default_factory=list)


class PersonaStance(BaseModel):
    persona_id: str
    persona_name: str
    avatar_emoji: str
    stance: float
    confidence: float
    label: Literal["for", "against", "undecided"]
    rationale: str


class PanelRecommendation(BaseModel):
    persona: Persona
    reasons: list[str]
    initial_stance: PersonaStance


class PanelRecommendationResponse(BaseModel):
    decision_frame: DecisionFrame
    blind_spot_message: str
    recommendations: list[PanelRecommendation]
    suggested_ids: list[str]
    selection_source: Literal["provider", "fallback", "stub"] = "fallback"
    selection_notice: str | None = None


class ExpandPersonaRequest(BaseModel):
    description: str = Field(min_length=12)


class CreatePersonaRequest(BaseModel):
    name: str
    summary: str
    identity_anchor: str
    epistemic_style: str
    argumentative_voice: str
    tags: list[str]
    opinion_change_threshold: Literal["LOW", "MODERATE", "HIGH"] = "MODERATE"
    avatar_emoji: str = "🧭"
    visibility: Literal["public", "private"] = "private"
    creator_id: str = "local-user"
    cognitive_biases: list[BiasConfig]


class UpdatePersonaRequest(BaseModel):
    summary: str | None = None
    identity_anchor: str | None = None
    epistemic_style: str | None = None
    argumentative_voice: str | None = None
    opinion_change_threshold: Literal["LOW", "MODERATE", "HIGH"] | None = None


class RuntimeLLMConfig(BaseModel):
    provider: str = "stub"
    model: str = "stub"
    selector_model: str | None = None
    summary_model: str | None = None
    base_url: str | None = None
    api_key: str | None = None


class RuntimeLLMConfigResponse(BaseModel):
    provider: str
    model: str
    selector_model: str | None = None
    summary_model: str | None = None
    base_url: str | None = None
    api_key_set: bool
    source: Literal["default", "session"]


class RecommendPanelRequest(BaseModel):
    decision: str = Field(min_length=20)
    panel_size: int = Field(default=5, ge=3, le=8)
    manual_ids: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)


class CreateSessionRequest(BaseModel):
    decision: str = Field(min_length=20)
    persona_ids: list[str] = Field(min_length=3, max_length=8)
    round_goal: int = Field(default=6, ge=3, le=8)
    document_ids: list[str] = Field(default_factory=list)


class UserInterjectionRequest(BaseModel):
    content: str = Field(min_length=3)


class Message(BaseModel):
    id: str
    author_id: str
    author_name: str
    avatar_emoji: str
    role: Literal["persona", "user", "system"]
    round_index: int
    content: str
    stance: float | None = None
    confidence: float | None = None
    cue: str | None = None
    timestamp: str


class TrajectoryPoint(BaseModel):
    round_index: int
    stance: float
    confidence: float


class TrajectorySeries(BaseModel):
    persona_id: str
    persona_name: str
    avatar_emoji: str
    points: list[TrajectoryPoint]


class NetworkEdge(BaseModel):
    source_id: str
    target_id: str


class ArgumentHighlight(BaseModel):
    persona_name: str
    title: str
    explanation: str


class DecisionBrief(BaseModel):
    headline: str
    landscape_summary: str
    strongest_arguments: list[ArgumentHighlight]
    key_uncertainties: list[str]
    blind_spots: list[str]
    suggested_next_steps: list[str]


class SessionSnapshot(BaseModel):
    session_id: str
    decision: str
    current_round: int
    round_goal: int
    status: Literal["idle", "running", "complete"]
    messages: list[Message]
    roster: list[PersonaStance]
    trajectories: list[TrajectorySeries]
    network_edges: list[NetworkEdge]
    brief: DecisionBrief | None = None


class SessionEvent(BaseModel):
    id: int
    event_type: str
    round_index: int | None
    payload: dict[str, Any]
    created_at: str


class ContributionPayload(BaseModel):
    message: str = Field(min_length=1)
    stance: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)


class StanceInterviewPayload(BaseModel):
    stance: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)


class PanelPlannerPayload(BaseModel):
    recommended_ids: list[str]
    rationales: dict[str, list[str]]
    blind_spot_message: str


class DecisionBriefPayload(BaseModel):
    headline: str
    landscape_summary: str
    strongest_arguments: list[ArgumentHighlight]
    key_uncertainties: list[str]
    blind_spots: list[str]
    suggested_next_steps: list[str]
