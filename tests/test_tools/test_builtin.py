"""Tests for built-in tools: file_read, web_fetch."""

from pathlib import Path

import pytest

from roxy.tools.base import ToolContext
from roxy.tools.builtin.file_read import ReadFileTool
from roxy.tools.builtin.web_fetch import WebFetchTool


class TestReadFileTool:
    @pytest.mark.asyncio
    async def test_reads_file_in_workspace(self, tmp_path: Path):
        (tmp_path / "test.txt").write_text("line 1\nline 2\nline 3")
        ctx = ToolContext(workspace_root=tmp_path)
        tool = ReadFileTool()
        result = await tool.execute({"path": "test.txt"}, ctx)
        assert result.success
        assert "line 1" in result.content
        assert result.data["total_lines"] == 3

    @pytest.mark.asyncio
    async def test_reads_file_with_absolute_path(self, tmp_path: Path):
        path = tmp_path / "abs.txt"
        path.write_text("absolute content")
        ctx = ToolContext(workspace_root=tmp_path)
        tool = ReadFileTool()
        result = await tool.execute({"path": str(path)}, ctx)
        assert result.success
        assert "absolute content" in result.content

    @pytest.mark.asyncio
    async def test_file_not_found(self, tmp_path: Path):
        ctx = ToolContext(workspace_root=tmp_path)
        tool = ReadFileTool()
        result = await tool.execute({"path": "nonexistent.txt"}, ctx)
        assert not result.success
        assert "not found" in result.content.lower()

    @pytest.mark.asyncio
    async def test_not_a_file(self, tmp_path: Path):
        ctx = ToolContext(workspace_root=tmp_path)
        tool = ReadFileTool()
        result = await tool.execute({"path": "."}, ctx)
        assert not result.success
        assert "not a file" in result.content.lower()

    @pytest.mark.asyncio
    async def test_offset_and_limit(self, tmp_path: Path):
        (tmp_path / "lines.txt").write_text("\n".join(str(i) for i in range(100)))
        ctx = ToolContext(workspace_root=tmp_path)
        tool = ReadFileTool()
        result = await tool.execute({"path": "lines.txt", "offset": 50, "limit": 10}, ctx)
        assert result.success
        assert result.data["start_line"] == 50
        assert result.data["end_line"] == 59

    def test_risk_level(self):
        from roxy.tools.base import RiskLevel
        assert ReadFileTool.risk_level == RiskLevel.safe
        assert ReadFileTool.workspace_bounded is True

    def test_schema_has_required_fields(self):
        tool = ReadFileTool()
        schema = tool.to_openai_schema()
        func = schema["function"]
        assert func["name"] == "file_read"
        assert "path" in func["parameters"].get("required", [])


class TestWebFetchTool:
    def test_risk_level(self):
        from roxy.tools.base import RiskLevel
        assert WebFetchTool.risk_level == RiskLevel.safe
        assert WebFetchTool.workspace_bounded is False

    def test_schema_has_url_required(self):
        tool = WebFetchTool()
        schema = tool.to_openai_schema()
        assert "url" in schema["function"]["parameters"].get("required", [])

    @pytest.mark.asyncio
    async def test_rejects_invalid_url(self, tmp_path: Path):
        ctx = ToolContext(workspace_root=tmp_path)
        tool = WebFetchTool()
        result = await tool.execute({"url": "not-a-real-url"}, ctx)
        assert not result.success
        assert "http" in result.content.lower()

    @pytest.mark.asyncio
    async def test_handles_connection_error(self, tmp_path: Path):
        """Fetching a non-existent domain returns an error (not an exception)."""
        ctx = ToolContext(workspace_root=tmp_path)
        tool = WebFetchTool()
        result = await tool.execute({"url": "https://this-domain-definitely-does-not-exist-12345.com"}, ctx)
        # Should return a ToolResult (success=False), not raise
        from roxy.tools.base import ToolResult
        assert isinstance(result, ToolResult)
        assert not result.success
