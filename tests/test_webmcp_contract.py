"""
WebMCP Contract Compliance Test Suite.

Verifies adherence to the Web Model Context Protocol specification:
- document.modelContext presence and schema integrity
- Tool definition enumeration and JSON schema conformance
- Programmatic tool execution contract
- Graceful skipping on non-WebMCP pages
"""

import pytest
from playwright.async_api import Page
from utils.webmcp_helper import WebMCPHelper


@pytest.mark.webmcp
class TestWebMCPContract:

    async def test_document_model_context_availability(self, page: Page, webmcp: WebMCPHelper, target_url: str):
        """
        Verify if the target URL exposes document.modelContext or window.modelContext.
        Skips gracefully if the target URL is a standard non-WebMCP website.
        """
        is_supported = await webmcp.is_supported()
        if not is_supported:
            pytest.skip(
                f"Target URL '{target_url}' does not implement WebMCP (document.modelContext). "
                "Skipping WebMCP contract verification gracefully."
            )
        assert is_supported is True

    async def test_model_context_metadata(self, webmcp: WebMCPHelper, target_url: str):
        """
        Verify that document.modelContext exposes valid metadata (name, version, capabilities).
        """
        if not await webmcp.is_supported():
            pytest.skip(f"WebMCP not supported on '{target_url}'.")

        meta = await webmcp.get_model_context_metadata()
        assert isinstance(meta, dict), "Model context metadata must be a dictionary"
        assert "name" in meta and len(meta["name"]) > 0, "Model context must declare a non-empty name"
        assert "version" in meta, "Model context should declare a version string"

    async def test_tool_enumeration_and_types(self, webmcp: WebMCPHelper, target_url: str):
        """
        Verify that exposed WebMCP tools can be parsed into structured Pydantic WebMCPTool instances.
        """
        if not await webmcp.is_supported():
            pytest.skip(f"WebMCP not supported on '{target_url}'.")

        tools = await webmcp.get_webmcp_tools()
        assert isinstance(tools, list), "WebMCP tools must resolve to a list"
        assert len(tools) > 0, "Target WebMCP page should expose at least one tool"

        for tool in tools:
            assert tool.name, "Every WebMCP tool must declare a name"
            assert isinstance(tool.inputSchema.properties, dict), f"Tool {tool.name} properties must be a dictionary"

    async def test_tool_schema_conformance(self, webmcp: WebMCPHelper, target_url: str):
        """
        Validate all exposed tool parameter schemas against JSON schema format rules.
        """
        if not await webmcp.is_supported():
            pytest.skip(f"WebMCP not supported on '{target_url}'.")

        tools = await webmcp.get_webmcp_tools()
        if not tools:
            pytest.skip("No tools exposed to validate schemas.")

        audit_results = webmcp.validate_tool_schemas(tools)
        for report in audit_results:
            assert report.valid is True, (
                f"WebMCP Tool '{report.tool_name}' failed JSON Schema validation: {report.errors}"
            )

    async def test_safe_tool_execution(self, webmcp: WebMCPHelper, target_url: str):
        """
        Verify that a registered tool can be executed programmatically through the WebMCP bridge.
        """
        if not await webmcp.is_supported():
            pytest.skip(f"WebMCP not supported on '{target_url}'.")

        tools = await webmcp.get_webmcp_tools()
        if not tools:
            pytest.skip("No tools exposed for execution.")

        # Pick a safe tool that requires zero or basic arguments
        target_tool = None
        sample_args = {}

        # Look for search or cart tools
        for t in tools:
            if t.name in ["searchCatalog", "search"]:
                target_tool = t.name
                sample_args = {"query": "test"}
                break
            elif t.name in ["getCurrentCart", "getCart", "getStatus"]:
                target_tool = t.name
                sample_args = {}
                break

        if not target_tool:
            # Fallback to first tool with its required fields populated as mocks
            target_tool = tools[0].name
            for req in tools[0].inputSchema.required:
                prop_type = tools[0].inputSchema.properties.get(req, {}).get("type", "string")
                sample_args[req] = 1 if prop_type in ["integer", "number"] else "test"

        result = await webmcp.execute_webmcp_tool(target_tool, sample_args)
        assert result.tool_name == target_tool
        assert result.success is True, f"Execution of WebMCP tool '{target_tool}' failed: {result.error}"
        assert result.execution_time_ms >= 0.0
