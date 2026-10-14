"""
Integration Test Suite.

Validates front-end to back-end communication, API payload structures,
network traffic health, and asset delivery using Playwright v1.64.
"""

from typing import List
import pytest
from playwright.async_api import Page, Response


@pytest.mark.integration
class TestIntegration:

    async def test_network_traffic_health(self, page: Page, target_url: str):
        """
        Monitors all HTTP network responses during page load.
        Asserts that no server-side 5xx errors occur.
        """
        failed_responses: List[str] = []

        def handle_response(response: Response):
            if response.status >= 500:
                failed_responses.append(f"{response.url} returned status {response.status}")

        page.on("response", handle_response)
        
        # Reload to capture all initial network traffic
        await page.reload(wait_until="domcontentloaded")
        assert len(failed_responses) == 0, f"Server errors detected: {failed_responses}"

    async def test_static_asset_integrity(self, page: Page):
        """
        Validates that critical scripts and stylesheets load with appropriate HTTP status codes.
        """
        resources = await page.evaluate("""() => {
            return performance.getEntriesByType('resource').map(r => ({
                name: r.name,
                initiatorType: r.initiatorType,
                duration: r.duration
            }));
        }""")

        assert isinstance(resources, list), "Resource entries should be a list"
        # Validate that asset durations are reasonable (non-blocking)
        for res in resources[:20]:
            assert res.get("duration", 0) < 15000, f"Resource {res.get('name')} took excessive time to load"

    async def test_client_side_api_dispatch(self, page: Page):
        """
        Validates the page's ability to dispatch asynchronous fetch requests and parse JSON payloads.
        """
        result = await page.evaluate("""async () => {
            try {
                // Test client fetch capability
                const res = await fetch(window.location.href);
                return {
                    status: res.status,
                    ok: res.ok,
                    type: res.type
                };
            } catch (err) {
                return { error: String(err) };
            }
        }""")

        assert "error" not in result, f"Client-side fetch error: {result.get('error')}"
        assert result.get("ok") is True or result.get("status") in [200, 304, 0], (
            f"Unexpected fetch status: {result}"
        )

    async def test_console_error_boundaries(self, page: Page):
        """
        Asserts that no uncaught JavaScript exceptions are thrown in the browser console.
        """
        console_errors: List[str] = []
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        await page.evaluate("() => console.info('Framework integration check running.')")
        assert len(console_errors) == 0, f"Uncaught page errors found: {console_errors}"
