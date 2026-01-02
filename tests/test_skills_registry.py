from __future__ import annotations

from pathlib import Path

from echoagent.skills.registry import SkillRegistry


def _write_skill(path: Path, content: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(content, encoding="utf-8")


def test_skill_registry_parses_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "web_search"
    _write_skill(
        skill_dir,
        """---
name: Web Search
description: Search the web for fresh info.
tags: [web, search]
allowed_tools: [web_search]
---

Use web_search to answer queries.
""",
    )

    registry = SkillRegistry([str(tmp_path)])
    index = registry.list_index()
    assert len(index) == 1
    assert index[0].skill_id == "web_search"
    assert index[0].name == "Web Search"
    assert "search" in index[0].description.lower()

    asset = registry.load_full("web_search")
    assert "Use web_search" in asset.markdown
    assert asset.index.allowed_tools == ["web_search"]
