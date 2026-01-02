---
name: Web Search
description: Retrieve fresh information from the web and summarize with sources.
tags:
  - web
  - search
allowed_tools:
  - web_search
  - crawl_website
---

# Web Search Skill

Use `web_search` to find relevant sources for the user query. If the initial search results are insufficient, use `crawl_website` on the most relevant URL to gather additional context.

When answering:
- Summarize the findings clearly.
- Include source URLs in brackets after each factual statement.
- Prefer concise citations over long excerpts.
