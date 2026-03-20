from __future__ import annotations

import json
import os
import re

import httpx

from ..models import (
    PanelRecommendation,
    PanelRecommendationResponse,
    Persona,
    StoredDocument,
    UserReasoningProfile,
)
from .documents import build_document_context
from .panel import build_decision_context, estimate_initial_stance, recommend_panel

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"


async def select_panel(
    *,
    decision: str,
    documents: list[StoredDocument],
    personas: list[Persona],
    profile: UserReasoningProfile,
    panel_size: int,
    manual_ids: list[str],
) -> PanelRecommendationResponse:
    fallback = recommend_panel(
        decision=decision,
        personas=personas,
        profile=profile,
        panel_size=panel_size,
        manual_ids=manual_ids,
        documents=documents,
    )

    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    if not api_key:
        fallback.selection_notice = "ANTHROPIC_API_KEY is not set, so persona preselection is using the local fallback recommender."
        return fallback

    try:
        llm_result = await _call_anthropic_selector(
            decision=decision,
            documents=documents,
            personas=personas,
            profile=profile,
            panel_size=panel_size,
            manual_ids=manual_ids,
            api_key=api_key,
            model=model,
        )
    except Exception:
        fallback.selection_notice = "Anthropic preselection failed, so the local fallback recommender was used instead."
        return fallback

    selected_map = {recommendation.persona.id: recommendation for recommendation in fallback.recommendations}
    merged_ids = _merge_ids(manual_ids, llm_result.get("recommended_ids", []), fallback.suggested_ids, panel_size)

    recommendations: list[PanelRecommendation] = []
    for persona_id in merged_ids:
        persona = next((candidate for candidate in personas if candidate.id == persona_id), None)
        if persona is None:
            continue

        stance = estimate_initial_stance(
            persona,
            build_decision_context(decision, documents),
        )
        reasons = _reason_list_for_persona(persona_id, llm_result, selected_map)
        recommendations.append(
            PanelRecommendation(
                persona=persona,
                reasons=reasons,
                initial_stance=stance,
            )
        )

    if not recommendations:
        fallback.selection_notice = "Anthropic returned an unusable response, so the local fallback recommender was used instead."
        return fallback

    return PanelRecommendationResponse(
        decision_frame=fallback.decision_frame,
        blind_spot_message=llm_result.get("blind_spot_message") or fallback.blind_spot_message,
        recommendations=recommendations,
        suggested_ids=[recommendation.persona.id for recommendation in recommendations],
        selection_source="anthropic",
        selection_notice=None,
    )


async def _call_anthropic_selector(
    *,
    decision: str,
    documents: list[StoredDocument],
    personas: list[Persona],
    profile: UserReasoningProfile,
    panel_size: int,
    manual_ids: list[str],
    api_key: str,
    model: str,
) -> dict:
    persona_catalog = [
        {
            "id": persona.id,
            "name": persona.name,
            "summary": persona.summary,
            "tags": persona.tags,
            "visibility": persona.visibility,
        }
        for persona in personas
    ]
    document_context = build_document_context(documents)

    prompt = (
        "You are selecting a panel of deliberation personas.\n"
        f"User decision:\n{decision}\n\n"
        f"Least-engaged tags to amplify: {', '.join(profile.least_engaged_tags)}\n"
        f"Already manually selected ids: {manual_ids}\n"
        f"Desired panel size: {panel_size}\n\n"
        f"Supporting documents:\n{document_context or 'No documents attached.'}\n\n"
        "Persona catalog:\n"
        f"{json.dumps(persona_catalog, ensure_ascii=True)}\n\n"
        "Return strict JSON with this shape:\n"
        '{'
        '"recommended_ids": ["persona-id"], '
        '"rationales": {"persona-id": ["reason 1", "reason 2"]}, '
        '"blind_spot_message": "one sentence"'
        '}\n'
        "Rules: choose a diverse panel, include blind-spot coverage, respect manual ids, and never invent ids."
    )

    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 900,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()

    payload = response.json()
    text_blocks = [
        block.get("text", "")
        for block in payload.get("content", [])
        if block.get("type") == "text"
    ]
    return _extract_json_payload("\n".join(text_blocks))


def _extract_json_payload(raw_text: str) -> dict:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in Anthropic response.")
    return json.loads(match.group(0))


def _merge_ids(manual_ids: list[str], llm_ids: list[str], fallback_ids: list[str], panel_size: int) -> list[str]:
    merged: list[str] = []
    for candidate_list in [manual_ids, llm_ids, fallback_ids]:
        for persona_id in candidate_list:
            if persona_id not in merged:
                merged.append(persona_id)
            if len(merged) >= panel_size:
                return merged[:panel_size]
    return merged[:panel_size]


def _reason_list_for_persona(
    persona_id: str,
    llm_result: dict,
    fallback_map: dict[str, PanelRecommendation],
) -> list[str]:
    llm_rationales = llm_result.get("rationales", {})
    candidate = llm_rationales.get(persona_id)
    if isinstance(candidate, list) and candidate:
        return [str(item) for item in candidate]
    if isinstance(candidate, str):
        return [candidate]
    if persona_id in fallback_map:
        return fallback_map[persona_id].reasons
    return ["Selected to add a distinct perspective to the panel."]
