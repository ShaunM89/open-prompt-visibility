"""CLI entry point for AI Visibility Tracker."""

import sys
import os
from pathlib import Path

import click
import rich_click as click_rich
from rich.console import Console
from rich.table import Table

from src.tracker import VisibilityTracker
from src.storage import TrackDatabase
from src.analyzer import AnalyticsEngine
from src.prompt_compiler import PromptCompiler, StructuredPrompt

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
    "--models",
    "add_models_csv",
    default=None,
    help="Comma-separated model specs (format: provider:model,...). Adds to config models.",
)
@click.option(
    "--scenario",
    "scenario_name",
    default=None,
    help="Use a named scenario from config (replaces models list).",
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
@click.option(
    "--estimate-cost",
    is_flag=True,
    help="Show cost estimate without running queries",
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
    add_models_csv: str,
    override_model: str,
    scenario_name: str,
    target_ci_width: float,
    max_queries: int,
    convergence_scope: str,
    sentiment_mode: str,
    analysis_model: str,
    estimate_cost: bool,
):
    """Run a full tracking batch across all configured models and prompts."""
    try:
        console.print(f"[blue]Loading configuration from {config}...[/blue]")
        tracker = VisibilityTracker(config)

        # Model selection precedence:
        # --model-only > --scenario > env vars (PVT_DEFAULT_MODEL > PVT_MODELS) > --model/--models > config
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

        elif scenario_name:
            scenarios = tracker.config.get("scenarios", {})
            if scenario_name not in scenarios:
                raise ValueError(
                    f"Scenario '{scenario_name}' not found in config. "
                    f"Available: {list(scenarios.keys())}"
                )
            scenario_models = scenarios[scenario_name].get("models", [])
            if not scenario_models:
                raise ValueError(f"Scenario '{scenario_name}' has no models defined")
            tracker.config["models"] = scenario_models
            tracker.adapters = tracker._init_adapters()
            console.print(
                f"[cyan]Loaded scenario '{scenario_name}' with {len(scenario_models)} model(s)[/cyan]"
            )

        else:
            # No exclusive override: check env vars, then process additive CLI flags
            if "PVT_DEFAULT_MODEL" in os.environ:
                env_model = os.environ["PVT_DEFAULT_MODEL"]
                provider, model_name = _parse_model_spec(env_model)
                tracker.config["models"] = [
                    {
                        "provider": provider,
                        "model": model_name,
                        "enabled": True,
                        "temperature": 0.7,
                    }
                ]
                tracker.adapters = tracker._init_adapters()
                console.print(
                    f"[cyan]Model override from PVT_DEFAULT_MODEL: {provider}/{model_name}[/cyan]"
                )

            elif "PVT_MODELS" in os.environ:
                env_specs = [s.strip() for s in os.environ["PVT_MODELS"].split(",") if s.strip()]
                for spec in env_specs:
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
                console.print(f"[cyan]Added {len(env_specs)} model(s) from PVT_MODELS[/cyan]")

            # CLI: --model (additive, repeated)
            if add_models:
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

            # CLI: --models (additive, comma-separated)
            if add_models_csv:
                specs = [s.strip() for s in add_models_csv.split(",") if s.strip()]
                for spec in specs:
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
                console.print(f"[cyan]Added {len(specs)} model(s) from --models[/cyan]")
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

        if estimate_cost:
            from src.cost import estimate_run_cost

            all_prompts = tracker._prepare_prompts(
                enable_variations,
                num_variations,
                variation_strategy,
                enable_auto_gen,
                auto_gen_per_brand,
            )
            num_prompts = sum(len(p) for p in all_prompts.values())
            enabled_models = [m for m in tracker.config.get("models", []) if m.get("enabled", True)]
            adaptive_cfg = tracker.config.get("tracking", {}).get("adaptive_sampling", {})
            max_q = adaptive_cfg.get(
                "max_queries", tracker.config["tracking"]["queries_per_prompt"]
            )

            user_pricing = None
            if tracker.config.get("pricing"):
                user_pricing = tracker.config["pricing"]

            result = estimate_run_cost(
                enabled_models, num_prompts, max_q, user_pricing=user_pricing
            )

            console.print("\n[bold]Cost Estimate[/bold]")
            console.print(f"  Prompts: {num_prompts}")
            console.print(f"  Queries per prompt: up to {max_q} (adaptive)")
            console.print(f"  Estimated total queries: ~{result['estimated_queries']}")

            for mc in result["models"]:
                if mc.total_cost == 0.0:
                    console.print(f"\n  {mc.provider}/{mc.model}: [green]$0.00 (local)[/green]")
                else:
                    console.print(f"\n  {mc.provider}/{mc.model}: max ${mc.total_cost:.2f}")

            if result["is_local"]:
                console.print(f"\n  [green]Total: $0.00 (all local models)[/green]")
            else:
                console.print(f"\n  Max cost: ${result['total_max_cost']:.2f}")
                console.print(
                    f"  Expected: ${result['total_expected_cost']:.2f} (with adaptive sampling)"
                )
            return

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
        console.print(
            "[dim]Press Ctrl+C to suspend (progress is saved). Resume with: pvt resume[/dim]"
        )
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


@cli.command("resume")
@click.argument("run_id", required=False, type=int)
@click.option("--latest", "-l", is_flag=True, help="Resume the most recent suspended run")
@click.option("--config", "-c", default="configs/default.yaml", help="Path to configuration file")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output during run")
def resume_cli(run_id: int, latest: bool, config: str, verbose: bool):
    """Resume a suspended or interrupted tracking run.

    Provide a RUN_ID or use --latest to resume the most recent run.
    """
    try:
        tracker = VisibilityTracker(config)

        if latest and not run_id:
            suspended = tracker.db.get_latest_suspended_run()
            if not suspended:
                console.print("[yellow]No resumable runs found.[/yellow]")
                return
            run_id = suspended["id"]
            status = suspended.get("status", "unknown")
            console.print(f"[cyan]Resuming run #{run_id} (was {status})[/cyan]")

        if not run_id:
            suspended = tracker.db.get_suspended_runs()
            if not suspended:
                console.print("[yellow]No resumable runs found.[/yellow]")
                return
            console.print("[bold]Resumable runs:[/bold]")
            for r in suspended:
                ckpt = r.get("checkpoint_at", "unknown")
                count = r.get("record_count", 0)
                status = r.get("status", "unknown")
                console.print(f"  #{r['id']} — {count} queries, {status}, last checkpoint {ckpt}")
            console.print("\n[yellow]Use: pvt resume <run_id>[/yellow]")
            return

        result = tracker.resume_run(run_id, verbose=verbose)
        sys.exit(0 if result.failed_queries == 0 else 1)

    except ValueError as e:
        console.print(f"[red]{e}[/red]")
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


# --- pvt prompts command group ---


@cli.group("prompts")
def prompts_group():
    """Manage structured prompt test sets.

    Examples:
        pvt prompts generate --brand Nike --keywords running,basketball
        pvt prompts classify --brand Nike
        pvt prompts list
        pvt prompts validate
    """
    pass


@prompts_group.command("generate")
@click.option("--brand", required=True, help="Brand name to generate prompts for")
@click.option("--keywords", required=True, help="Comma-separated topic keywords")
@click.option(
    "--num-prompts", default=50, help="Number of canonical prompts to generate (default: 50)"
)
@click.option(
    "--output",
    "-o",
    default="configs/users/prompts.yaml",
    help="Output file path",
)
@click.option("--config", "-c", default="configs/default.yaml", help="Config file")
def prompts_generate(brand: str, keywords: str, num_prompts: int, output: str, config: str):
    """Generate a classified prompt set using LLM."""
    from src.prompt_compiler import PromptCompiler

    try:
        console.print(f"[blue]Loading configuration from {config}...[/blue]")
        tracker = VisibilityTracker(config)
        compiler = PromptCompiler(tracker.config)

        keywords_list = [k.strip() for k in keywords.split(",") if k.strip()]
        console.print(
            f"[cyan]Generating {num_prompts} prompts for {brand} "
            f"(topics: {', '.join(keywords_list)})...[/cyan]"
        )

        structured = compiler.generate(brand, keywords_list, num_prompts)

        if not structured:
            console.print("[red]No prompts generated. Check LLM availability.[/red]")
            sys.exit(1)

        compiler.save_prompts(structured, output)

        # Summary
        from collections import Counter

        intent_counts = Counter(sp.tags.intent for sp in structured)
        topic_counts = Counter(sp.tags.topic for sp in structured)
        total_variations = sum(len(sp.prompts) - 1 for sp in structured)

        console.print(f"\n[bold green]Generated {len(structured)} canonical prompts[/bold green]")
        console.print(f"  Total with variations: {sum(len(sp.prompts) for sp in structured)}")
        console.print(f"  Variations: {total_variations}")
        console.print(f"\n  [bold]By intent:[/bold]")
        for intent, count in intent_counts.most_common():
            console.print(f"    {intent}: {count}")
        console.print(f"  [bold]By topic:[/bold]")
        for topic, count in topic_counts.most_common():
            console.print(f"    {topic}: {count}")
        console.print(f"\n  Written to: {output}")

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Generation failed: {e}[/red]")
        sys.exit(1)


@prompts_group.command("classify")
@click.option(
    "--input", "input_path", default="configs/users/prompts.yaml", help="Input prompts file"
)
@click.option("--brand", required=True, help="Brand name for query_type detection")
@click.option("--config", "-c", default="configs/default.yaml", help="Config file")
def prompts_classify(input_path: str, brand: str, config: str):
    """Classify untagged prompts using LLM."""
    from src.prompt_compiler import PromptCompiler

    try:
        console.print(f"[blue]Loading configuration from {config}...[/blue]")
        tracker = VisibilityTracker(config)
        compiler = PromptCompiler(tracker.config)

        console.print(f"[cyan]Loading prompts from {input_path}...[/cyan]")
        all_prompts = compiler.load_prompts(input_path)

        if not all_prompts:
            console.print("[yellow]No prompts found in file.[/yellow]")
            return

        # Separate tagged from untagged
        tagged = [sp for sp in all_prompts if sp.tags.is_complete()]
        untagged = [sp for sp in all_prompts if not sp.tags.is_complete()]

        console.print(
            f"  Found {len(all_prompts)} prompts: "
            f"{len(tagged)} already tagged, {len(untagged)} need classification"
        )

        if not untagged:
            console.print("[green]All prompts already classified![/green]")
            return

        # Classify untagged prompts
        untagged_texts = [sp.canonical_prompt() for sp in untagged if sp.canonical_prompt()]
        console.print(f"[cyan]Classifying {len(untagged_texts)} prompts...[/cyan]")

        classified = compiler.classify_prompts(untagged_texts)

        # Merge: classified replaces untagged
        merged = tagged + classified

        compiler.save_prompts(merged, input_path)

        console.print(f"\n[bold green]Classified {len(classified)} prompts[/bold green]")
        console.print(f"  Total prompts in file: {len(merged)}")
        console.print(f"  Written to: {input_path}")

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Classification failed: {e}[/red]")
        sys.exit(1)


@prompts_group.command("list")
@click.option(
    "--input", "input_path", default="configs/users/prompts.yaml", help="Input prompts file"
)
@click.option("--filter-intent", default=None, help="Filter by intent type")
@click.option("--filter-topic", default=None, help="Filter by topic")
@click.option("--config", "-c", default="configs/default.yaml", help="Config file")
def prompts_list(input_path: str, filter_intent: str, filter_topic: str, config: str):
    """Display current prompt set with tags and variation counts."""
    from src.prompt_compiler import PromptCompiler

    try:
        tracker = VisibilityTracker(config)
        compiler = PromptCompiler(tracker.config)
        all_prompts = compiler.load_prompts(input_path)

        if not all_prompts:
            console.print(f"[yellow]No prompts found in {input_path}[/yellow]")
            return

        # Apply filters
        filtered = all_prompts
        if filter_intent:
            filtered = [sp for sp in filtered if sp.tags.intent == filter_intent]
        if filter_topic:
            filtered = [sp for sp in filtered if sp.tags.topic == filter_topic]

        table = Table(title=f"Prompt Set ({len(filtered)} prompts, {input_path})")
        table.add_column("Canonical ID", style="cyan", max_width=16)
        table.add_column("Prompt", style="white", max_width=50, no_wrap=False)
        table.add_column("Intent", style="green", max_width=16)
        table.add_column("Stage", style="yellow", max_width=13)
        table.add_column("Topic", style="blue", max_width=15)
        table.add_column("Type", style="magenta", max_width=10)
        table.add_column("Vars", style="white", justify="right", max_width=4)

        for sp in filtered:
            canonical = sp.canonical_prompt()
            prompt_display = canonical[:47] + "..." if len(canonical) > 50 else canonical

            cid = sp.canonical_id or "(none)"
            intent = sp.tags.intent or "(unclassified)"
            stage = sp.tags.purchase_stage or "(unclassified)"
            topic = sp.tags.topic or "(unclassified)"
            qtype = sp.tags.query_type or "(unclassified)"
            var_count = str(max(0, len(sp.prompts) - 1))

            table.add_row(cid, prompt_display, intent, stage, topic, qtype, var_count)

        console.print(table)

        # Summary
        from collections import Counter

        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  Total canonical prompts: {len(filtered)}")
        console.print(f"  Total with variations: {sum(len(sp.prompts) for sp in filtered)}")

        intent_counts = Counter(sp.tags.intent or "(unclassified)" for sp in filtered)
        console.print(f"  [bold]By intent:[/bold]")
        for intent, count in intent_counts.most_common():
            console.print(f"    {intent}: {count}")

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]List failed: {e}[/red]")
        sys.exit(1)


@prompts_group.command("validate")
@click.option(
    "--input", "input_path", default="configs/users/prompts.yaml", help="Input prompts file"
)
@click.option("--config", "-c", default="configs/default.yaml", help="Config file")
def prompts_validate(input_path: str, config: str):
    """Validate all prompts have complete tags and valid canonical IDs."""
    from src.prompt_compiler import PromptCompiler

    try:
        tracker = VisibilityTracker(config)
        compiler = PromptCompiler(tracker.config)
        all_prompts = compiler.load_prompts(input_path)

        if not all_prompts:
            console.print(f"[yellow]No prompts found in {input_path}[/yellow]")
            return

        errors = compiler.validate_prompts(all_prompts)

        if errors:
            console.print(f"[bold red]Found {len(errors)} validation error(s):[/bold red]")
            for error in errors:
                console.print(f"  [red]✗[/red] {error}")
            sys.exit(1)
        else:
            console.print(f"[bold green]All {len(all_prompts)} prompts are valid[/bold green]")

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Validation failed: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
