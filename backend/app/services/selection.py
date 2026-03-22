from __future__ import annotations

from ..models import (
    PanelRecommendation,
    PanelRecommendationResponse,
    PanelPlannerPayload,
    Persona,
    StoredDocument,
    UserReasoningProfile,
)
from ..simulation.prompts import build_panel_selection_prompt
from ..simulation.provider import SimulationProviderFactory, StructuredLLMClient
from .documents import build_document_context
from .panel import build_decision_context, estimate_initial_stance, recommend_panel


async def select_panel(
    *,
    decision: str,
    documents: list[StoredDocument],
    personas: list[Persona],
    profile: UserReasoningProfile,
    panel_size: int,
    manual_ids: list[str],
    provider_factory: SimulationProviderFactory,
) -> PanelRecommendationResponse:
    fallback = recommend_panel(
        decision=decision,
        personas=personas,
        profile=profile,
        panel_size=panel_size,
        manual_ids=manual_ids,
        documents=documents,
    )

    backend = provider_factory.create_selector_backend()
    client = StructuredLLMClient(backend)
    payload = await client.generate_json(
        system_prompt="You select a diverse deliberation panel for a structured decision room.",
        user_prompt=build_panel_selection_prompt(
            decision=decision,
            panel_size=panel_size,
            manual_ids=manual_ids,
            least_engaged_tags=profile.least_engaged_tags,
            persona_catalog=[
                {
                    "id": persona.id,
                    "name": persona.name,
                    "summary": persona.summary,
                    "tags": persona.tags,
                    "visibility": persona.visibility,
                }
                for persona in personas
            ],
            document_context=build_document_context(documents),
        ),
        schema=PanelPlannerPayload,
    )

    selected_map = {recommendation.persona.id: recommendation for recommendation in fallback.recommendations}
    merged_ids = _merge_ids(manual_ids, payload.recommended_ids, fallback.suggested_ids, panel_size)

    recommendations: list[PanelRecommendation] = []
    for persona_id in merged_ids:
        persona = next((candidate for candidate in personas if candidate.id == persona_id), None)
        if persona is None:
            continue
        recommendations.append(
            PanelRecommendation(
                persona=persona,
                reasons=payload.rationales.get(persona_id) or selected_map.get(persona_id, PanelRecommendation(persona=persona, reasons=["Selected to add a distinct perspective to the panel."], initial_stance=estimate_initial_stance(persona, build_decision_context(decision, documents)))).reasons,
                initial_stance=estimate_initial_stance(persona, build_decision_context(decision, documents)),
            )
        )

    if not recommendations:
        raise RuntimeError("AI panel recommendation returned no usable personas.")

    return PanelRecommendationResponse(
        decision_frame=fallback.decision_frame,
        blind_spot_message=payload.blind_spot_message or fallback.blind_spot_message,
        recommendations=recommendations,
        suggested_ids=[recommendation.persona.id for recommendation in recommendations],
        selection_source="provider",
        selection_notice=None,
    )


def _merge_ids(manual_ids: list[str], llm_ids: list[str], fallback_ids: list[str], panel_size: int) -> list[str]:
    merged: list[str] = []
    for candidate_list in [manual_ids, llm_ids, fallback_ids]:
        for persona_id in candidate_list:
            if persona_id not in merged:
                merged.append(persona_id)
            if len(merged) >= panel_size:
                return merged[:panel_size]
    return merged[:panel_size]
