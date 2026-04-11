"""Core visibility tracking engine."""

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from .analyzer import AnalyticsEngine, MentionDetector
from .models import ModelAdapter, create_adapter
from .storage import TrackDatabase
from .prompt_generator import PromptGenerator, PromptVariation

console = Console()


@dataclass
class RunResult:
    """Result of a tracking run."""

    run_id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    models_used: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class VisibilityTracker:
    """Main orchestrator for visibility tracking."""

    def __init__(self, config_path: str = "configs/default.yaml"):
        """Initialize tracker with configuration."""
        self.config = self._load_config(config_path)
        self.db = TrackDatabase(self.config["output"]["database_path"])
        self.adapters = self._init_adapters()
        self.detector = MentionDetector(self.config)
        self.analyzer = AnalyticsEngine(self.db)
        self.generator = PromptGenerator(self.config)
        self.config_path = config_path
        self.config_hash = self._calculate_config_hash()

    def _load_config(self, config_path: str) -> dict:
        """Load and validate configuration."""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        # If config references tool/users, merge them
        if "tool" in config and "users" in config:
            base_config = {}

            # Load tool config (relative to config file directory)
            tool_path = config_file.parent / config["tool"].lstrip("/")
            if tool_path.exists():
                with open(tool_path, "r") as f:
                    tool_config = yaml.safe_load(f)
                    base_config = tool_config.copy()

            # Load user configs (brands, prompts)
            users_path = config_file.parent / config["users"].lstrip("/")
            if users_path.exists():
                brands_file = users_path / "brands.yaml"
                prompts_file = users_path / "prompts.yaml"

                if brands_file.exists():
                    with open(brands_file, "r") as f:
                        user_config = yaml.safe_load(f)
                        base_config["brands"] = user_config.get("brands", [])

                if prompts_file.exists():
                    with open(prompts_file, "r") as f:
                        user_config = yaml.safe_load(f)
                        # User prompts replace/add to base prompts
                        base_config.update(user_config)

            # Now merge into final config
            config = base_config

        # Validate required fields
        required = ["brands", "models", "prompts", "tracking"]
        for field in required:
            if field not in config:
                raise ValueError(f"Missing required config field: {field}")

        # Also merge detection settings
        if "detection" in config:
            if "method" in config["detection"]:
                if "tracking" not in config:
                    config["tracking"] = {}
                config["tracking"]["detection_method"] = config["detection"]["method"]
            if "llm" in config["detection"]:
                if "tracking" not in config:
                    config["tracking"] = {}
                config["tracking"]["llm_detection"] = config["detection"]["llm"]

        return config

    def _merge_prompts(self, config: dict, prompt_file: str) -> None:
        """Merge prompts from additional YAML files."""
        file_path = Path(prompt_file)
        if not file_path.exists():
            console.print(f"[yellow]Warning: Prompt file not found: {prompt_file}[/yellow]")
            return

        with open(file_path, "r") as f:
            additional = yaml.safe_load(f)

        if isinstance(additional, dict):
            for key, value in additional.items():
                if key in config["prompts"]:
                    config["prompts"][key].extend(value)
                else:
                    config["prompts"][key] = value

    def _calculate_config_hash(self) -> str:
        """Calculate hash of config for tracking runs."""
        config_str = json.dumps(self.config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]

    def _init_adapters(self) -> Dict[str, ModelAdapter]:
        """Initialize enabled model adapters."""
        adapters = {}

        for model_config in self.config["models"]:
            if not model_config.get("enabled", True):
                continue

            try:
                adapter = create_adapter(model_config)
                adapters[f"{model_config['provider']}:{model_config['model']}"] = adapter
            except ValueError as e:
                console.print(f"[yellow]Skipping {model_config['provider']}: {e}[/yellow]")

        return adapters

    def _prepare_prompts(
        self,
        enable_variations: bool = False,
        num_variations: int = 3,
        variation_strategy: str = "semantic",
        enable_auto_gen: bool = False,
        auto_gen_per_brand: int = 5,
    ) -> Dict[str, List[str]]:
        """Prepare prompts with variations and/or auto-generation.

        Args:
            enable_variations: Whether to generate variations
            num_variations: Number of variations per base prompt
            variation_strategy: Strategy for variations
            enable_auto_gen: Whether to auto-generate prompts
            auto_gen_per_brand: Number of auto-generated prompts per brand

        Returns:
            Dictionary of prompt categories to prompt lists
        """
        all_prompts = {}

        # Start with base prompts
        for category, prompts in self.config["prompts"].items():
            all_prompts[category] = prompts.copy()

        # Add variations if enabled
        if enable_variations:
            base_prompts = []
            for prompts in self.config["prompts"].values():
                base_prompts.extend(prompts)

            if base_prompts:
                variations = self.generator.generate_variations(
                    base_prompts, num_variations=num_variations, strategy=variation_strategy
                )

                # Group variations by original prompt
                for prompt in base_prompts:
                    original_category = "variations"

                    # Add original prompt
                    if original_category not in all_prompts:
                        all_prompts[original_category] = []
                    if prompt not in all_prompts[original_category]:
                        all_prompts[original_category].append(prompt)

                    # Add variations
                    for var in variations:
                        if var.original_prompt == prompt:
                            if var.variation not in all_prompts[original_category]:
                                all_prompts[original_category].append(var.variation)

                console.print(f"  → Generated {len(variations)} prompt variations")

        # Add auto-generated prompts if enabled
        if enable_auto_gen:
            auto_gen_category = "auto_generated"
            all_prompts[auto_gen_category] = []

            for brand_config in self.config.get("brands", []):
                brand_name = brand_config["name"]
                gen_prompts = self.generator.generate_domain_prompts(
                    brand_name, num_prompts=auto_gen_per_brand, categories=None
                )

                for gp in gen_prompts:
                    if gp.prompt not in all_prompts[auto_gen_category]:
                        all_prompts[auto_gen_category].append(gp.prompt)

            console.print(
                f"  → Generated {len(all_prompts[auto_gen_category])} auto-generated prompts"
            )

        return all_prompts

    def _health_check(self) -> Dict[str, bool]:
        """Check health of all adapters."""
        results = {}

        console.print("\n[bold]Checking model availability...[/bold]")

        for key, adapter in self.adapters.items():
            status = adapter.health_check()
            results[key] = status
            icon = "[green]✓[/green]" if status else "[red]×[/red]"
            console.print(f"  {icon} {key}")

        return results

    def run_batch(self, verbose: bool = True) -> RunResult:
        """Execute a full tracking batch across all models and prompts."""
        result = RunResult(
            run_id=self.db.create_run(self.config_hash), started_at=datetime.now(timezone.utc)
        )

        # Get prompt generation settings
        prompt_gen_config = self.config.get("tracking", {}).get("prompt_variations", {})
        enable_variations = prompt_gen_config.get("enabled", False)
        num_variations = prompt_gen_config.get("num_variations", 3)
        variation_strategy = prompt_gen_config.get("strategy", "semantic")

        # Auto-generate prompts if enabled
        auto_gen_config = self.config.get("tracking", {}).get("auto_prompt_generation", {})
        enable_auto_gen = auto_gen_config.get("enabled", False)
        auto_gen_per_brand = auto_gen_config.get("per_brand_prompts", 5)

        # Process prompts with variations and/or auto-generation
        all_prompts = self._prepare_prompts(
            enable_variations,
            num_variations,
            variation_strategy,
            enable_auto_gen,
            auto_gen_per_brand,
        )

        if verbose:
            console.print(f"\n[bold]Starting visibility tracking run #{result.run_id}[/bold]")
            console.print(f"Config hash: {self.config_hash}")
            console.print(
                f"Batches: {len(self.adapters)} models × {len(all_prompts)} prompts × {self.config['tracking']['queries_per_prompt']} queries"
            )
            if enable_variations:
                console.print(f"  → Prompt variations enabled ({num_variations} per base prompt)")
            if enable_auto_gen:
                console.print(f"  → Auto-generation enabled ({auto_gen_per_brand} per brand)")

        # Health check
        health = self._health_check()
        enabled_models = [k for k, v in health.items() if v]

        if not enabled_models:
            raise RuntimeError("No models available. Check configuration and API keys.")

        if verbose:
            console.print(f"\n[bold]Enabled models:[/bold] {', '.join(enabled_models)}\n")

        # Get retry settings
        max_retries = self.config["tracking"].get("max_retries", 3)
        queries_per_prompt = self.config["tracking"]["queries_per_prompt"]

        # Total queries to run
        total_queries = len(enabled_models) * len(all_prompts) * queries_per_prompt

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Running queries...", total=total_queries)

            for model_key in enabled_models:
                adapter = self.adapters[model_key]
                parts = model_key.split(":")
                provider = parts[0]
                model_name = parts[1] if len(parts) > 1 else model_key

                for prompt_category, prompts in all_prompts.items():
                    for prompt_idx, prompt in enumerate(prompts):
                        for query_num in range(queries_per_prompt):
                            # Retry logic
                            success = False
                            error_msg = None

                            for attempt in range(max_retries):
                                try:
                                    response = adapter.query(prompt)
                                    mentions = self.detector.detect(response)

                                    self.db.record_query(
                                        run_id=result.run_id,
                                        model_provider=provider,
                                        model_name=model_name,
                                        prompt=prompt,
                                        response_text=response,
                                        mentions=mentions,
                                    )

                                    result.successful_queries += 1
                                    success = True

                                    if verbose and attempt > 0:
                                        console.print(
                                            f"  [green]Retry {attempt}/{max_retries} successful: {model_name} - {prompt[:50]}...[/green]"
                                        )
                                    break

                                except Exception as e:
                                    error_msg = str(e)
                                    if verbose and attempt < max_retries - 1:
                                        console.print(
                                            f"  [yellow]Attempt {attempt + 1}/{max_retries} failed: {str(e)[:60]}...[/yellow]"
                                        )
                                    time.sleep(2**attempt)  # Exponential backoff

                            if not success:
                                result.failed_queries += 1
                                result.errors.append(
                                    f"{model_name}: {prompt[:50]}... - {error_msg}"
                                )

                            result.total_queries += 1
                            progress.update(task, advance=1)

                            # Small delay between queries to avoid rate limiting
                            time.sleep(0.5)

        result.completed_at = datetime.now(timezone.utc)
        self.db.complete_run(result.run_id)

        if verbose:
            self._print_summary(result)

        return result

    def _print_summary(self, result: RunResult) -> None:
        """Print run summary."""
        console.print("\n" + "=" * 50)
        console.print(f"[bold]Run #{result.run_id} Complete[/bold]")
        if result.completed_at:
            console.print(f"Duration: {result.completed_at - result.started_at}")
        else:
            console.print("Duration: Still running")
        console.print(f"Total queries: {result.total_queries}")
        console.print(f"Successful: [green]{result.successful_queries}[/green]")
        console.print(f"Failed: [red]{result.failed_queries}[/red]")

        if result.failed_queries > 0:
            console.print(f"\n[bold yellow]Errors ([/{result.failed_queries}]):[/bold]")
            for error in result.errors[:5]:  # Show first 5 errors
                console.print(f"  • {error}")
            if len(result.errors) > 5:
                console.print(f"  ... and {len(result.errors) - 5} more")

    def export_results(
        self, run_id: Optional[int] = None, format: str = "csv", output_path: str = "results.csv"
    ) -> str:
        """Export results to CSV or JSON."""
        if run_id:
            records = self.db.get_by_run(run_id)
            if not records:
                raise ValueError(f"No records found for run #{run_id}")

            import json as json_module

            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            with open(output, "w", encoding="utf-8") as f:
                json_module.dump(records, f, indent=2, default=str)

            return str(output)
        else:
            # Export all history
            if format.lower() == "csv":
                self.db.export_to_csv(output_path)
            elif format.lower() == "json":
                self.db.export_to_json(output_path)
            else:
                raise ValueError(f"Unsupported format: {format}. Use 'csv' or 'json'.")

            return str(Path(output_path).absolute())

    def show_trends(self, brand_keyword: str, days: int = 30) -> None:
        """Print trend analysis for a brand."""
        trends = self.db.get_trends(brand_keyword, days)

        if not trends:
            console.print(
                f"[yellow]No data found for '{brand_keyword}' in the last {days} days[/yellow]"
            )
            return

        console.print(f"\n[bold]Trends for {brand_keyword} (last {days} days)[/bold]")

        # Group by model
        by_model = {}
        for row in trends:
            model = row["model_name"]
            if model not in by_model:
                by_model[model] = {"total": 0, "mentions": 0}
            by_model[model]["total"] += row["total_queries"]
            by_model[model]["mentions"] += row["mention_count"]

        for model, stats in by_model.items():
            rate = (stats["mentions"] / stats["total"] * 100) if stats["total"] > 0 else 0
            console.print(
                f"  {model}: {stats['mentions']}/{stats['total']} ({rate:.1f}% mention rate)"
            )
