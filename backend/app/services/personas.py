from __future__ import annotations

import re
import unicodedata

from ..models import BiasConfig, CreatePersonaRequest

KEYWORD_TAGS = {
    "operations": ["operations", "operator", "process", "workflow", "delivery", "burned"],
    "psychology": ["behavior", "psychology", "incentive", "habit", "adoption"],
    "people": ["people", "culture", "hr", "manager", "team", "trust"],
    "finance": ["finance", "investor", "fund", "runway", "venture", "series"],
    "engineering": ["engineer", "technical", "system", "architecture", "code", "security"],
    "risk": ["risk", "compliance", "security", "legal", "unsafe"],
    "growth": ["growth", "marketing", "brand", "distribution", "awareness"],
    "product": ["product", "pm", "ship", "launch", "feature", "customer"],
    "founder": ["founder", "startup", "vision", "builder", "bootstrap"],
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
        tags = ["strategy", "analysis"]

    name = _derive_name(description)
    summary = _derive_summary(description)
    threshold = _infer_threshold(lowered)
    avatar = _infer_avatar(tags)

    biases = [
        BiasConfig(
            type="confirmation bias",
            strength="MODERATE" if "skeptic" not in lowered else "HIGH",
            description="You instinctively favor evidence that validates your frame.",
        ),
        BiasConfig(
            type="commitment bias",
            strength="HIGH" if threshold == "HIGH" else "MODERATE",
            description="Once you state a position, changing it feels expensive.",
        ),
        BiasConfig(
            type="availability bias",
            strength="MODERATE",
            description="Recent examples and vivid stories shape your judgment.",
        ),
    ]

    return CreatePersonaRequest(
        name=name,
        summary=summary,
        identity_anchor=f"You are {name}, a decision-maker shaped by the lived experience described here: {description.strip()}",
        epistemic_style=_derive_style(description, tags),
        argumentative_voice=_derive_voice(description, tags),
        tags=tags,
        opinion_change_threshold=threshold,
        avatar_emoji=avatar,
        cognitive_biases=biases,
    )


def _derive_name(description: str) -> str:
    match = re.search(r"(?:a|an)\s+([a-z][a-z\s-]{4,40})", description.lower())
    if match:
        phrase = " ".join(word.capitalize() for word in match.group(1).split()[:4])
        return f"The {phrase}"
    return "The New Perspective"


def _derive_summary(description: str) -> str:
    trimmed = description.strip().rstrip(".")
    if len(trimmed) <= 100:
        return trimmed[0].upper() + trimmed[1:] + "."
    return trimmed[:97].rstrip() + "..."


def _derive_style(description: str, tags: list[str]) -> str:
    if "finance" in tags:
        return "You convert qualitative claims into economic tradeoffs, downside exposure, and return shape."
    if "operations" in tags:
        return "You look for coordination load, execution drag, and whether the team can absorb the move."
    if "psychology" in tags:
        return "You focus on incentives, defaults, and the gap between what people say and what they actually do."
    if "engineering" in tags:
        return "You reduce the debate to constraints, interfaces, and the assumptions that can be tested quickly."
    return "You search for the hidden frame underneath the obvious argument and explain your reasoning clearly."


def _derive_voice(description: str, tags: list[str]) -> str:
    if "cynical" in description.lower() or "skeptic" in description.lower():
        return "Skeptical, concise, and unsentimental. You poke at the weakest assumption first."
    if "operations" in tags:
        return "Grounded and practical. You sound like someone who has had to carry the plan after the meeting ended."
    if "psychology" in tags:
        return "Curious and pattern-aware. You reframe behavior before offering advice."
    return "Distinct, clear, and willing to disagree without hedging."


def _infer_threshold(lowered: str) -> str:
    if any(word in lowered for word in ["stubborn", "scarred", "burned", "cynical"]):
        return "HIGH"
    if any(word in lowered for word in ["curious", "adaptive", "experimental"]):
        return "LOW"
    return "MODERATE"


def _infer_avatar(tags: list[str]) -> str:
    if "finance" in tags:
        return "💼"
    if "operations" in tags:
        return "🧰"
    if "psychology" in tags:
        return "🧭"
    if "engineering" in tags:
        return "🛠️"
    if "people" in tags:
        return "🌱"
    return "🪞"

