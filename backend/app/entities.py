from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class PersonaEntity(Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    creator_id: Mapped[str] = mapped_column(String, nullable=False)
    forked_from: Mapped[str | None] = mapped_column(String, nullable=True)
    visibility: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    identity_anchor: Mapped[str] = mapped_column(Text, nullable=False)
    epistemic_style: Mapped[str] = mapped_column(Text, nullable=False)
    cognitive_biases: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    argumentative_voice: Mapped[str] = mapped_column(Text, nullable=False)
    opinion_change_threshold: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    avatar_emoji: Mapped[str] = mapped_column(String, nullable=False)
    times_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effectiveness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class UserProfileEntity(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    sessions_count: Mapped[int] = mapped_column(Integer, nullable=False)
    most_engaged_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    least_engaged_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    personas_favorited: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    ignored_perspective_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    override_frequency: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_rounds_before_ending: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_change_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class DocumentEntity(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_status: Mapped[str] = mapped_column(String, nullable=False)
    extracted_text_preview: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    chunks: Mapped[list["DocumentChunkEntity"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunkEntity.chunk_index",
    )


class DocumentChunkEntity(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped[DocumentEntity] = relationship(back_populates="chunks")


class SimulationEntity(Base):
    __tablename__ = "simulations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    document_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    document_names: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    round_goal: Mapped[int] = mapped_column(Integer, nullable=False)
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    oasis_db_path: Mapped[str] = mapped_column(Text, nullable=False)
    oasis_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_frame: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    participants: Mapped[list["SimulationParticipantEntity"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="SimulationParticipantEntity.display_order",
    )
    rounds: Mapped[list["SimulationRoundEntity"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="SimulationRoundEntity.round_index",
    )
    messages: Mapped[list["SimulationMessageEntity"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="SimulationMessageEntity.timestamp",
    )
    metrics: Mapped[list["SimulationMetricEntity"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="SimulationMetricEntity.id",
    )
    artifacts: Mapped[list["SimulationArtifactEntity"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="SimulationArtifactEntity.id",
    )
    events: Mapped[list["SimulationEventEntity"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="SimulationEventEntity.id",
    )


class SimulationParticipantEntity(Base):
    __tablename__ = "simulation_participants"
    __table_args__ = (
        UniqueConstraint("simulation_id", "persona_id", name="uq_simulation_persona"),
        UniqueConstraint("simulation_id", "agent_id", name="uq_simulation_agent"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False)
    persona_id: Mapped[str] = mapped_column(ForeignKey("personas.id"), nullable=False)
    agent_id: Mapped[int] = mapped_column(Integer, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    current_stance: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    simulation: Mapped[SimulationEntity] = relationship(back_populates="participants")
    persona: Mapped[PersonaEntity] = relationship()


class SimulationRoundEntity(Base):
    __tablename__ = "simulation_rounds"
    __table_args__ = (UniqueConstraint("simulation_id", "round_index", name="uq_simulation_round"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False)
    round_index: Mapped[int] = mapped_column(Integer, nullable=False)
    cue: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    simulation: Mapped[SimulationEntity] = relationship(back_populates="rounds")


class SimulationMessageEntity(Base):
    __tablename__ = "simulation_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[str] = mapped_column(String, nullable=False)
    author_name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_emoji: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    round_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    stance: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    cue: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    simulation: Mapped[SimulationEntity] = relationship(back_populates="messages")


class SimulationMetricEntity(Base):
    __tablename__ = "simulation_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False)
    persona_id: Mapped[str | None] = mapped_column(String, nullable=True)
    round_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metric_name: Mapped[str] = mapped_column(String, nullable=False)
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    json_value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    simulation: Mapped[SimulationEntity] = relationship(back_populates="metrics")


class SimulationArtifactEntity(Base):
    __tablename__ = "simulation_artifacts"
    __table_args__ = (UniqueConstraint("simulation_id", "artifact_type", name="uq_simulation_artifact_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    simulation: Mapped[SimulationEntity] = relationship(back_populates="artifacts")


class SimulationEventEntity(Base):
    __tablename__ = "simulation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    round_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    simulation: Mapped[SimulationEntity] = relationship(back_populates="events")
