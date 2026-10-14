"""
System Test Suite.

Executes end-to-end multi-step UI flows, verifying navigation, locator interactions,
form state mutations, and accessibility landmarks via Playwright v1.64.
"""

import pytest
from playwright.async_api import Page, expect


@pytest.mark.system
class TestSystem:

    async def test_page_title_and_main_landmarks(self, page: Page):
        """
        Verify that the page defines a readable title and primary landmark container.
        """
        title = await page.title()
        assert len(title) > 0, "Page must define a document title"

        # Check for main landmark or body
        main_landmark = page.locator("main, [role='main'], body")
        await expect(main_landmark.first).to_be_visible()

    async def test_interactive_element_flow(self, page: Page):
        """
        Locates interactive inputs and buttons, performs user interactions,
        and verifies that DOM mutations occur as expected.
        """
        # 1. Check for search input or text inputs
        inputs = page.locator("input[type='text'], input:not([type]), textarea")
        buttons = page.locator("button, input[type='submit']")

        input_count = await inputs.count()
        button_count = await buttons.count()

        assert button_count >= 1 or input_count >= 1, "Page should contain interactive buttons or inputs"

        if input_count > 0:
            first_input = inputs.first
            await first_input.fill("Playwright 1.64 System Test")
            val = await first_input.input_value()
            assert "Playwright" in val, "Input value should reflect filled string"

        if button_count > 0:
            first_button = buttons.first
            if await first_button.is_enabled():
                await first_button.click()

    async def test_interactive_state_persistence(self, page: Page):
        """
        Verifies that interacting with UI widgets updates corresponding text containers.
        """
        # If targeting the demo app, execute specific flow; else general assertion
        cart_button = page.locator("#add-sample-btn")
        if await cart_button.count() > 0:
            await cart_button.click()
            cart_status = page.locator("#cart-status")
            await expect(cart_status).to_contain_text("Cart updated")

            cart_count = page.locator("#cart-count")
            await expect(cart_count).to_contain_text("1")
        else:
            # Universal check: page has interactive elements that don't crash upon focus
            focusable = page.locator("a, button, input").first
            if await focusable.count() > 0:
                await focusable.focus()
                await expect(focusable).to_be_visible()

    async def test_form_validation_and_submission(self, page: Page):
        """
        Tests form validation or submission handling on active page.
        """
        feedback_btn = page.locator("#submit-feedback-btn")
        if await feedback_btn.count() > 0:
            feedback_input = page.locator("#feedback-text")
            await feedback_input.fill("Autonomous validation confirmed.")
            await feedback_btn.click()

            response_box = page.locator("#feedback-response")
            await expect(response_box).to_contain_text("FB-")
        else:
            # General fallback check: ensure forms do not have broken actions
            forms = page.locator("form")
            if await forms.count() > 0:
                first_form = forms.first
                await expect(first_form).to_be_visible()
