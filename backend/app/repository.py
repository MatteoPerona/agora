from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from .entities import (
    DocumentChunkEntity,
    DocumentEntity,
    PersonaEntity,
    SimulationArtifactEntity,
    SimulationEntity,
    SimulationEventEntity,
    SimulationMessageEntity,
    SimulationMetricEntity,
    SimulationParticipantEntity,
    SimulationRoundEntity,
    UserProfileEntity,
)
from .models import (
    CreatePersonaRequest,
    DecisionBrief,
    Message,
    Persona,
    StoredDocument,
    UploadedDocument,
    UserReasoningProfile,
)


def now_utc() -> datetime:
    return datetime.now(UTC)


def persona_from_entity(entity: PersonaEntity) -> Persona:
    return Persona(
        id=entity.id,
        name=entity.name,
        creator_id=entity.creator_id,
        forked_from=entity.forked_from,
        visibility=entity.visibility,
        summary=entity.summary,
        identity_anchor=entity.identity_anchor,
        epistemic_style=entity.epistemic_style,
        cognitive_biases=entity.cognitive_biases,
        argumentative_voice=entity.argumentative_voice,
        opinion_change_threshold=entity.opinion_change_threshold,
        tags=entity.tags,
        avatar_emoji=entity.avatar_emoji,
        times_used=entity.times_used,
        effectiveness_score=entity.effectiveness_score,
    )


def profile_from_entity(entity: UserProfileEntity) -> UserReasoningProfile:
    return UserReasoningProfile(
        sessions_count=entity.sessions_count,
        most_engaged_tags=entity.most_engaged_tags,
        least_engaged_tags=entity.least_engaged_tags,
        personas_favorited=entity.personas_favorited,
        ignored_perspective_types=entity.ignored_perspective_types,
        override_frequency=entity.override_frequency,
        avg_rounds_before_ending=entity.avg_rounds_before_ending,
        position_change_rate=entity.position_change_rate,
    )


def stored_document_from_entity(entity: DocumentEntity) -> StoredDocument:
    return StoredDocument(
        id=entity.id,
        filename=entity.filename,
        mime_type=entity.mime_type,
        size_bytes=entity.size_bytes,
        extraction_status=entity.extraction_status,
        extracted_text_preview=entity.extracted_text_preview,
        extracted_char_count=entity.extracted_char_count,
        created_at=entity.created_at.isoformat(),
        storage_path=entity.storage_path,
        extracted_text=entity.extracted_text,
        chunks=[chunk.content for chunk in entity.chunks],
    )


def uploaded_document_from_entity(entity: DocumentEntity) -> UploadedDocument:
    return UploadedDocument(**stored_document_from_entity(entity).model_dump(exclude={"storage_path", "extracted_text", "chunks"}))


def message_from_entity(entity: SimulationMessageEntity) -> Message:
    return Message(
        id=entity.id,
        author_id=entity.author_id,
        author_name=entity.author_name,
        avatar_emoji=entity.avatar_emoji,
        role=entity.role,
        round_index=entity.round_index,
        content=entity.content,
        stance=entity.stance,
        confidence=entity.confidence,
        cue=entity.cue,
        timestamp=entity.timestamp.isoformat(),
    )


class AppRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_personas(self) -> list[Persona]:
        records = self.session.scalars(select(PersonaEntity).order_by(PersonaEntity.visibility.desc(), PersonaEntity.times_used.desc(), PersonaEntity.name.asc())).all()
        return [persona_from_entity(record) for record in records]

    def get_persona(self, persona_id: str) -> Persona | None:
        record = self.session.get(PersonaEntity, persona_id)
        return persona_from_entity(record) if record else None

    def get_persona_entities(self, persona_ids: Iterable[str]) -> list[PersonaEntity]:
        ids = list(persona_ids)
        if not ids:
            return []
        records = self.session.scalars(select(PersonaEntity).where(PersonaEntity.id.in_(ids))).all()
        mapping = {record.id: record for record in records}
        return [mapping[persona_id] for persona_id in ids if persona_id in mapping]

    def create_persona(self, payload: CreatePersonaRequest, persona_id: str) -> Persona:
        record = PersonaEntity(
            id=persona_id,
            name=payload.name,
            creator_id=payload.creator_id,
            forked_from=None,
            visibility=payload.visibility,
            summary=payload.summary,
            identity_anchor=payload.identity_anchor,
            epistemic_style=payload.epistemic_style,
            cognitive_biases=[bias.model_dump() for bias in payload.cognitive_biases],
            argumentative_voice=payload.argumentative_voice,
            opinion_change_threshold=payload.opinion_change_threshold,
            tags=payload.tags,
            avatar_emoji=payload.avatar_emoji,
            times_used=0,
            effectiveness_score=0.0,
        )
        self.session.add(record)
        self.session.flush()
        return persona_from_entity(record)

    def update_persona(self, persona_id: str, updates: dict) -> Persona | None:
        record = self.session.get(PersonaEntity, persona_id)
        if record is None:
            return None
        for key, value in updates.items():
            if value is not None and hasattr(record, key):
                setattr(record, key, value)
        self.session.flush()
        return persona_from_entity(record)

    def increment_persona_usage(self, persona_ids: list[str]) -> None:
        for record in self.get_persona_entities(persona_ids):
            record.times_used += 1

    def get_profile(self) -> UserReasoningProfile:
        record = self.session.get(UserProfileEntity, 1)
        if record is None:
            raise ValueError("User profile is not initialized.")
        return profile_from_entity(record)

    def update_profile(self, profile: UserReasoningProfile) -> None:
        record = self.session.get(UserProfileEntity, 1)
        if record is None:
            raise ValueError("User profile is not initialized.")
        record.sessions_count = profile.sessions_count
        record.most_engaged_tags = profile.most_engaged_tags
        record.least_engaged_tags = profile.least_engaged_tags
        record.personas_favorited = profile.personas_favorited
        record.ignored_perspective_types = profile.ignored_perspective_types
        record.override_frequency = profile.override_frequency
        record.avg_rounds_before_ending = profile.avg_rounds_before_ending
        record.position_change_rate = profile.position_change_rate

    def create_document(
        self,
        *,
        document_id: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
        extraction_status: str,
        extracted_text_preview: str,
        extracted_char_count: int,
        extracted_text: str,
        storage_path: str,
        chunks: list[str],
    ) -> StoredDocument:
        record = DocumentEntity(
            id=document_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            extraction_status=extraction_status,
            extracted_text_preview=extracted_text_preview,
            extracted_char_count=extracted_char_count,
            extracted_text=extracted_text,
            storage_path=storage_path,
            chunks=[DocumentChunkEntity(chunk_index=index, content=chunk) for index, chunk in enumerate(chunks)],
        )
        self.session.add(record)
        self.session.flush()
        self.session.refresh(record)
        return stored_document_from_entity(record)

    def get_document_entity(self, document_id: str) -> DocumentEntity | None:
        return self.session.scalar(
            select(DocumentEntity).options(selectinload(DocumentEntity.chunks)).where(DocumentEntity.id == document_id)
        )

    def get_document(self, document_id: str) -> StoredDocument | None:
        record = self.get_document_entity(document_id)
        return stored_document_from_entity(record) if record else None

    def get_documents(self, document_ids: list[str]) -> list[StoredDocument]:
        entities = [
            entity
            for entity in (self.get_document_entity(document_id) for document_id in document_ids)
            if entity is not None
        ]
        return [stored_document_from_entity(entity) for entity in entities]

    def delete_persona(self, persona_id: str) -> Persona | None:
        record = self.session.get(PersonaEntity, persona_id)
        if record is None:
            return None
        payload = persona_from_entity(record)
        self.session.delete(record)
        return payload

    def delete_document(self, document_id: str) -> UploadedDocument | None:
        record = self.get_document_entity(document_id)
        if record is None:
            return None
        payload = uploaded_document_from_entity(record)
        self.session.delete(record)
        return payload

    def create_simulation(
        self,
        *,
        simulation_id: str,
        decision: str,
        document_ids: list[str],
        document_names: list[str],
        round_goal: int,
        oasis_db_path: str,
        decision_frame: dict[str, Any],
        persona_entities: list[PersonaEntity],
    ) -> SimulationEntity:
        simulation = SimulationEntity(
            id=simulation_id,
            decision=decision,
            document_ids=document_ids,
            document_names=document_names,
            round_goal=round_goal,
            current_round=0,
            status="running",
            oasis_db_path=oasis_db_path,
            decision_frame=decision_frame,
        )
        self.session.add(simulation)
        self.session.flush()

        for index, persona in enumerate(persona_entities, start=1):
            self.session.add(
                SimulationParticipantEntity(
                    simulation_id=simulation_id,
                    persona_id=persona.id,
                    agent_id=index,
                    display_order=index - 1,
                )
            )

        self.add_event(simulation_id, "session_created", {"decision": decision}, round_index=0)
        self.session.flush()
        return self.get_simulation(simulation_id)

    def get_simulation(self, simulation_id: str) -> SimulationEntity:
        self.session.expire_all()
        record = self.session.scalar(
            select(SimulationEntity)
            .options(
                selectinload(SimulationEntity.participants).selectinload(SimulationParticipantEntity.persona),
                selectinload(SimulationEntity.messages),
                selectinload(SimulationEntity.rounds),
                selectinload(SimulationEntity.metrics),
                selectinload(SimulationEntity.artifacts),
                selectinload(SimulationEntity.events),
            )
            .where(SimulationEntity.id == simulation_id)
        )
        if record is None:
            raise ValueError("Simulation not found.")
        return record

    def set_group_id(self, simulation_id: str, group_id: int) -> None:
        simulation = self.get_simulation(simulation_id)
        simulation.oasis_group_id = group_id

    def create_round(self, simulation_id: str, round_index: int, cue: str) -> SimulationRoundEntity:
        round_record = SimulationRoundEntity(
            simulation_id=simulation_id,
            round_index=round_index,
            cue=cue,
            status="running",
        )
        self.session.add(round_record)
        self.add_event(simulation_id, "round_started", {"cue": cue}, round_index=round_index)
        self.session.flush()
        return round_record

    def complete_round(self, simulation_id: str, round_index: int) -> None:
        round_record = self.session.scalar(
            select(SimulationRoundEntity).where(
                SimulationRoundEntity.simulation_id == simulation_id,
                SimulationRoundEntity.round_index == round_index,
            )
        )
        if round_record is None:
            raise ValueError("Round not found.")
        round_record.status = "complete"
        round_record.completed_at = now_utc()

        simulation = self.get_simulation(simulation_id)
        simulation.current_round = max(simulation.current_round, round_index)
        self.session.flush()

    def add_message(
        self,
        *,
        simulation_id: str,
        author_id: str,
        author_name: str,
        avatar_emoji: str,
        role: str,
        round_index: int,
        content: str,
        cue: str | None = None,
        stance: float | None = None,
        confidence: float | None = None,
        message_id: str | None = None,
    ) -> SimulationMessageEntity:
        record = SimulationMessageEntity(
            id=message_id or str(uuid4()),
            simulation_id=simulation_id,
            author_id=author_id,
            author_name=author_name,
            avatar_emoji=avatar_emoji,
            role=role,
            round_index=round_index,
            content=content,
            cue=cue,
            stance=stance,
            confidence=confidence,
        )
        self.session.add(record)
        self.add_event(
            simulation_id,
            "message_added",
            {
                "message_id": record.id,
                "author_id": author_id,
                "role": role,
                "content": content,
            },
            round_index=round_index,
        )
        self.session.flush()
        return record

    def update_message_metrics(
        self,
        *,
        simulation_id: str,
        author_id: str,
        round_index: int,
        stance: float,
        confidence: float,
    ) -> None:
        record = self.session.scalar(
            select(SimulationMessageEntity)
            .where(
                SimulationMessageEntity.simulation_id == simulation_id,
                SimulationMessageEntity.author_id == author_id,
                SimulationMessageEntity.round_index == round_index,
                SimulationMessageEntity.role == "persona",
            )
            .order_by(SimulationMessageEntity.timestamp.desc())
        )
        if record is None:
            return
        record.stance = stance
        record.confidence = confidence

    def set_participant_state(
        self,
        *,
        simulation_id: str,
        persona_id: str,
        stance: float,
        confidence: float,
        rationale: str,
        round_index: int,
    ) -> None:
        participant = self.session.scalar(
            select(SimulationParticipantEntity).where(
                SimulationParticipantEntity.simulation_id == simulation_id,
                SimulationParticipantEntity.persona_id == persona_id,
            )
        )
        if participant is None:
            raise ValueError("Simulation participant not found.")

        participant.current_stance = stance
        participant.current_confidence = confidence
        participant.last_rationale = rationale

        self.session.add(
            SimulationMetricEntity(
                simulation_id=simulation_id,
                persona_id=persona_id,
                round_index=round_index,
                metric_name="trajectory_point",
                numeric_value=stance,
                json_value={"confidence": confidence, "rationale": rationale},
            )
        )

    def get_trajectory_metrics(self, simulation_id: str) -> list[SimulationMetricEntity]:
        return self.session.scalars(
            select(SimulationMetricEntity)
            .where(
                SimulationMetricEntity.simulation_id == simulation_id,
                SimulationMetricEntity.metric_name == "trajectory_point",
            )
            .order_by(SimulationMetricEntity.persona_id.asc(), SimulationMetricEntity.round_index.asc(), SimulationMetricEntity.id.asc())
        ).all()

    def set_artifact(self, simulation_id: str, artifact_type: str, payload_json: dict[str, Any]) -> SimulationArtifactEntity:
        artifact = self.session.scalar(
            select(SimulationArtifactEntity).where(
                SimulationArtifactEntity.simulation_id == simulation_id,
                SimulationArtifactEntity.artifact_type == artifact_type,
            )
        )
        if artifact is None:
            artifact = SimulationArtifactEntity(
                simulation_id=simulation_id,
                artifact_type=artifact_type,
                payload_json=payload_json,
            )
            self.session.add(artifact)
        else:
            artifact.payload_json = payload_json
        self.add_event(simulation_id, "artifact_updated", {"artifact_type": artifact_type}, round_index=None)
        self.session.flush()
        return artifact

    def get_brief(self, simulation_id: str) -> DecisionBrief | None:
        artifact = self.session.scalar(
            select(SimulationArtifactEntity).where(
                SimulationArtifactEntity.simulation_id == simulation_id,
                SimulationArtifactEntity.artifact_type == "brief",
            )
        )
        if artifact is None:
            return None
        return DecisionBrief(**artifact.payload_json)

    def add_event(
        self,
        simulation_id: str,
        event_type: str,
        payload_json: dict[str, Any],
        round_index: int | None,
    ) -> SimulationEventEntity:
        event = SimulationEventEntity(
            simulation_id=simulation_id,
            event_type=event_type,
            payload_json=payload_json,
            round_index=round_index,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def list_events_after(self, simulation_id: str, event_id: int | None = None) -> list[SimulationEventEntity]:
        statement = select(SimulationEventEntity).where(SimulationEventEntity.simulation_id == simulation_id)
        if event_id is not None:
            statement = statement.where(SimulationEventEntity.id > event_id)
        return self.session.scalars(statement.order_by(SimulationEventEntity.id.asc())).all()

    def add_pending_interjection(self, simulation_id: str, content: str, round_index: int) -> SimulationEventEntity:
        return self.add_event(
            simulation_id,
            "pending_interjection",
            {"content": content, "processed": False},
            round_index=round_index,
        )

    def get_pending_interjections(self, simulation_id: str) -> list[SimulationEventEntity]:
        events = self.session.scalars(
            select(SimulationEventEntity)
            .where(
                SimulationEventEntity.simulation_id == simulation_id,
                SimulationEventEntity.event_type == "pending_interjection",
            )
            .order_by(SimulationEventEntity.id.asc())
        ).all()
        return [event for event in events if not bool(event.payload_json.get("processed"))]

    def mark_interjection_processed(self, event_id: int) -> None:
        event = self.session.get(SimulationEventEntity, event_id)
        if event is None:
            return
        payload = dict(event.payload_json)
        payload["processed"] = True
        event.payload_json = payload

    def mark_simulation_complete(self, simulation_id: str) -> None:
        simulation = self.get_simulation(simulation_id)
        simulation.status = "complete"
        simulation.ended_at = now_utc()
        self.add_event(simulation_id, "simulation_completed", {}, round_index=simulation.current_round)

    def purge_simulation_messages(self, simulation_id: str) -> None:
        self.session.execute(delete(SimulationMessageEntity).where(SimulationMessageEntity.simulation_id == simulation_id))
