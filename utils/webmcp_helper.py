"""
WebMCP Helper Utility.

Provides programmatic inspection, execution, and JSON Schema validation for WebMCP
(Web Model Context Protocol) contexts exposed on web pages via `document.modelContext`.
Built for integration with Playwright v1.64.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from playwright.async_api import Page


class ToolInputSchema(BaseModel):
    """Schema definition for WebMCP tool input parameters."""
    type: str = Field(default="object", description="Root schema type, typically 'object'")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Property definitions")
    required: List[str] = Field(default_factory=list, description="List of required property names")
    additionalProperties: Optional[bool] = Field(default=None, description="Whether extra properties are allowed")


class WebMCPTool(BaseModel):
    """Pydantic representation of an exposed WebMCP tool."""
    name: str = Field(..., description="Unique tool identifier name")
    description: Optional[str] = Field(default="", description="Human/LLM readable tool purpose")
    inputSchema: ToolInputSchema = Field(default_factory=ToolInputSchema, description="JSON Schema for parameters")
    raw_definition: Dict[str, Any] = Field(default_factory=dict, description="Original raw JS tool definition")


class ToolExecutionResult(BaseModel):
    """Result payload from executing a WebMCP tool on a page."""
    success: bool
    tool_name: str
    output: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0


class SchemaValidationResult(BaseModel):
    """Schema conformance evaluation report."""
    valid: bool
    tool_name: str
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class WebMCPHelper:
    """
    Helper class interfacing with Playwright 1.64 Page instances to discover,
    validate, and execute WebMCP tools via `document.modelContext`.
    """

    def __init__(self, page: Page):
        self.page = page

    async def is_supported(self) -> bool:
        """
        Check if the current page implements WebMCP (document.modelContext or window.modelContext).
        
        Returns:
            bool: True if WebMCP modelContext exists on the page.
        """
        try:
            return await self.page.evaluate("""() => {
                return (
                    (typeof document !== 'undefined' && document.modelContext != null) ||
                    (typeof window !== 'undefined' && window.modelContext != null)
                );
            }""")
        except Exception:
            return False

    async def get_model_context_metadata(self) -> Dict[str, Any]:
        """
        Extract high-level WebMCP context metadata from the document.
        
        Returns:
            Dict containing version, name, and available capabilities.
        """
        if not await self.is_supported():
            return {}

        return await self.page.evaluate("""() => {
            const ctx = document.modelContext || window.modelContext;
            if (!ctx) return {};
            return {
                name: ctx.name || document.title || 'WebMCP-Page',
                version: ctx.version || '1.0.0',
                description: ctx.description || '',
                capabilities: ctx.capabilities || {},
                hasTools: !!(ctx.tools || ctx.getTools)
            };
        }""")

    async def get_webmcp_tools(self) -> List[WebMCPTool]:
        """
        Extract available WebMCP tools and their parameter JSON schemas from the target page.
        
        Returns:
            List[WebMCPTool]: Structured tool definitions.
        """
        if not await self.is_supported():
            return []

        raw_tools = await self.page.evaluate("""async () => {
            const ctx = document.modelContext || window.modelContext;
            if (!ctx) return [];

            let toolsList = [];
            if (typeof ctx.getTools === 'function') {
                try {
                    toolsList = await ctx.getTools();
                } catch (e) {
                    console.error('Error invoking ctx.getTools():', e);
                }
            } else if (Array.isArray(ctx.tools)) {
                toolsList = ctx.tools;
            } else if (typeof ctx.tools === 'object' && ctx.tools !== null) {
                // If stored as key-value map
                toolsList = Object.entries(ctx.tools).map(([name, def]) => {
                    return typeof def === 'object' ? { name, ...def } : { name };
                });
            }

            // Sanitize functions and circular references for JSON serialization
            return toolsList.map(t => {
                const schema = t.inputSchema || t.parameters || t.schema || { type: 'object', properties: {} };
                return {
                    name: String(t.name || ''),
                    description: String(t.description || ''),
                    inputSchema: {
                        type: schema.type || 'object',
                        properties: schema.properties || {},
                        required: Array.isArray(schema.required) ? schema.required : [],
                        additionalProperties: schema.additionalProperties
                    },
                    raw_definition: {
                        name: t.name,
                        description: t.description,
                        hasHandler: typeof t.execute === 'function' || typeof t.handler === 'function' || typeof t.call === 'function'
                    }
                };
            });
        }""")

        tools: List[WebMCPTool] = []
        for item in raw_tools:
            try:
                schema = ToolInputSchema(
                    type=item.get("inputSchema", {}).get("type", "object"),
                    properties=item.get("inputSchema", {}).get("properties", {}),
                    required=item.get("inputSchema", {}).get("required", []),
                    additionalProperties=item.get("inputSchema", {}).get("additionalProperties")
                )
                tools.append(WebMCPTool(
                    name=item.get("name", "unnamed_tool"),
                    description=item.get("description", ""),
                    inputSchema=schema,
                    raw_definition=item.get("raw_definition", {})
                ))
            except Exception as ex:
                # If single tool schema parsing fails, preserve minimal definition
                tools.append(WebMCPTool(
                    name=item.get("name", "malformed_tool"),
                    description=f"Parsing error: {ex}",
                    inputSchema=ToolInputSchema(),
                    raw_definition=item
                ))

        return tools

    async def execute_webmcp_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Programmatically execute a WebMCP tool on the live page via document.modelContext.
        
        Args:
            tool_name: Name of the registered tool to call.
            arguments: Dictionary of arguments conforming to inputSchema.
            
        Returns:
            ToolExecutionResult with execution output or error message.
        """
        args = arguments or {}
        
        if not await self.is_supported():
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error="WebMCP is not supported on this page (document.modelContext missing)."
            )

        try:
            result = await self.page.evaluate("""async ([name, callArgs]) => {
                const startTime = performance.now();
                const ctx = document.modelContext || window.modelContext;
                if (!ctx) {
                    return { success: false, error: 'document.modelContext is not defined.' };
                }

                // 1. Direct tool execution method on context
                if (typeof ctx.executeTool === 'function') {
                    try {
                        const out = await ctx.executeTool(name, callArgs);
                        return { success: true, output: out, elapsed: performance.now() - startTime };
                    } catch (err) {
                        return { success: false, error: String(err && err.message ? err.message : err) };
                    }
                }

                // 2. Direct tool invocation on ctx.call
                if (typeof ctx.call === 'function') {
                    try {
                        const out = await ctx.call(name, callArgs);
                        return { success: true, output: out, elapsed: performance.now() - startTime };
                    } catch (err) {
                        return { success: false, error: String(err && err.message ? err.message : err) };
                    }
                }

                // 3. Locate tool within ctx.tools
                let targetTool = null;
                if (Array.isArray(ctx.tools)) {
                    targetTool = ctx.tools.find(t => t.name === name);
                } else if (typeof ctx.tools === 'object' && ctx.tools !== null) {
                    targetTool = ctx.tools[name];
                }

                if (!targetTool) {
                    return { success: false, error: `Tool "${name}" not found in document.modelContext.tools` };
                }

                const handler = targetTool.execute || targetTool.handler || targetTool.run || (typeof targetTool === 'function' ? targetTool : null);
                if (typeof handler !== 'function') {
                    return { success: false, error: `Tool "${name}" exists but has no executable handler.` };
                }

                try {
                    const out = await handler(callArgs);
                    return { success: true, output: out, elapsed: performance.now() - startTime };
                } catch (err) {
                    return { success: false, error: String(err && err.message ? err.message : err) };
                }
            }""", [tool_name, args])

            return ToolExecutionResult(
                success=bool(result.get("success", False)),
                tool_name=tool_name,
                output=result.get("output"),
                error=result.get("error"),
                execution_time_ms=float(result.get("elapsed", 0.0))
            )
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=f"Playwright evaluation error during tool execution: {str(e)}"
            )

    @staticmethod
    def validate_tool_schemas(tools: List[WebMCPTool]) -> List[SchemaValidationResult]:
        """
        Verify format adherence for model context communication.
        Validates:
        - Non-empty name matching standard identifier rules.
        - Tool description presence for model steering.
        - inputSchema type == 'object'.
        - Valid properties dictionary.
        - Required parameters list referencing actual properties.
        
        Args:
            tools: List of WebMCPTool objects to evaluate.
            
        Returns:
            List[SchemaValidationResult]: Detailed audit report per tool.
        """
        results: List[SchemaValidationResult] = []

        for tool in tools:
            errors: List[str] = []
            warnings: List[str] = []

            # Validate Name
            if not tool.name or not tool.name.strip():
                errors.append("Tool name is missing or empty.")
            elif not tool.name.replace("_", "").replace("-", "").isalnum():
                warnings.append(f"Tool name '{tool.name}' contains non-standard characters.")

            # Validate Description
            if not tool.description or not tool.description.strip():
                warnings.append(f"Tool '{tool.name}' is missing a descriptive purpose for AI agents.")

            # Validate Schema
            schema = tool.inputSchema
            if schema.type != "object":
                errors.append(f"Root schema type must be 'object', got '{schema.type}'.")

            if not isinstance(schema.properties, dict):
                errors.append("inputSchema.properties must be a valid JSON object/dictionary.")
            else:
                # Check required fields exist in properties
                for req_key in schema.required:
                    if req_key not in schema.properties:
                        errors.append(f"Required field '{req_key}' is not defined in properties dictionary.")

                # Validate individual property definitions
                for prop_name, prop_def in schema.properties.items():
                    if not isinstance(prop_def, dict):
                        errors.append(f"Property definition for '{prop_name}' must be an object.")
                    elif "type" not in prop_def and "$ref" not in prop_def:
                        warnings.append(f"Property '{prop_name}' has no defined 'type' or '$ref'.")

            results.append(SchemaValidationResult(
                valid=(len(errors) == 0),
                tool_name=tool.name,
                errors=errors,
                warnings=warnings
            ))

        return results
