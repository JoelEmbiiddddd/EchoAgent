from __future__ import annotations

from pathlib import Path
from typing import Mapping, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

_FRONTMATTER_DELIMITER = "---"


class SkillFrontmatter(BaseModel):
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    model_override: Optional[str] = None
    disable_model_invocation: bool = False
    entry: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class SkillIndexItem(BaseModel):
    skill_id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    model_override: Optional[str] = None
    disable_model_invocation: bool = False
    root: str


class SkillAsset(BaseModel):
    index: SkillIndexItem
    markdown: str
    scripts: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)


def parse_skill_markdown(text: str) -> tuple[SkillFrontmatter, str]:
    if not text or not text.strip():
        raise ValueError("Skill markdown is empty")

    sanitized = text.lstrip("\ufeff")
    lines = sanitized.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        raise ValueError("Skill frontmatter is required")

    end_index = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == _FRONTMATTER_DELIMITER:
            end_index = idx
            break
    if end_index is None:
        raise ValueError("Skill frontmatter delimiter is not closed")

    frontmatter_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")

    try:
        data = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid skill frontmatter: {exc}") from exc

    if not isinstance(data, Mapping):
        raise ValueError("Skill frontmatter must be a mapping")

    frontmatter = SkillFrontmatter.model_validate(dict(data))
    return frontmatter, body


def load_skill_markdown(path: Path) -> tuple[SkillFrontmatter, str]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"Skill markdown not found: {path}") from exc
    return parse_skill_markdown(content)
