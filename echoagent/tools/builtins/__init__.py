from __future__ import annotations

from echoagent.tools.builtins.web import (
    CRAWL_WEBSITE_SPEC,
    WEB_SEARCH_SPEC,
    crawl_website_handler,
    web_search_handler,
)
from echoagent.tools.registry import ToolRegistry


def register_builtin_tools(registry: ToolRegistry) -> None:
    if not registry.has(WEB_SEARCH_SPEC.name):
        registry.register(WEB_SEARCH_SPEC, web_search_handler)
    if not registry.has(CRAWL_WEBSITE_SPEC.name):
        registry.register(CRAWL_WEBSITE_SPEC, crawl_website_handler)
