from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from echoagent.context import Context
from echoagent.skills.activator import activate_skill
from echoagent.skills.registry import SkillRegistry
from echoagent.skills.router import SkillRouter
from echoagent.tools.executor import ToolExecutor
from echoagent.tools.models import ToolCall, ToolContext
from workflows.base import BaseWorkflow, autotracing


# 踩坑记录（必须写清楚）：
# 1) 中文 prompt 可能被 router 分词为空，导致完全匹配不到 skill（建议 smoke test 用英文）。
# 2) 允许工具执行会被 API key 影响，判断标准必须是“不是 TOOL_NOT_ALLOWED”。
# 3) skills 目录相对路径易失效，必须基于 repo root 推导。
# 4) allowlist 写入路径必须与 ToolExecutor 读取路径一致（context.state.execution.allowed_tools）。


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _get_test_config(config: Any) -> dict[str, Any]:
    pipeline_config = dict(config.pipeline or {})
    test_config = dict(pipeline_config.get("skill_smoke_test", {}) or {})
    for key in ("test_prompt", "force_skill_id", "top_k", "auto_activate", "skills_dir"):
        if key in pipeline_config and key not in test_config:
            test_config[key] = pipeline_config[key]
    return test_config


def _default_tool_args(tool_name: str, prompt: str) -> dict[str, Any]:
    if tool_name == "web_search":
        return {"query": prompt}
    if tool_name == "crawl_website":
        return {"starting_url": "https://example.com"}
    return {}


class SkillSmokeTestWorkflow(BaseWorkflow):
    def __init__(self, config: Any) -> None:
        super().__init__(config)
        self.context = Context()
        self._repo_root = _repo_root()

    @autotracing(enable_printer=False)
    async def run(self) -> dict[str, Any]:
        test_config = _get_test_config(self.config)
        test_prompt = str(test_config.get("test_prompt") or "web search ai")
        force_skill_id = str(test_config.get("force_skill_id") or "").strip()
        top_k = int(test_config.get("top_k") or 3)
        auto_activate = bool(test_config.get("auto_activate", True))

        skills_dir_value = test_config.get("skills_dir")
        if skills_dir_value:
            skills_dir = Path(skills_dir_value).expanduser()
        else:
            skills_dir = self._repo_root / "skills"

        registry = SkillRegistry([str(skills_dir)])
        router = SkillRouter(registry)

        index_items = registry.list_index()
        available_count = len(index_items)

        selected_skill_id: Optional[str] = None
        if force_skill_id:
            selected_skill_id = force_skill_id
        else:
            matches = router.topk(test_prompt, k=top_k)
            if matches:
                selected_skill_id = matches[0].skill_id

        activated_skill_id: Optional[str] = None
        allowlist: list[str] = []
        if auto_activate and selected_skill_id:
            asset = registry.load_full(selected_skill_id)
            activate_skill(self.context, asset)
            activated_skill_id = asset.index.skill_id
            allowlist = list(asset.index.allowed_tools)

        tool_test: dict[str, Any] = {"skipped": True, "reason": "agents not available"}
        try:
            import agents  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            tool_test = {"skipped": True, "reason": f"agents import failed: {exc.__class__.__name__}"}
        else:
            if not allowlist:
                tool_test = {"skipped": True, "reason": "allowlist is empty"}
            else:
                executor = ToolExecutor(context=ToolContext(tracker=self.runtime_tracker))
                denied_call = ToolCall(name="analyze_data", args={}, call_id="deny-1")
                denied_result = await executor.execute(denied_call)

                allowed_tool = "web_search" if "web_search" in allowlist else allowlist[0]
                allowed_args = _default_tool_args(allowed_tool, test_prompt)
                allowed_call = ToolCall(name=allowed_tool, args=allowed_args, call_id="allow-1")
                allowed_result = await executor.execute(allowed_call)

                tool_test = {
                    "skipped": False,
                    "denied": {
                        "tool": denied_call.name,
                        "error_code": denied_result.error.code if denied_result.error else None,
                    },
                    "allowed": {
                        "tool": allowed_call.name,
                        "error_code": allowed_result.error.code if allowed_result.error else None,
                    },
                }

        return {
            "available_skills_count": available_count,
            "selected_skill_id": selected_skill_id,
            "activated_skill_id": activated_skill_id,
            "allowlist": allowlist,
            "tool_test": tool_test,
        }


def run(config_path: str | Path | None = None) -> dict[str, Any]:
    config_path = config_path or _repo_root() / "workflows" / "configs" / "skill_smoke_test.yaml"
    workflow = SkillSmokeTestWorkflow(str(config_path))
    return workflow.run_sync()


def _format_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    result = run()
    print(_format_json(result))
