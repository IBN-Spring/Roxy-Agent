---
name: web-research
description: Search the web and extract structured research findings. Use when the user asks to research a topic, find information online, or gather sources.
---

# Web Research

Search the web for a given topic and extract structured findings.

## Workflow

1. **Clarify the topic** — ask the user what specific aspect they want researched
2. **Search** — use web_search tool with targeted queries
3. **Fetch** — use web_fetch tool to read the most promising pages
4. **Extract** — pull out key facts, viewpoints, and sources
5. **Write to KB** — use knowledge_write to save findings

## Output Format

For each finding:
- Title
- Source URL
- Key points (bullet list)
- Relevance to user's research domain
- Follow-up questions
