from __future__ import annotations

import re
import unicodedata

from ..models import BiasConfig, CreatePersonaRequest

KEYWORD_TAGS = {
    "philosophy": ["philosophy", "philosopher", "ethics", "virtue", "wisdom", "meaning", "truth"],
    "psychology": ["psychology", "behavior", "mind", "feeling", "emotion", "habit", "trauma", "joy"],
    "creativity": ["artist", "creative", "writer", "maker", "design", "imagine", "story", "dream"],
    "science": ["science", "scientist", "evidence", "data", "experiment", "research", "logic"],
    "politics": ["politics", "power", "justice", "society", "democracy", "rights", "activist"],
    "culture": ["culture", "anthropology", "tradition", "community", "ritual", "identity", "belong"],
    "spirituality": ["spiritual", "faith", "religion", "mystic", "contemplative", "monk", "prayer"],
    "history": ["history", "historian", "ancient", "past", "archive", "memory", "century"],
    "art": ["art", "poet", "musician", "painter", "sculptor", "theatre", "performer"],
    "ethics": ["moral", "ethics", "right", "wrong", "ought", "duty", "care", "harm"],
}


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return cleaned or "custom-persona"


def expand_natural_language_persona(description: str) -> CreatePersonaRequest:
    lowered = description.lower()
    tags = [
        tag
        for tag, triggers in KEYWORD_TAGS.items()
        if any(trigger in lowered for trigger in triggers)
    ]
    if not tags:
        tags = ["philosophy", "culture"]

    name = _derive_name(description)
    summary = _derive_summary(description)
    threshold = _infer_threshold(lowered)

    biases = [
        BiasConfig(
            type="narrative bias",
            strength="MODERATE",
            description="A compelling story moves them more than a careful argument ever will.",
        ),
        BiasConfig(
            type="lived-experience bias",
            strength="HIGH" if threshold == "HIGH" else "MODERATE",
            description="They trust what they've personally felt or seen over what they've only read.",
        ),
        BiasConfig(
            type="optimism bias",
            strength="MODERATE",
            description="Even when being critical, there's a flicker of hope they can't quite extinguish.",
        ),
    ]

    return CreatePersonaRequest(
        name=name,
        summary=summary,
        identity_anchor=f"You are {name}. You carry the world described here inside you: {description.strip()}",
        epistemic_style=_derive_style(description, tags),
        argumentative_voice=_derive_voice(description, tags),
        tags=tags,
        opinion_change_threshold=threshold,
        avatar_emoji="",
        cognitive_biases=biases,
    )


def _derive_name(description: str) -> str:
    match = re.search(r"(?:a|an)\s+([a-z][a-z\s-]{4,40})", description.lower())
    if match:
        phrase = " ".join(word.capitalize() for word in match.group(1).split()[:4])
        return f"The {phrase}"
    return "The New Voice"


def _derive_summary(description: str) -> str:
    trimmed = description.strip().rstrip(".")
    if len(trimmed) <= 100:
        return trimmed[0].upper() + trimmed[1:] + "."
    return trimmed[:97].rstrip() + "..."


def _derive_style(description: str, tags: list[str]) -> str:
    if "philosophy" in tags:
        return "You chase the question underneath the question — the assumption everyone else walked past."
    if "creativity" in tags:
        return "You think in images and metaphors, finding the angle no one was looking at."
    if "science" in tags:
        return "You want to know what would change your mind, and you ask that of everyone else too."
    if "psychology" in tags:
        return "You're always listening for what's not being said — the feeling underneath the argument."
    if "history" in tags:
        return "You reach for the long view, finding precedents and patterns that repeat across centuries."
    if "spirituality" in tags:
        return "You look for what endures when everything external is stripped away."
    return "You search for the real thing underneath the surface argument and follow it wherever it leads."


def _derive_voice(description: str, tags: list[str]) -> str:
    if "cynical" in description.lower() or "skeptic" in description.lower():
        return "Dry, a little mischievous, fond of the question that makes everyone pause."
    if "creativity" in tags or "art" in tags:
        return "Playful and associative — you'll take a surprising detour to arrive at something true."
    if "spirituality" in tags:
        return "Calm and unhurried. You speak like you're not in a rush to be right."
    if "psychology" in tags:
        return "Warm and perceptive. You reflect things back to people in ways they didn't expect."
    return "Curious, direct, and a little unpredictable — you say the thing others were circling around."


def _infer_threshold(lowered: str) -> str:
    if any(word in lowered for word in ["stubborn", "scarred", "burned", "cynical", "committed", "devout"]):
        return "HIGH"
    if any(word in lowered for word in ["curious", "open", "wandering", "searching", "questioning"]):
        return "LOW"
    return "MODERATE"
