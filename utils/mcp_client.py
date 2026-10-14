"""
Playwright MCP (Model Context Protocol) Client Utilities.

Provides Model Context Protocol abstraction layers over Playwright v1.64 browser contexts,
enabling standardized tool discovery, capability negotiation, and tool execution
for AI agents and automated testing frameworks.
"""

from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from playwright.async_api import BrowserContext, Page


class MCPToolParameter(BaseModel):
    """Specification of an MCP tool parameter."""
    type: str = "string"
    description: Optional[str] = None
    default: Optional[Any] = None


class MCPToolDefinition(BaseModel):
    """MCP standard tool schema definition."""
    name: str = Field(..., description="Unique tool name")
    description: str = Field(..., description="Semantic tool description")
    inputSchema: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        description="JSON schema of input arguments"
    )


class MCPToolCall(BaseModel):
    """MCP tool execution request."""
    id: Optional[str] = None
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPToolResponse(BaseModel):
    """MCP tool execution response."""
    id: Optional[str] = None
    is_error: bool = False
    content: List[Dict[str, Any]] = Field(default_factory=list)


class PlaywrightMCPClient:
    """
    Bridge between Playwright v1.64 browser sessions and the Model Context Protocol.
    Manages browser-level tools and injects WebMCP adapters when needed.
    """

    def __init__(self, context: BrowserContext):
        self.context = context
        self._registered_browser_tools: Dict[str, Callable] = {}

    def register_browser_tool(
        self,
        name: str,
        handler: Callable,
        description: str,
        input_schema: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register a host-level browser automation tool (e.g. screenshot, evaluate, click)."""
        self._registered_browser_tools[name] = handler

    async def list_tools(self, page: Optional[Page] = None) -> List[MCPToolDefinition]:
        """
        List all available tools in both host browser context and the active page's WebMCP.
        """
        tools: List[MCPToolDefinition] = []

        # 1. Built-in Playwright context tools
        tools.append(MCPToolDefinition(
            name="browser_take_screenshot",
            description="Captures a full-page or viewport screenshot in Base64.",
            inputSchema={
                "type": "object",
                "properties": {
                    "full_page": {"type": "boolean", "default": True}
                }
            }
        ))
        tools.append(MCPToolDefinition(
            name="browser_get_accessibility_snapshot",
            description="Extracts the accessibility tree of the current page for assistive AI navigation.",
            inputSchema={"type": "object", "properties": {}}
        ))

        # 2. Extract tools from page WebMCP if available
        if page:
            try:
                page_tools = await page.evaluate("""() => {
                    const ctx = document.modelContext || window.modelContext;
                    if (!ctx || !ctx.tools) return [];
                    const list = Array.isArray(ctx.tools) ? ctx.tools : Object.values(ctx.tools);
                    return list.map(t => ({
                        name: t.name,
                        description: t.description || '',
                        inputSchema: t.inputSchema || t.parameters || { type: 'object', properties: {} }
                    }));
                }""")
                for pt in page_tools:
                    tools.append(MCPToolDefinition(
                        name=f"webmcp_{pt['name']}",
                        description=f"[WebMCP Page Tool] {pt['description']}",
                        inputSchema=pt.get("inputSchema", {})
                    ))
            except Exception:
                pass

        return tools

    async def call_tool(
        self,
        page: Page,
        tool_call: MCPToolCall
    ) -> MCPToolResponse:
        """
        Execute an MCP tool against the browser context or page.
        """
        name = tool_call.name
        args = tool_call.arguments

        try:
            if name == "browser_take_screenshot":
                full_page = args.get("full_page", True)
                bytes_data = await page.screenshot(full_page=full_page)
                return MCPToolResponse(
                    id=tool_call.id,
                    content=[{
                        "type": "text",
                        "text": f"Screenshot captured ({len(bytes_data)} bytes)"
                    }]
                )

            elif name == "browser_get_accessibility_snapshot":
                if hasattr(page.locator(":root"), "aria_snapshot"):
                    snapshot = await page.locator(":root").aria_snapshot()
                elif hasattr(page, "accessibility"):
                    snapshot = await page.accessibility.snapshot()
                else:
                    snapshot = await page.evaluate("() => document.body.innerText.substring(0, 1000)")
                return MCPToolResponse(
                    id=tool_call.id,
                    content=[{
                        "type": "text" if isinstance(snapshot, str) else "json",
                        "data": snapshot
                    }]
                )

            elif name.startswith("webmcp_"):
                real_name = name.replace("webmcp_", "")
                out = await page.evaluate("""([tName, tArgs]) => {
                    const ctx = document.modelContext || window.modelContext;
                    if (!ctx) throw new Error('No modelContext found on page');
                    if (typeof ctx.executeTool === 'function') return ctx.executeTool(tName, tArgs);
                    if (typeof ctx.call === 'function') return ctx.call(tName, tArgs);
                    const t = Array.isArray(ctx.tools) ? ctx.tools.find(x => x.name === tName) : ctx.tools[tName];
                    if (!t) throw new Error('Tool not found: ' + tName);
                    const fn = t.execute || t.handler || t;
                    return fn(tArgs);
                }""", [real_name, args])
                return MCPToolResponse(
                    id=tool_call.id,
                    content=[{"type": "json", "data": out}]
                )

            elif name in self._registered_browser_tools:
                handler = self._registered_browser_tools[name]
                res = await handler(page, args)
                return MCPToolResponse(
                    id=tool_call.id,
                    content=[{"type": "json", "data": res}]
                )

            else:
                return MCPToolResponse(
                    id=tool_call.id,
                    is_error=True,
                    content=[{"type": "text", "text": f"Unknown tool: {name}"}]
                )

        except Exception as e:
            return MCPToolResponse(
                id=tool_call.id,
                is_error=True,
                content=[{"type": "text", "text": f"Tool execution failed: {str(e)}"}]
            )
