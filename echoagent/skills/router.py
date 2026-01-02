from __future__ import annotations

import re
from typing import Iterable

from pydantic import BaseModel

from echoagent.skills.registry import SkillRegistry
from echoagent.skills.spec import SkillIndexItem


class SkillMatch(BaseModel):
    skill_id: str
    score: float
    reason: str
    auto_activate: bool


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _score_skill(query_tokens: set[str], item: SkillIndexItem) -> tuple[float, str]:
    haystack = " ".join([
        item.name,
        item.description,
        " ".join(item.tags or []),
    ])
    skill_tokens = set(_tokenize(haystack))
    if not query_tokens:
        return 0.0, "no query tokens"
    overlap = sorted(query_tokens & skill_tokens)
    if not overlap:
        return 0.0, "no overlap"
    score = len(overlap) / max(len(query_tokens), 1)
    reason = f"overlap: {', '.join(overlap)}"
    return score, reason


def _sorted_matches(matches: Iterable[SkillMatch]) -> list[SkillMatch]:
    return sorted(matches, key=lambda match: (-match.score, match.skill_id))


class SkillRouter:
    def __init__(
        self,
        registry: SkillRegistry,
        *,
        auto_threshold: float = 0.65,
        suggest_threshold: float = 0.35,
    ) -> None:
        self._registry = registry
        self._auto_threshold = auto_threshold
        self._suggest_threshold = suggest_threshold

    def topk(self, query: str, *, k: int = 5) -> list[SkillMatch]:
        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return []

        matches: list[SkillMatch] = []
        for item in self._registry.list_index():
            score, reason = _score_skill(query_tokens, item)
            if score < self._suggest_threshold:
                continue
            matches.append(
                SkillMatch(
                    skill_id=item.skill_id,
                    score=score,
                    reason=reason,
                    auto_activate=score >= self._auto_threshold,
                )
            )

        ordered = _sorted_matches(matches)
        return ordered[:k]
