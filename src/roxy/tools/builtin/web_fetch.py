"""WebFetchTool — fetch and parse a URL into markdown (risk=safe, GET-only)."""

from typing import Any

import httpx

from roxy.tools.base import BaseTool, RiskLevel, ToolContext, ToolResult


class WebFetchTool(BaseTool):
    """Fetch a URL and return its content as markdown text.

    GET-only — no POST, no auth headers. Uses Jina Reader as a fallback
    for JavaScript-heavy pages that plain httpx can't render.

    Risk=safe: read-only network request, no file writes.
    """

    name: str = "web_fetch"
    description: str = (
        "Fetch the content of a web page at the given URL and return it as markdown text. "
        "Use this to read articles, documentation, or any publicly accessible web page. "
        "Only GET requests are supported."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch. Must start with http:// or https://.",
            },
        },
        "required": ["url"],
    }
    risk_level: RiskLevel = RiskLevel.safe
    workspace_bounded: bool = False  # Network access is not workspace-bounded

    # Timeout for requests
    REQUEST_TIMEOUT: float = 30.0

    async def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        url = params["url"].strip()

        if not url.startswith(("http://", "https://")):
            return ToolResult.fail(f"Invalid URL: {url} (must start with http:// or https://)")

        # Try direct fetch first
        try:
            async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Roxy/0.1 (research-agent)",
                        "Accept": "text/html, text/plain, */*",
                    },
                )
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if "text/html" in content_type:
                        text = self._html_to_markdown(response.text, url)
                        return ToolResult.ok(
                            content=text,
                            data={"url": url, "status": 200, "method": "direct"},
                        )
                    elif "text/plain" in content_type:
                        return ToolResult.ok(
                            content=response.text,
                            data={"url": url, "status": 200, "method": "direct"},
                        )
                    else:
                        return ToolResult.ok(
                            content=response.text[:5000],
                            data={"url": url, "status": 200, "content_type": content_type, "method": "direct"},
                        )
                elif response.status_code in (403, 451):
                    # Try Jina Reader fallback for pages that block direct access
                    return await self._jina_fallback(url)
                else:
                    return ToolResult.fail(f"HTTP {response.status_code} for {url}")
        except httpx.TimeoutException:
            return ToolResult.fail(f"Timeout fetching {url} (>{self.REQUEST_TIMEOUT}s)")
        except httpx.ConnectError:
            return ToolResult.fail(f"Cannot connect to {url}")
        except Exception as exc:
            # Last resort: Jina fallback
            return await self._jina_fallback(url)

    # ── helpers ──────────────────────────────────────────────────

    async def _jina_fallback(self, url: str) -> ToolResult:
        """Use Jina Reader (r.jina.ai) as a fallback renderer."""
        jina_url = f"https://r.jina.ai/{url}"
        try:
            async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT, follow_redirects=True) as client:
                response = await client.get(
                    jina_url,
                    headers={"Accept": "text/markdown"},
                )
                if response.status_code == 200:
                    return ToolResult.ok(
                        content=response.text,
                        data={"url": url, "status": 200, "method": "jina_fallback"},
                    )
                return ToolResult.fail(f"Jina fallback returned HTTP {response.status_code}")
        except Exception as exc:
            return ToolResult.fail(f"All fetch methods failed for {url}: {exc}")

    @staticmethod
    def _html_to_markdown(html: str, base_url: str = "") -> str:
        """Convert HTML to markdown using markdownify if available, else basic strip."""
        try:
            from bs4 import BeautifulSoup
            from markdownify import markdownify as md

            soup = BeautifulSoup(html, "html.parser")
            # Remove scripts and styles
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            body = soup.find("body") or soup
            return md(str(body), heading_style="ATX")
        except ImportError:
            # Fallback: basic HTML tag stripping
            import re

            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", "", text)
            text = re.sub(r"\n\s*\n", "\n\n", text)
            return text.strip()[:10000]
