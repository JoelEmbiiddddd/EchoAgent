import json
import sys
from pathlib import Path

# 确保从仓库根目录执行时可导入 workflows 包
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflows.skill_smoke_test import run


def _assert_result(result: dict) -> None:
    if result.get("available_skills_count", 0) <= 0:
        raise AssertionError("available_skills_count 应大于 0")

    if result.get("activated_skill_id") == "web_search":
        allowlist = result.get("allowlist") or []
        if "web_search" not in allowlist:
            raise AssertionError("allowlist 应包含 web_search")

    tool_test = result.get("tool_test") or {}
    if not tool_test.get("skipped", False):
        denied = tool_test.get("denied") or {}
        allowed = tool_test.get("allowed") or {}
        if denied.get("error_code") != "TOOL_NOT_ALLOWED":
            raise AssertionError("deny 调用必须是 TOOL_NOT_ALLOWED")
        if allowed.get("error_code") == "TOOL_NOT_ALLOWED":
            raise AssertionError("allowed 调用不能是 TOOL_NOT_ALLOWED")


def main() -> int:
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    _assert_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
