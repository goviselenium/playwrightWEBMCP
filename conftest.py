"""
Pytest configuration and global fixtures for the AI Playwright WebMCP Testing Framework.
Supports Playwright v1.64, local Ollama integration, and dynamic CLI target URLs.
"""

import os
import pathlib
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from utils.webmcp_helper import WebMCPHelper
from utils.ollama_client import OllamaClient
from utils.mcp_client import PlaywrightMCPClient

# Load .env file if available
load_dotenv()

DEFAULT_DEMO_PATH = pathlib.Path(__file__).parent / "demo" / "demo_app.html"
DEFAULT_DEMO_URL = DEFAULT_DEMO_PATH.as_uri()


def pytest_addoption(parser):
    """Register custom CLI options for pytest."""
    parser.addoption(
        "--url",
        action="store",
        default=os.getenv("TARGET_URL", DEFAULT_DEMO_URL),
        help="Target URL for test execution (e.g. https://example.com or local demo)"
    )
    parser.addoption(
        "--model",
        action="store",
        default=os.getenv("DEFAULT_OLLAMA_MODEL", "llama3.2:latest"),
        help="Ollama model name for AI assertions (default: llama3.2:latest)"
    )
    parser.addoption(
        "--ollama-url",
        action="store",
        default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        help="Base URL for local Ollama server"
    )
    # Check if --headed is already registered (e.g. by pytest-playwright)
    try:
        parser.addoption(
            "--headed",
            action="store_true",
            default=False,
            help="Run Playwright browser in headed mode (visible UI)"
        )
    except Exception:
        pass


@pytest.fixture(scope="session")
def target_url(request) -> str:
    """Fixture providing the target test URL."""
    url = request.config.getoption("--url")
    return url or DEFAULT_DEMO_URL


@pytest.fixture(scope="session")
def ollama_model(request) -> str:
    """Fixture providing the resolved Ollama model."""
    return request.config.getoption("--model")


@pytest.fixture(scope="session")
def ollama_client(request) -> OllamaClient:
    """Fixture providing configured Ollama client."""
    ollama_url = request.config.getoption("--ollama-url")
    model = request.config.getoption("--model")
    return OllamaClient(base_url=ollama_url, default_model=model)


@pytest_asyncio.fixture(scope="function")
async def browser_instance(request):
    """Creates a fresh Playwright browser instance."""
    headed = request.config.getoption("--headed")
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(
            headless=not headed,
            args=["--disable-web-security", "--allow-file-access-from-files"]
        )
        yield browser
        await browser.close()


@pytest_asyncio.fixture(scope="function")
async def browser_context(browser_instance: Browser) -> BrowserContext:
    """Creates an isolated browser context per test."""
    context = await browser_instance.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent="Playwright-WebMCP-Framework/1.64.0 (Autonomous-AI-Tester)",
        accept_downloads=True,
        ignore_https_errors=True
    )
    yield context
    await context.close()


@pytest_asyncio.fixture(scope="function")
async def page(browser_context: BrowserContext, target_url: str) -> Page:
    """
    Creates an active Playwright page navigated to the target URL.
    Ensures DOM ready state before yielding.
    """
    page_obj = await browser_context.new_page()
    try:
        await page_obj.goto(target_url, wait_until="domcontentloaded", timeout=25000)
    except Exception as e:
        pytest.fail(f"Failed to navigate to target URL '{target_url}': {e}")
    yield page_obj
    await page_obj.close()


@pytest_asyncio.fixture(scope="function")
async def webmcp(page: Page) -> WebMCPHelper:
    """Provides WebMCP helper bound directly to the active page."""
    return WebMCPHelper(page)


@pytest.fixture(scope="function")
def mcp_client(browser_context: BrowserContext) -> PlaywrightMCPClient:
    """Provides Playwright MCP Client for browser-level tool management."""
    return PlaywrightMCPClient(browser_context)
