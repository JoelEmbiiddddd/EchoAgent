from __future__ import annotations

from pathlib import Path

from echoagent.skills.registry import SkillRegistry
from echoagent.skills.router import SkillRouter


def _write_skill(path: Path, content: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(content, encoding="utf-8")


def test_skill_router_topk(tmp_path: Path) -> None:
    web_skill = tmp_path / "web_search"
    _write_skill(
        web_skill,
        """---
name: Web Search
description: Search the web for relevant sources.
tags: [web, search]
allowed_tools: [web_search]
---

Use web_search.
""",
    )
    file_skill = tmp_path / "file_reader"
    _write_skill(
        file_skill,
        """---
name: File Reader
description: Read local files.
tags: [file]
allowed_tools: [read_file]
---

Use read_file.
""",
    )

    registry = SkillRegistry([str(tmp_path)])
    router = SkillRouter(registry, auto_threshold=0.5, suggest_threshold=0.1)

    matches = router.topk("search the web", k=3)
    assert matches
    assert matches[0].skill_id == "web_search"
    assert matches[0].auto_activate is True
