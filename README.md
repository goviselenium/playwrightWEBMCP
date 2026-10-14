# 🚀 AI Autonomous & Playwright v1.64 WebMCP E2E Testing Framework

A production-ready Python-based end-to-end testing and autonomous evaluation framework utilizing **Playwright v1.64** (leveraging native capabilities for WebMCP and browser context features), Playwright MCP server utilities, custom Pytest fixtures, and a local **Ollama LLM provider** (defaulting to `llama3.2:latest`) for smart assertions, DOM accessibility auditing, and autonomous web app navigation.

---

## 🌟 Key Features

- **Native WebMCP Integration (`document.modelContext`)**: Inspects, validates JSON schemas, and programmatically executes WebMCP tools on live web pages via Playwright v1.64.
- **Local Ollama AI Integration**: Connects to `http://localhost:11434` with default model `llama3.2:latest` to perform semantic heuristics, DOM accessibility analysis, and autonomous tool calling without external API fees.
- **Graceful Skipping**: When executed against arbitrary websites that do not implement WebMCP, tests skip gracefully (`pytest.skip()`) rather than generating false-alarm failures.
- **Unified Click CLI**: Command-line interface (`cli.py`) enabling executions against ANY target URL across test tiers (`webmcp`, `integration`, `system`, `uat`, `autonomous`, `all`).
- **Comprehensive 5-Tier Test Architecture**:
  1. `test_webmcp_contract.py`: Asserts WebMCP specification compliance and tool schema validity.
  2. `test_integration.py`: Validates front-end to back-end endpoints, network traffic, and payload responses.
  3. `test_system.py`: Multi-step UI flows via Playwright 1.64 locators and state assertions.
  4. `test_uat.py`: Business requirement validation, responsive viewport tests, and performance SLAs.
  5. `test_ai_autonomous.py`: Captures page accessibility trees and executes autonomous AI heuristic checks and tool invocations.
- **Self-Contained Demo Target**: Includes a built-in WebMCP reference application (`demo/demo_app.html`) that works completely offline.

---

## 📂 Project Directory Structure

```
ai-playwright-webmcp-framework/
├── .env.example              # Environment variables template
├── .gitignore                 # Standard Python, Playwright, and Pytest exclusions
├── README.md                  # Comprehensive framework documentation
├── requirements.txt           # Pinned dependencies (Playwright 1.64, Pytest 8, etc.)
├── pytest.ini                 # Pytest configuration and marker declarations
├── cli.py                     # Click CLI runner
├── conftest.py                # Global fixtures (URL passing, Playwright context, WebMCP, Ollama)
├── demo/
│   ├── demo_app.html          # Reference WebMCP application
│   └── serve_demo.py          # Local HTTP server helper
├── utils/
│   ├── __init__.py
│   ├── mcp_client.py          # Playwright MCP context client and protocol bindings
│   ├── webmcp_helper.py       # document.modelContext inspection, validation, & execution
│   └── ollama_client.py       # Local Ollama client for smart assertions & heuristics
└── tests/
    ├── __init__.py
    ├── test_webmcp_contract.py # Contract and JSON schema adherence
    ├── test_integration.py    # Network and API response validation
    ├── test_system.py         # Multi-step UI locator interactions
    ├── test_uat.py            # User acceptance scenarios and responsive layouts
    └── test_ai_autonomous.py  # AI DOM accessibility and autonomous tool calling
```

---

## ⚡ Quickstart Guide

### 1. Prerequisites
- **Python**: 3.10+ (tested on Python 3.13)
- **Ollama**: Installed and running locally (`ollama serve`). Ensure model is pulled:
  ```bash
  ollama pull llama3.2:latest
  ```

### 2. Installation
Clone or navigate into the framework folder:
```bash
cd ai-playwright-webmcp-framework
pip install -r requirements.txt
playwright install chromium
```

### 3. Environment Setup (Optional)
Copy the template and modify variables if desired:
```bash
cp .env.example .env
```

---

## 🖥️ Running Tests via CLI

The unified CLI runner (`cli.py`) allows you to run test tiers against any target URL:

### Run All Tiers (against default built-in WebMCP demo)
```bash
python cli.py --tier all
```

### Run WebMCP Contract Tests against an External URL
```bash
python cli.py --url "https://example.com" --tier webmcp
```
*(Note: If the target website does not implement `document.modelContext`, contract tests skip gracefully).*

### Run AI Autonomous Tests with a Specific Ollama Model
```bash
python cli.py --tier autonomous --model "llama3.2:latest"
```

### Run System & UI Tests in Headed Mode (Visible Browser)
```bash
python cli.py --tier system --headed
```

### Generate HTML Test Execution Report
```bash
python cli.py --tier all --report
```
*Generates a self-contained `report.html` viewable in any browser.*

---

## 🧪 Direct Pytest Execution

You can also run tests directly with `pytest`:

```bash
# Run WebMCP tier
pytest -m webmcp --url="https://example.com"

# Run system tier
pytest -m system

# Run autonomous AI tests
pytest -m autonomous --model="llama3.2:latest"
```

---

## 📦 GitHub Initialization Instructions

Follow these steps to initialize and push this repository to GitHub:

### 1. Initialize Local Git Repository
```bash
git init
```

### 2. Stage and Commit All Framework Files
```bash
git add .
git commit -m "feat: init Playwright 1.64 WebMCP AI Autonomous Testing Framework"
```

### 3. Connect to Remote GitHub Repository and Push
```bash
git branch -M main
git remote add origin https://github.com/goviselenium/playwrightWEBMCP.git
git push -u origin main
```

---

## 🛠️ Architecture & WebMCP API Reference

### `document.modelContext` Contract
WebMCP exposes a standardized JavaScript context object directly on the DOM:
```javascript
document.modelContext = {
  name: "Store App",
  version: "1.64.0",
  tools: [
    {
      name: "searchCatalog",
      description: "Search products by keyword",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string" }
        },
        required: ["query"]
      },
      execute: async ({ query }) => { /* ... */ }
    }
  ]
};
```

### `WebMCPHelper` (`utils/webmcp_helper.py`)
- `is_supported()`: Returns `True` if `document.modelContext` exists on the active page.
- `get_webmcp_tools()`: Discovers and parses all tools into validated Pydantic models.
- `validate_tool_schemas(tools)`: Verifies parameter schemas conform to JSON Schema specifications.
- `execute_webmcp_tool(name, args)`: Dispatches tool invocations into the live page context with error boundary capture.

### `OllamaClient` (`utils/ollama_client.py`)
- `is_healthy()`: Health check for `http://localhost:11434`.
- `evaluate_accessibility_tree(snapshot, url)`: Sends DOM accessibility tree to Ollama for WCAG/heuristic evaluation.
- `evaluate_webmcp_decision(goal, tools, page_state)`: Evaluates user goals against WebMCP tools and selects the best action.
- `smart_assertion(description, observed_data)`: Autonomous test assertion evaluating UI semantics and behavior.
