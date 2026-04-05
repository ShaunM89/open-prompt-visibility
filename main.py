"""CLI entry point for AI Visibility Tracker."""

import sys
from pathlib import Path

import click
import rich_click as click_rich
from rich.console import Console
from rich.table import Table

from src.tracker import VisibilityTracker
from src.storage import TrackDatabase
from src.analyzer import AnalyticsEngine

# Enable rich click for better CLI formatting
click_rich.click_rich_style = {
    "styles": {
        "option": "bright_cyan",
        "option_flag": "bright_cyan",
        "arg": "bright_yellow",
        "command": "bold blue",
    }
}

console = Console()


@click.group()
def cli():
    """AI Visibility Tracker - Track brand mentions in LLM responses.

    Examples:
        pvt run                     # Run tracking batch
        pvt export --format csv     # Export results
        pvt dashboard               # Launch dashboard
    """
    pass


@cli.command("run")
@click.option(
    "--config",
    "-c",
    default="configs/default.yaml",
    help="Path to configuration file (default: configs/default.yaml)",
)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output during run")
@click.option("--health-check", is_flag=True, help="Only run health checks, do not execute queries")
@click.option("--enable-variations", is_flag=True, help="Enable prompt variations for base prompts")
@click.option(
    "--num-variations",
    type=int,
    default=3,
    help="Number of variations per base prompt (default: 3)",
)
@click.option(
    "--variation-strategy",
    type=click.Choice(["semantic", "syntactic", "llm"]),
    default="semantic",
    help="Strategy for generating variations (default: semantic)",
)
@click.option(
    "--enable-auto-gen", is_flag=True, help="Enable auto-generation of brand-specific prompts"
)
@click.option(
    "--auto-gen-per-brand",
    type=int,
    default=5,
    help="Number of auto-generated prompts per brand (default: 5)",
)
def run_cli(
    config: str,
    verbose: bool,
    health_check: bool,
    enable_variations: bool,
    num_variations: int,
    variation_strategy: str,
    enable_auto_gen: bool,
    auto_gen_per_brand: int,
):
    """Run a full tracking batch across all configured models and prompts."""
    try:
        console.print(f"[blue]Loading configuration from {config}...[/blue]")
        tracker = VisibilityTracker(config)

        if health_check:
            console.print("\n[bold]Running health check...[/bold]")
            health = tracker._health_check()
            if all(health.values()):
                console.print("\n[green]All models available![/green]")
            else:
                failed = [k for k, v in health.items() if not v]
                console.print(f"\n[red]{len(failed)} model(s) unavailable:[/red] {failed}")
            return

        console.print("\n[bold blue]Starting tracking run...[/bold blue]")
        result = tracker.run_batch(verbose=verbose)

        if result.failed_queries > 0:
            console.print(f"\n[yellow]Warning: {result.failed_queries} queries failed[/yellow]")

        sys.exit(0 if result.failed_queries == 0 else 1)

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@cli.command("export")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["csv", "json"]),
    default="csv",
    help="Export format (default: csv)",
)
@click.option("--output", "-o", required=True, help="Output file path")
@click.option("--run-id", type=int, help="Export only a specific run (default: all history)")
@click.option("--days", "-d", default=90, help="Number of days of history to export (default: 90)")
def export_cli(format: str, output: str, run_id: int, days: int):
    """Export tracking data to CSV or JSON."""
    try:
        tracker = VisibilityTracker()

        if run_id:
            output_path = tracker.export_results(run_id=run_id, format=format, output_path=output)
        else:
            output_path = tracker.export_results(format=format, output_path=output)

        console.print(f"[green]Exported to: {output_path}[/green]")

    except Exception as e:
        console.print(f"[red]Export failed: {e}[/red]")
        sys.exit(1)


@cli.command("config")
@click.option("--config", "-c", default="configs/default.yaml", help="Path to configuration file")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def config_cli(config: str, as_json: bool):
    """Display the active configuration."""
    import json

    try:
        tracker = VisibilityTracker(config)

        if as_json:
            console.print(json.dumps(tracker.config, indent=2, default=str))
        else:
            console.print(f"[bold]Configuration: {config}[/bold]\n")
            console.print(f"[bold]Brands:[/bold] {len(tracker.config.get('brands', []))}")

            prompts = tracker.config.get("prompts", {})
            console.print(f"[bold]Prompt categories:[/bold] {len(prompts)}")
            for cat, pmts in prompts.items():
                console.print(f"  - {cat}: {len(pmts)} prompts")

            models = [m for m in tracker.config.get("models", []) if m.get("enabled", True)]
            console.print(f"[bold]Enabled models:[/bold] {len(models)}")
            for m in models:
                console.print(f"  - {m['provider']}/{m['model']}")

            tracking = tracker.config.get("tracking", {})
            console.print(f"[bold]Tracking settings:[/bold]")
            console.print(f"  queries_per_prompt: {tracking.get('queries_per_prompt', 10)}")
            console.print(f"  detection_method: {tracking.get('detection_method', 'both')}")

    except Exception as e:
        console.print(f"[red]Failed to load config: {e}[/red]")
        sys.exit(1)


@cli.command("stats")
@click.option("--days", "-d", default=90, help="Days of history to analyze (default: 90)")
def stats_cli(days: int):
    """Show database statistics."""
    try:
        db = TrackDatabase()
        stats = db.get_stats()

        table = Table(title=f"Database Statistics (Last {days} days)")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Total runs", str(stats["total_runs"]))
        table.add_row("Total queries", str(stats["total_records"]))
        table.add_row("Unique models", str(stats["unique_models"]))
        table.add_row("Total mentions detected", str(stats["total_mentions"]))

        console.print(table)

    except Exception as e:
        console.print(f"[red]Failed to get stats: {e}[/red]")
        sys.exit(1)


@cli.command("trends")
@click.argument("brand", required=True)
@click.option("--days", "-d", default=30, help="Days of history to analyze (default: 30)")
@click.option("--ci", default=95, type=int, help="Confidence level (90, 95, or 99)")
def trends_cli(brand: str, days: int, ci: int):
    """Show mention trends for a specific brand."""
    try:
        tracker = VisibilityTracker()

        # Show summary with confidence intervals
        summary = tracker.analyzer.get_summary(brand, days)

        console.print(f"\n[bold]Brand Analysis: {brand}[/bold]")
        console.print(f"[cyan]Period:[/cyan] Last {days} days")
        console.print(f"[cyan]Total Queries:[/cyan] {summary['total_queries']}")
        console.print(f"[cyan]Total Mentions:[/cyan] {summary['total_mentions']}")
        console.print(f"[cyan]Overall Rate:[/cyan] {summary['overall_mention_rate']}%")

        console.print(f"\n[bold]Model Comparison ({ci}% Confidence Interval)[/bold]")

        variance = tracker.analyzer.calculate_variance(brand, days, ci)

        for model_name, stats in variance.items():
            rate = stats["mention_rate"]
            ci_interval = stats["confidence_interval_95"]
            total = stats["total_runs"]

            if ci_interval:
                ci_str = f"[{ci_interval[0]:.1f} - {ci_interval[1]:.1f}]%"
            else:
                ci_str = "Insufficient data"

            console.print(f"  {model_name}:")
            console.print(f"    Rate: {rate:.1f}% ({total} queries)")
            console.print(f"    {ci}% CI: {ci_str}")

    except Exception as e:
        console.print(f"[red]Failed to get trends: {e}[/red]")
        sys.exit(1)


@cli.command("dashboard")
@click.option("--host", default="localhost", help="Dashboard host (default: localhost)")
@click.option("--port", "-p", type=int, default=8501, help="Dashboard port (default: 8501)")
def dashboard_cli(host: str, port: int):
    """Launch the visualization dashboard.

    Note: This requires the dashboard extra:
        pip install prompt-visibility-tracker[dashboard]

    Or installs Streamlit for a simpler dashboard.
    """
    try:
        import streamlit
        import subprocess
        import sys

        # Find the dashboard.py file
        dashboard_path = Path(__file__).parent / "src" / "dashboard.py"

        if not dashboard_path.exists():
            console.print("[yellow]Streamlit dashboard not implemented yet.[/yellow]")
            console.print("[cyan]View trends with: pvt trends <brand> --days 30[/cyan]")
            return

        console.print(f"[blue]Launching dashboard at http://{host}:{port}...[/blue]")
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(dashboard_path),
                "--server.address",
                host,
                "--server.port",
                str(port),
            ]
        )

    except ImportError:
        console.print("[red]Streamlit not installed.[/red]")
        console.print("[cyan]Install with: pip install prompt-visibility-tracker[dashboard][/cyan]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Failed to launch dashboard: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
