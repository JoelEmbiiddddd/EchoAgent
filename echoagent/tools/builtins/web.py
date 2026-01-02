from __future__ import annotations

from echoagent.tools.models import ToolContext, ToolSpec
from echoagent.tools.web_tools.crawl import crawl_site
from echoagent.tools.web_tools.search import search_and_scrape

WEB_SEARCH_SPEC = ToolSpec(
    name="web_search",
    description=(
        "Perform a web search for a given query and return URLs with titles, "
        "descriptions, and extracted text."
    ),
    args_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
        },
        "required": ["query"],
    },
    result_schema=None,
    tags=["web"],
)

CRAWL_WEBSITE_SPEC = ToolSpec(
    name="crawl_website",
    description=(
        "Crawl pages within a website starting from a URL and return extracted text."
    ),
    args_schema={
        "type": "object",
        "properties": {
            "starting_url": {
                "type": "string",
                "description": "Starting URL to crawl",
            },
        },
        "required": ["starting_url"],
    },
    result_schema=None,
    tags=["web"],
)


async def web_search_handler(args: dict[str, object], ctx: ToolContext):
    # Source: echoagent/tools/web_tools/search.py:289-312 -> echoagent/tools/builtins/web.py
    _ = ctx
    query = args["query"]
    return await search_and_scrape(query)


async def crawl_website_handler(args: dict[str, object], ctx: ToolContext):
    # Source: echoagent/tools/web_tools/crawl.py:9-81 -> echoagent/tools/builtins/web.py
    _ = ctx
    starting_url = args["starting_url"]
    return await crawl_site(starting_url)
