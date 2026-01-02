from __future__ import annotations

from pathlib import Path
from typing import Optional

from echoagent.skills.spec import SkillAsset, SkillFrontmatter, SkillIndexItem, load_skill_markdown


class SkillRegistry:
    def __init__(self, roots: list[str]) -> None:
        self._roots = [Path(root).expanduser() for root in roots]
        self._index_cache: Optional[list[SkillIndexItem]] = None
        self._index_by_id: dict[str, SkillIndexItem] = {}
        self._root_by_id: dict[str, Path] = {}

    def list_index(self) -> list[SkillIndexItem]:
        if self._index_cache is None:
            self._index_cache = self._scan_index()
        return list(self._index_cache)

    def get(self, skill_id: str) -> Optional[SkillIndexItem]:
        _ = self.list_index()
        return self._index_by_id.get(skill_id)

    def load_full(self, skill_id: str) -> SkillAsset:
        _ = self.list_index()
        skill_root = self._root_by_id.get(skill_id)
        if skill_root is None:
            raise ValueError(f"Unknown skill_id: {skill_id}")

        skill_path = skill_root / "SKILL.md"
        frontmatter, body = load_skill_markdown(skill_path)
        index_item = self._index_by_id.get(skill_id) or _build_index_item(skill_id, frontmatter, skill_root)

        return SkillAsset(
            index=index_item,
            markdown=body,
            scripts=_list_asset_files(skill_root, "scripts"),
            resources=_list_asset_files(skill_root, "resources"),
            assets=_list_asset_files(skill_root, "assets"),
        )

    def _scan_index(self) -> list[SkillIndexItem]:
        items: list[SkillIndexItem] = []
        seen: set[str] = set()
        for root in self._roots:
            if not root.exists() or not root.is_dir():
                continue
            for entry in sorted(root.iterdir(), key=lambda item: item.name):
                if not entry.is_dir():
                    continue
                skill_id = entry.name
                if skill_id in seen:
                    continue
                skill_path = entry / "SKILL.md"
                if not skill_path.exists():
                    continue
                frontmatter, _body = load_skill_markdown(skill_path)
                index_item = _build_index_item(skill_id, frontmatter, entry)
                items.append(index_item)
                self._index_by_id[skill_id] = index_item
                self._root_by_id[skill_id] = entry
                seen.add(skill_id)
        return items


def _build_index_item(skill_id: str, frontmatter: SkillFrontmatter, root: Path) -> SkillIndexItem:
    return SkillIndexItem(
        skill_id=skill_id,
        name=frontmatter.name,
        description=frontmatter.description,
        tags=list(frontmatter.tags),
        allowed_tools=list(frontmatter.allowed_tools),
        model_override=frontmatter.model_override,
        disable_model_invocation=frontmatter.disable_model_invocation,
        root=str(root),
    )


def _list_asset_files(skill_root: Path, folder: str) -> list[str]:
    target = skill_root / folder
    if not target.exists() or not target.is_dir():
        return []
    files = [
        str(path.relative_to(skill_root))
        for path in target.rglob("*")
        if path.is_file()
    ]
    return sorted(files)
