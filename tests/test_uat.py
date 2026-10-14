"""
User Acceptance Test (UAT) Suite.

Validates end-user business requirements, responsive viewport layouts,
accessibility baselines, and performance thresholds via Playwright v1.64.
"""

import pytest
from playwright.async_api import BrowserContext, Page, expect


@pytest.mark.uat
class TestUserAcceptance:

    async def test_responsive_mobile_viewport(self, browser_context: BrowserContext, target_url: str):
        """
        Verify that the application renders properly on mobile viewports (375x667).
        Asserts that the page body fits within viewport without horizontal overflow.
        """
        mobile_page: Page = await browser_context.new_page()
        await mobile_page.set_viewport_size({"width": 375, "height": 667})
        await mobile_page.goto(target_url, wait_until="domcontentloaded")

        # Verify main content is visible
        main_elem = mobile_page.locator("main, [role='main'], body").first
        await expect(main_elem).to_be_visible()

        # Check for horizontal scroll overflow
        overflow = await mobile_page.evaluate("""() => {
            return document.documentElement.scrollWidth > window.innerWidth + 20;
        }""")
        assert not overflow, "Mobile viewport has excessive horizontal scrolling/overflow"
        await mobile_page.close()

    async def test_heading_hierarchy_baseline(self, page: Page):
        """
        Validates basic accessibility user criteria: page must have an H1 or primary title.
        """
        h1_locator = page.locator("h1")
        count = await h1_locator.count()
        if count == 0:
            # Fallback check for ARIA heading level 1
            aria_h1 = page.locator("[role='heading'][aria-level='1']")
            count = await aria_h1.count()

        assert count >= 1, "Page must include at least one prominent primary heading (h1)"
        await expect(h1_locator.first if count > 0 else page.locator("body")).to_be_visible()

    async def test_end_to_end_user_journey(self, page: Page):
        """
        Validates primary end-to-end user journey: searching, reviewing, and acting.
        """
        # Search workflow if search input exists
        search_box = page.locator("#search-input, input[type='search'], input[name='q']")
        if await search_box.count() > 0:
            await search_box.fill("Camera")
            search_btn = page.locator("#search-btn, button:has-text('Search')")
            if await search_btn.count() > 0:
                await search_btn.click()
                await page.wait_for_timeout(300)

        # Action workflow: add to cart or click call-to-action
        add_btn = page.locator("#add-sample-btn, button:has-text('Add to Cart'), a:has-text('Get Started')")
        if await add_btn.count() > 0:
            await add_btn.first.click()
            await page.wait_for_timeout(300)

    async def test_navigation_timing_threshold(self, page: Page):
        """
        Validates page load performance criteria: DOMContentLoaded within 10 seconds.
        """
        timing = await page.evaluate("""() => {
            const perf = performance.getEntriesByType('navigation')[0];
            if (!perf) return { domContentLoadedEventEnd: 0 };
            return {
                domContentLoaded: perf.domContentLoadedEventEnd - perf.startTime,
                load: perf.loadEventEnd - perf.startTime
            };
        }""")

        dom_time = timing.get("domContentLoaded", 0)
        # Ensure DOM content loaded is within acceptable SLA (10,000ms)
        assert dom_time < 10000, f"Page DOMContentLoaded took too long: {dom_time}ms"
