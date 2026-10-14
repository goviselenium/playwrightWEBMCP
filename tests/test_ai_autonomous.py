"""
AI Autonomous & Heuristic Test Suite.

Integrates Playwright v1.64 accessibility snapshots, WebMCP tool registries,
and local Ollama LLMs (e.g. llama3.2) for autonomous UI auditing, tool selection,
and smart heuristic assertions.
"""

import pytest
from playwright.async_api import Page
from utils.webmcp_helper import WebMCPHelper
from utils.ollama_client import OllamaClient


@pytest.mark.autonomous
class TestAIAutonomous:

    async def test_ollama_connectivity(self, ollama_client: OllamaClient):
        """
        Verifies local Ollama connectivity.
        Gracefully skips if Ollama daemon is offline.
        """
        if not ollama_client.is_healthy():
            pytest.skip(
                f"Local Ollama server is offline at {ollama_client.base_url}. "
                "Start Ollama via 'ollama serve' to execute AI autonomous suites."
            )
        assert ollama_client.is_healthy() is True

    async def test_ai_accessibility_audit(
        self,
        page: Page,
        ollama_client: OllamaClient,
        target_url: str,
        ollama_model: str
    ):
        """
        Captures the Playwright accessibility snapshot and prompts Ollama
        to evaluate navigation clarity, label completeness, and interactive structure.
        """
        if not ollama_client.is_healthy():
            pytest.skip("Ollama offline.")

        if hasattr(page.locator(":root"), "aria_snapshot"):
            snapshot = await page.locator(":root").aria_snapshot()
        elif hasattr(page, "accessibility"):
            snapshot = await page.accessibility.snapshot()
        else:
            snapshot = await page.evaluate("() => document.body.innerText.substring(0, 1000)")
        assert snapshot is not None, "Failed to capture page accessibility snapshot"

        eval_result = ollama_client.evaluate_accessibility_tree(
            accessibility_snapshot=snapshot,
            page_url=target_url,
            criteria="Verify page has accessible interactive controls and clear labeling without broken elements.",
            model=ollama_model
        )

        print(f"\n[AI Accessibility Audit] Reasoning: {eval_result.reasoning}")
        assert eval_result.passed is True, (
            f"AI Accessibility audit flagged critical issues: {eval_result.reasoning}"
        )

    async def test_autonomous_webmcp_tool_invocation(
        self,
        page: Page,
        webmcp: WebMCPHelper,
        ollama_client: OllamaClient,
        ollama_model: str
    ):
        """
        Autonomously inspects WebMCP tools on the active page, submits them along with
        a user goal to Ollama, and executes the AI-decided tool call.
        """
        if not ollama_client.is_healthy():
            pytest.skip("Ollama offline.")

        if not await webmcp.is_supported():
            pytest.skip("WebMCP is not implemented on the target page. Skipping autonomous tool invocation.")

        tools = await webmcp.get_webmcp_tools()
        if not tools:
            pytest.skip("No WebMCP tools exposed on target page.")

        goal = "Search the store catalog for 'Camera' products."
        serialized_tools = [
            {"name": t.name, "description": t.description, "parameters": t.inputSchema.model_dump()}
            for t in tools
        ]

        page_state = {
            "title": await page.title(),
            "url": page.url
        }

        # Ask Ollama to decide which tool to call
        decision = ollama_client.evaluate_webmcp_decision(
            goal=goal,
            tools=serialized_tools,
            page_state=page_state,
            model=ollama_model
        )

        selected_tool = decision.get("tool")
        arguments = decision.get("arguments", {})
        reasoning = decision.get("reasoning", "")

        print(f"\n[AI Autonomous Agent] Selected Tool: {selected_tool}")
        print(f"[AI Autonomous Agent] Arguments: {arguments}")
        print(f"[AI Autonomous Agent] Reasoning: {reasoning}")

        assert selected_tool in [t.name for t in tools], (
            f"Ollama selected an invalid tool: {selected_tool}"
        )

        # Autonomously execute tool on page
        exec_result = await webmcp.execute_webmcp_tool(selected_tool, arguments)
        assert exec_result.success is True, f"Autonomous execution of tool '{selected_tool}' failed: {exec_result.error}"
        assert exec_result.output is not None

    async def test_smart_assertion_page_semantics(
        self,
        page: Page,
        ollama_client: OllamaClient,
        ollama_model: str
    ):
        """
        Uses Ollama as a smart assertion oracle to verify that the page conveys
        its stated business purpose clearly without misleading content.
        """
        if not ollama_client.is_healthy():
            pytest.skip("Ollama offline.")

        page_text = await page.evaluate("() => document.body.innerText.substring(0, 2000)")
        assertion = ollama_client.smart_assertion(
            assertion_description="The web page presents clear product, tool, or informational content.",
            observed_data={"body_text": page_text, "title": await page.title()},
            model=ollama_model
        )

        print(f"\n[AI Smart Assertion] Result: {assertion.passed} | Reasoning: {assertion.reasoning}")
        assert assertion.passed is True, f"AI Smart assertion rejected page semantics: {assertion.reasoning}"
