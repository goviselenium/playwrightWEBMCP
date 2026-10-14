#!/usr/bin/env python3
"""
CLI Runner for the AI Autonomous & Playwright v1.64 WebMCP E2E Testing Framework.

Enables command-line orchestration to execute test suites against ANY target URL:
    python cli.py --url "https://example.com" --tier webmcp
    python cli.py --url "https://example.com" --tier all --model "llama3.2:latest"
"""

import os
import sys
import pathlib
import click
import pytest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

TIER_MARKER_MAP = {
    "webmcp": "-m webmcp",
    "integration": "-m integration",
    "system": "-m system",
    "uat": "-m uat",
    "autonomous": "-m autonomous",
    "all": ""
}


@click.command()
@click.option(
    "--url",
    default=None,
    help="Target web URL to test (e.g. 'https://example.com' or local file/HTTP demo)."
)
@click.option(
    "--tier",
    type=click.Choice(["webmcp", "integration", "system", "uat", "autonomous", "all"], case_sensitive=False),
    default="all",
    show_default=True,
    help="Execution tier to run."
)
@click.option(
    "--model",
    default="llama3.2:latest",
    show_default=True,
    help="Ollama model for AI smart assertions and autonomous navigation."
)
@click.option(
    "--headed/--headless",
    default=False,
    help="Launch browser in headed (visible) or headless mode."
)
@click.option(
    "--report/--no-report",
    default=False,
    help="Generate an HTML test execution report."
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=True,
    help="Enable detailed Pytest verbose output."
)
def main(url: str, tier: str, model: str, headed: bool, report: bool, verbose: bool):
    """
    AI Autonomous & Playwright v1.64 WebMCP E2E Testing Framework Runner.
    """
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    base_dir = pathlib.Path(__file__).parent.resolve()
    default_demo_url = (base_dir / "demo" / "demo_app.html").as_uri()
    active_url = url or os.getenv("TARGET_URL") or default_demo_url

    # Display execution banner
    banner_text = (
        f"[bold cyan]AI Autonomous & Playwright v1.64 WebMCP E2E Runner[/bold cyan]\n"
        f"[bold white]Target URL:[/bold white] [green]{active_url}[/green]\n"
        f"[bold white]Test Tier:[/bold white] [yellow]{tier.upper()}[/yellow]\n"
        f"[bold white]Ollama Model:[/bold white] [magenta]{model}[/magenta]\n"
        f"[bold white]Browser Mode:[/bold white] {'Headed' if headed else 'Headless'}"
    )
    console.print(Panel(banner_text, border_style="blue", title="[+] Framework Execution Config"))

    # Build pytest CLI arguments
    pytest_args = [
        str(base_dir / "tests"),
        f"--url={active_url}",
        f"--model={model}",
    ]

    if verbose:
        pytest_args.append("-v")

    if headed:
        pytest_args.append("--headed")

    # Apply tier marker filter
    marker_flag = TIER_MARKER_MAP.get(tier.lower(), "")
    if marker_flag:
        pytest_args.extend(marker_flag.split())

    # HTML Report configuration
    if report:
        report_path = str(base_dir / "report.html")
        pytest_args.append(f"--html={report_path}")
        pytest_args.append("--self-contained-html")
        console.print(f"[cyan]Report generation enabled -> {report_path}[/cyan]")

    console.print(f"[dim]Executing pytest with: {' '.join(pytest_args)}[/dim]\n")

    # Execute Pytest
    exit_code = pytest.main(pytest_args)

    # Render summary table
    table = Table(title="Test Execution Summary", border_style="cyan")
    table.add_column("Parameter", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    table.add_row("Target URL", active_url)
    table.add_row("Test Tier", tier.upper())
    table.add_row("Ollama Model", model)
    table.add_row("Exit Status", "[bold green]PASSED (0)[/bold green]" if exit_code == 0 else f"[bold red]FAILED ({exit_code})[/bold red]")

    console.print(table)

    if exit_code == 0:
        console.print("\n[bold green][PASS] All specified test assertions passed successfully![/bold green]\n")
    else:
        console.print(f"\n[bold red][FAIL] Tests finished with non-zero exit code: {exit_code}[/bold red]\n")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
