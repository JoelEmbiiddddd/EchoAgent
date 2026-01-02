from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# 确保从任意工作目录执行时也能导入项目包
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from echoagent.agent import EchoAgent
from echoagent.context import Context
from echoagent.profiles.debug.vanilla_chat import vanilla_chat_profile
from echoagent.skills.activator import activate_skill
from echoagent.skills.registry import SkillRegistry
from echoagent.skills.router import SkillRouter
from workflows.base import BaseWorkflow, autotracing


class SkillChatQuery(BaseModel):
    message: str

    def format(self) -> str:
        return self.message


class SkillChatWorkflow(BaseWorkflow):
    def __init__(self, config: Any):
        super().__init__(config)

        self.context = Context()
        self.context.profiles = {
            "vanilla_chat": vanilla_chat_profile,
        }
        llm = self.config.llm.main_model
        provider = self.config.provider
        self.chat_agent = EchoAgent(
            context=self.context,
            profile="vanilla_chat",
            llm=llm,
            provider=provider,
        )

        skills_config = dict(self.config.pipeline.get("skills", {}) or {})
        self._skill_topk = int(skills_config.get("topk", 5))
        self._auto_threshold = float(skills_config.get("auto_threshold", 0.65))
        self._suggest_threshold = float(skills_config.get("suggest_threshold", 0.35))

        roots = ["./skills", "~/.codex/skills"]
        self._registry = SkillRegistry(roots)
        self._router = SkillRouter(
            self._registry,
            auto_threshold=self._auto_threshold,
            suggest_threshold=self._suggest_threshold,
        )

    @autotracing()
    async def run(self, query: Any = None) -> Any:
        if query is None:
            message = self.config.prompt or ""
            query_obj = SkillChatQuery(message=message)
        elif isinstance(query, SkillChatQuery):
            query_obj = query
        else:
            message = getattr(query, "prompt", None) or getattr(query, "message", None) or str(query)
            query_obj = SkillChatQuery(message=message)

        self.context.state.set_query(query_obj)

        index_items = self._registry.list_index()
        self.context.state.available_skills = [item.model_dump() for item in index_items]

        matches = self._router.topk(query_obj.message, k=self._skill_topk)
        self.context.state.record_event(
            "SKILL_MATCH",
            f"Top {len(matches)} skills matched",
            meta={"matches": [match.model_dump() for match in matches]},
        )
        if matches:
            match_lines = [
                f"- {match.skill_id}: score={match.score:.2f} auto={match.auto_activate} ({match.reason})"
                for match in matches
            ]
            self.runtime_tracker.log_panel("Skill Match", "\n".join(match_lines))

        auto_match = next((match for match in matches if match.auto_activate), None)
        if auto_match is not None:
            asset = self._registry.load_full(auto_match.skill_id)
            activate_skill(self.context, asset)
            self.runtime_tracker.log_panel(
                "Skill Activate",
                f"skill={auto_match.skill_id}\nallowed_tools={asset.index.allowed_tools}",
            )

        self.update_printer("initialization", "Skill chat workflow initialized", is_done=True)
        self.update_printer("chat", "Chatting with skill routing...")

        result = await self.chat_agent(query_obj)

        self.update_printer("chat", "Chat complete", is_done=True)

        final_result = getattr(result, "response", None) or getattr(result, "output", None) or result
        if self.reporter is not None:
            try:
                self.reporter.set_final_result(final_result)
            except Exception:
                pass

        return final_result


async def _main() -> None:
    config_path = Path(__file__).resolve().parent / "configs" / "skill_chat.yaml"
    workflow = SkillChatWorkflow(str(config_path))
    result = await workflow.run()
    if result is not None:
        print(result)


if __name__ == "__main__":
    asyncio.run(_main())
