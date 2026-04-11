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


def _parse_model_spec(spec: str) -> tuple:
    parts = spec.split(":", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            f"Invalid model spec: '{spec}'. Expected format: provider:model "
            f"(e.g., ollama:gemma4:e2b, openai:gpt-4o)"
        )
    return parts[0], parts[1]


@click.group()
def cli():
    """AI Visibility Tracker - Track brand mentions in LLM responses.

    Examples:
        pvt run                     # Run tracking batch
        pvt export --format csv     # Export results
        pvt serve                   # Start API server for dashboard
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
@click.option(
    "--health-check",
    is_flag=True,
    help="Only run health checks, do not execute queries",
)
@click.option(
    "--enable-variations",
    is_flag=True,
    help="Enable prompt variations for base prompts",
)
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
    "--enable-auto-gen",
    is_flag=True,
    help="Enable auto-generation of brand-specific prompts",
)
@click.option(
    "--auto-gen-per-brand",
    type=int,
    default=5,
    help="Number of auto-generated prompts per brand (default: 5)",
)
@click.option(
    "--model",
    "add_models",
    multiple=True,
    help="Add a model alongside config models (format: provider:model). Can be repeated.",
)
@click.option(
    "--model-only",
    "override_model",
    default=None,
    help="Override config and run only this model (format: provider:model)",
)
@click.option(
    "--target-ci-width",
    type=float,
    default=None,
    help="Target CI width for adaptive sampling (e.g., 15.0 for ±7.5%% precision)",
)
@click.option(
    "--max-queries",
    type=int,
    default=None,
    help="Maximum queries per model×prompt pair for adaptive sampling",
)
@click.option(
    "--convergence-scope",
    type=click.Choice(["primary_brand", "all_tracked_brands"]),
    default=None,
    help="Convergence scope: primary_brand (default) or all_tracked_brands",
)
@click.option(
    "--sentiment-mode",
    type=click.Choice(["fast", "detailed", "off"]),
    default=None,
    help="Sentiment analysis mode (default: from config)",
)
@click.option(
    "--analysis-model",
    default=None,
    help="Override analysis LLM (format: provider:model)",
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
    add_models: tuple,
    override_model: str,
    target_ci_width: float,
    max_queries: int,
    convergence_scope: str,
    sentiment_mode: str,
    analysis_model: str,
):
    """Run a full tracking batch across all configured models and prompts."""
    try:
        console.print(f"[blue]Loading configuration from {config}...[/blue]")
        tracker = VisibilityTracker(config)

        if override_model:
            provider, model_name = _parse_model_spec(override_model)
            tracker.config["models"] = [
                {
                    "provider": provider,
                    "model": model_name,
                    "enabled": True,
                    "temperature": 0.7,
                }
            ]
            tracker.adapters = tracker._init_adapters()
            console.print(f"[cyan]Model override: running only {provider}/{model_name}[/cyan]")
        elif add_models:
            for spec in add_models:
                provider, model_name = _parse_model_spec(spec)
                tracker.config["models"].append(
                    {
                        "provider": provider,
                        "model": model_name,
                        "enabled": True,
                        "temperature": 0.7,
                    }
                )
            tracker.adapters = tracker._init_adapters()
            console.print(f"[cyan]Added {len(add_models)} model(s) from CLI[/cyan]")
        # Override config with CLI flags
        if enable_variations:
            tracker.config.setdefault("tracking", {}).setdefault("prompt_variations", {})[
                "enabled"
            ] = True
            tracker.config["tracking"]["prompt_variations"]["num_variations"] = num_variations
            tracker.config["tracking"]["prompt_variations"]["strategy"] = variation_strategy
        if enable_auto_gen:
            tracker.config.setdefault("tracking", {}).setdefault("auto_prompt_generation", {})[
                "enabled"
            ] = True
            tracker.config["tracking"]["auto_prompt_generation"]["per_brand_prompts"] = (
                auto_gen_per_brand
            )
        adaptive_cfg = tracker.config.setdefault("tracking", {}).setdefault("adaptive_sampling", {})
        if target_ci_width is not None:
            adaptive_cfg["target_ci_width"] = target_ci_width
        if max_queries is not None:
            adaptive_cfg["max_queries"] = max_queries
        if convergence_scope is not None:
            adaptive_cfg["convergence_scope"] = convergence_scope

        if sentiment_mode is not None:
            tracker.config.setdefault("sentiment", {})["mode"] = sentiment_mode
            if hasattr(tracker, "sentiment_analyzer") and tracker.sentiment_analyzer:
                tracker.sentiment_analyzer.mode = sentiment_mode

        if analysis_model:
            provider, model_name = _parse_model_spec(analysis_model)
            tracker.config.setdefault("analysis", {}).update(
                {
                    "provider": provider,
                    "model": model_name,
                }
            )
            if hasattr(tracker, "sentiment_analyzer") and tracker.sentiment_analyzer:
                from src.models import create_adapter

                tracker.sentiment_analyzer.adapter = create_adapter(
                    {
                        "provider": provider,
                        "model": model_name,
                        "temperature": 0.1,
                    }
                )
            console.print(f"[cyan]Analysis model: {provider}/{model_name}[/cyan]")

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


@cli.command("serve")
@click.option("--host", default="127.0.0.1", help="API server host (default: 127.0.0.1)")
@click.option("--port", "-p", type=int, default=8000, help="API server port (default: 8000)")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve_cli(host: str, port: int, reload: bool):
    """Start the API server for the Next.js dashboard.

    Run this before starting the frontend:
        pvt serve
        cd frontend && npm run dev
    """
    try:
        import uvicorn

        console.print(f"[blue]Starting API server at http://{host}:{port}...[/blue]")
        console.print(f"[cyan]API docs available at http://{host}:{port}/docs[/cyan]")
        uvicorn.run("src.api:app", host=host, port=port, reload=reload)

    except ImportError:
        console.print("[red]uvicorn not installed.[/red]")
        console.print("[cyan]Install with: pip install uvicorn[/cyan]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Failed to start API server: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
