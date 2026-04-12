"""Core visibility tracking engine."""

import hashlib
import json
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from .analyzer import (
    AnalyticsEngine,
    AdaptiveSampler,
    MentionDetector,
    MentionContextExtractor,
    SentimentAnalyzer,
    SentimentCIStrategy,
)
from .models import ModelAdapter, create_adapter
from .storage import TrackDatabase
from .prompt_generator import PromptGenerator, PromptVariation
from .prompt_compiler import PromptCompiler, StructuredPrompt

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
        self.compiler = PromptCompiler(self.config)
        self._prompt_metadata: Dict[str, tuple] = {}  # prompt_text -> (canonical_id, tags_dict)
        self.config_path = config_path
        self.config_hash = self._calculate_config_hash()
        self._result_lock = threading.Lock()

        sentiment_mode = self.config.get("sentiment", {}).get("mode", "fast")
        if sentiment_mode != "off":
            self.sentiment_analyzer = SentimentAnalyzer(self.config)
            self.context_extractor = MentionContextExtractor(self.detector.brands)
        else:
            self.sentiment_analyzer = None
            self.context_extractor = None

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

        # Handle both old format (dict of category -> string list) and
        # new format (list of structured prompt entries from PromptCompiler)
        prompts_config = self.config.get("prompts", {})
        if isinstance(prompts_config, list):
            # New structured format: prompts is a list of dicts with canonical_id, prompts, tags
            structured_texts = []
            for entry in prompts_config:
                if isinstance(entry, dict) and "prompts" in entry:
                    for p in entry["prompts"]:
                        if isinstance(p, str) and p not in structured_texts:
                            structured_texts.append(p)
                elif isinstance(entry, str) and entry not in structured_texts:
                    structured_texts.append(entry)
            all_prompts["structured"] = structured_texts
        elif isinstance(prompts_config, dict):
            # Old format: dict of category -> list of strings
            for category, prompts in prompts_config.items():
                if isinstance(prompts, list):
                    all_prompts[category] = [p for p in prompts if isinstance(p, str)]

        # Add variations if enabled
        if enable_variations:
            base_prompts = []
            for prompts in all_prompts.values():
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

        # Load structured prompts for metadata lookup
        self._load_prompt_metadata()

        return all_prompts

    def _load_prompt_metadata(self) -> None:
        """Load structured prompt metadata from prompts.yaml.

        Populates self._prompt_metadata for prompt→(canonical_id, tags) lookup
        at query recording time.
        """
        # Find prompts.yaml path from config
        prompts_path = Path("configs/users/prompts.yaml")
        if not prompts_path.exists():
            return

        try:
            structured = self.compiler.load_prompts(str(prompts_path))
            if structured:
                self._prompt_metadata = self.compiler.build_prompt_lookup(structured)
        except Exception:
            # Non-fatal — prompts will run without metadata
            pass

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

        prompt_gen_config = self.config.get("tracking", {}).get("prompt_variations", {})
        enable_variations = prompt_gen_config.get("enabled", False)
        num_variations = prompt_gen_config.get("num_variations", 3)
        variation_strategy = prompt_gen_config.get("strategy", "semantic")

        auto_gen_config = self.config.get("tracking", {}).get("auto_prompt_generation", {})
        enable_auto_gen = auto_gen_config.get("enabled", False)
        auto_gen_per_brand = auto_gen_config.get("per_brand_prompts", 5)

        all_prompts = self._prepare_prompts(
            enable_variations,
            num_variations,
            variation_strategy,
            enable_auto_gen,
            auto_gen_per_brand,
        )

        adaptive_config = self.config.get("tracking", {}).get("adaptive_sampling", {})
        adaptive_enabled = adaptive_config.get("enabled", True)

        sentiment_mode = self.sentiment_analyzer.mode if self.sentiment_analyzer else "off"
        if sentiment_mode == "detailed":
            ci_strategy = SentimentCIStrategy()
        else:
            ci_strategy = None

        sampler = AdaptiveSampler(self.config) if adaptive_enabled else None
        if sampler and ci_strategy:
            sampler.ci_strategy = ci_strategy

        brands = [b["name"] for b in self.config.get("brands", [])]
        primary_brand = brands[0] if brands else "Unknown"
        all_brand_keywords = []
        for b in self.config.get("brands", []):
            all_brand_keywords.append(b["name"])
            for c in b.get("competitors", []):
                all_brand_keywords.append(c["name"])

        max_retries = self.config["tracking"].get("max_retries", 3)
        queries_per_prompt = self.config["tracking"]["queries_per_prompt"]

        if verbose:
            console.print(f"\n[bold]Starting visibility tracking run #{result.run_id}[/bold]")
            console.print(f"Config hash: {self.config_hash}")
            if adaptive_enabled and sampler:
                console.print(
                    f"Adaptive sampling ON: target CI width {sampler.target_ci_width}%, "
                    f"min {sampler.min_queries}, max {sampler.max_queries} queries per pair"
                )
                console.print(f"  → Convergence scope: {sampler.convergence_scope}")
            else:
                fixed_total = (
                    len(self.adapters)
                    * sum(len(p) for p in all_prompts.values())
                    * queries_per_prompt
                )
                console.print(
                    f"Fixed mode: {len(self.adapters)} models × {sum(len(p) for p in all_prompts.values())} "
                    f"prompts × {queries_per_prompt} queries = {fixed_total} total"
                )
            if enable_variations:
                console.print(f"  → Prompt variations enabled ({num_variations} per base prompt)")
            if enable_auto_gen:
                console.print(f"  → Auto-generation enabled ({auto_gen_per_brand} per brand)")

        health = self._health_check()
        enabled_models = [k for k, v in health.items() if v]

        if not enabled_models:
            raise RuntimeError("No models available. Check configuration and API keys.")

        if verbose:
            console.print(f"\n[bold]Enabled models:[/bold] {', '.join(enabled_models)}\n")

        if adaptive_enabled and sampler:
            self._run_adaptive(
                result,
                enabled_models,
                all_prompts,
                sampler,
                primary_brand,
                all_brand_keywords,
                max_retries,
                verbose,
                sentiment_mode,
            )
        else:
            self._run_fixed(
                result,
                enabled_models,
                all_prompts,
                queries_per_prompt,
                max_retries,
                verbose,
                sentiment_mode,
            )

        run_metadata = {}
        if sampler:
            status = sampler.get_status(primary_brand, all_brand_keywords)
            run_metadata["convergence"] = status
            if verbose:
                s = status["summary"]
                console.print(f"\n[bold]Convergence summary:[/bold]")
                console.print(f"  {s['converged_pairs']}/{s['total_pairs']} pairs converged")
                console.print(
                    f"  {s['total_queries']} queries used, ~{s['estimated_queries_saved']} saved vs fixed max"
                )

        if sentiment_mode == "fast" and self.sentiment_analyzer:
            self._run_post_batch_sentiment(result, run_metadata, verbose)

        result.completed_at = datetime.now(timezone.utc)
        self.db.complete_run(result.run_id, metadata=run_metadata)

        if verbose:
            self._print_summary(result)
            self._print_model_comparison(result.run_id)

        return result

    def _run_adaptive(
        self,
        result: RunResult,
        enabled_models: list,
        all_prompts: dict,
        sampler: AdaptiveSampler,
        primary_brand: str,
        all_brands: list,
        max_retries: int,
        verbose: bool,
        sentiment_mode: str = "fast",
    ):
        max_q = sampler.max_queries
        check_interval = sampler.check_interval

        # Pre-resolve model info once
        model_info = {}
        for model_key in enabled_models:
            parts = model_key.split(":", 1)
            model_info[model_key] = {
                "adapter": self.adapters[model_key],
                "provider": parts[0],
                "model_name": parts[1] if len(parts) > 1 else model_key,
            }

        with ThreadPoolExecutor(max_workers=len(enabled_models)) as executor:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Running adaptive queries...", total=None)

                for prompt_category, prompts in all_prompts.items():
                    for prompt in prompts:
                        # Track per-model query counts and convergence independently
                        model_queries = {m: 0 for m in enabled_models}
                        converged_models = set()

                        while len(converged_models) < len(enabled_models):
                            # Build work list: non-converged models that haven't hit max
                            work_items = []
                            for model_key in enabled_models:
                                if model_key in converged_models:
                                    continue
                                if model_queries[model_key] >= max_q:
                                    converged_models.add(model_key)
                                    continue
                                info = model_info[model_key]
                                work_items.append((model_key, info))

                            if not work_items:
                                break

                            # Submit all non-converged models in parallel
                            futures = {}
                            for model_key, info in work_items:
                                future = executor.submit(
                                    self._execute_query,
                                    info["adapter"],
                                    result,
                                    info["provider"],
                                    info["model_name"],
                                    prompt,
                                    max_retries,
                                    sentiment_mode,
                                )
                                futures[future] = (model_key, info["model_name"])

                            # Collect results
                            for future in as_completed(futures):
                                model_key, model_name = futures[future]
                                try:
                                    success, error_msg, mentions, last_sentiment = future.result()
                                except Exception as e:
                                    success, error_msg = False, str(e)
                                    mentions, last_sentiment = {}, {}

                                model_queries[model_key] += 1
                                result.total_queries += 1

                                if success and sampler:
                                    for brand in all_brands:
                                        if sentiment_mode == "detailed" and self.sentiment_analyzer:
                                            comp = last_sentiment.get(brand, {}).get(
                                                "composite", 0.0
                                            )
                                            if brand in mentions:
                                                sampler.record(model_name, prompt, brand, comp)
                                        else:
                                            mentioned = 1.0 if brand in mentions else 0.0
                                            sampler.record(model_name, prompt, brand, mentioned)

                                # Update progress
                                stats = sampler.get_stats(model_name, prompt, primary_brand)
                                ci_w = (
                                    f"{stats.ci_width:.1f}%" if stats and stats.ci_width else "N/A"
                                )
                                progress.update(
                                    task,
                                    description=(
                                        f"  {model_name} — {prompt[:40]}... | "
                                        f"{model_queries[model_key]} queries, CI width: {ci_w}"
                                    ),
                                )

                            # Check convergence for each model after the batch
                            for model_key in list(set(enabled_models) - converged_models):
                                info = model_info[model_key]
                                q = model_queries[model_key]
                                if q >= sampler.min_queries and q % check_interval == 0:
                                    if sampler.should_stop(
                                        info["model_name"], prompt, primary_brand, all_brands
                                    ):
                                        converged_models.add(model_key)
                                        if verbose:
                                            stats = sampler.get_stats(
                                                info["model_name"], prompt, primary_brand
                                            )
                                            ci_w = (
                                                f"{stats.ci_width:.1f}%"
                                                if stats and stats.ci_width
                                                else "N/A"
                                            )
                                            console.print(
                                                f"  [green]Converged: {info['model_name']} / "
                                                f"{prompt[:40]}... "
                                                f"after {q} queries (CI: {ci_w})[/green]"
                                            )

                            # Rate limit between query rounds
                            time.sleep(0.5)

    def _run_fixed(
        self,
        result: RunResult,
        enabled_models: list,
        all_prompts: dict,
        queries_per_prompt: int,
        max_retries: int,
        verbose: bool,
        sentiment_mode: str = "fast",
    ):
        total_queries = (
            len(enabled_models) * sum(len(p) for p in all_prompts.values()) * queries_per_prompt
        )

        # Pre-resolve model info once (avoids repeated string splitting in threads)
        model_info = {}
        for model_key in enabled_models:
            parts = model_key.split(":", 1)
            model_info[model_key] = {
                "adapter": self.adapters[model_key],
                "provider": parts[0],
                "model_name": parts[1] if len(parts) > 1 else model_key,
            }

        with ThreadPoolExecutor(max_workers=len(enabled_models)) as executor:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Running queries...", total=total_queries)

                for prompt_category, prompts in all_prompts.items():
                    for prompt in prompts:
                        for query_num in range(queries_per_prompt):
                            # Submit all models in parallel for this (prompt, query_num)
                            futures = {}
                            for model_key in enabled_models:
                                info = model_info[model_key]
                                future = executor.submit(
                                    self._execute_query,
                                    info["adapter"],
                                    result,
                                    info["provider"],
                                    info["model_name"],
                                    prompt,
                                    max_retries,
                                    sentiment_mode,
                                )
                                futures[future] = info["model_name"]

                            # Collect results as they complete
                            for future in as_completed(futures):
                                model_name = futures[future]
                                try:
                                    success, error_msg, _mentions, _sentiment = future.result()
                                except Exception as e:
                                    success, error_msg = False, str(e)

                                if not success:
                                    result.errors.append(
                                        f"{model_name}: {prompt[:50]}... - {error_msg}"
                                    )
                                result.total_queries += 1
                                progress.update(task, advance=1)

                            # Rate limit between query rounds
                            time.sleep(0.5)

    def _execute_query(
        self,
        adapter,
        result: RunResult,
        provider: str,
        model_name: str,
        prompt: str,
        max_retries: int,
        sentiment_mode: str = "fast",
    ) -> tuple:
        success = False
        error_msg = None
        mentions = {}
        last_sentiment = {}
        for attempt in range(max_retries):
            try:
                response = adapter.query(prompt)
                mentions = self.detector.detect(response)

                enriched_mentions = mentions.copy()
                if sentiment_mode == "detailed" and self.sentiment_analyzer:
                    last_sentiment = {}
                    for brand in mentions:
                        sentiment = self.sentiment_analyzer.analyze_detailed(brand, response)
                        enriched_mentions[brand] = {
                            "count": mentions[brand],
                            "sentiment": {
                                "prominence": sentiment.prominence,
                                "sentiment": sentiment.sentiment,
                                "composite": sentiment.composite_score,
                            },
                        }
                        last_sentiment[brand] = {
                            "prominence": sentiment.prominence,
                            "sentiment": sentiment.sentiment,
                            "composite": sentiment.composite_score,
                        }

                # Resolve prompt metadata (canonical_id, tags) if available
                canonical_id = ""
                prompt_tags = "{}"
                if prompt in self._prompt_metadata:
                    cid, tags = self._prompt_metadata[prompt]
                    canonical_id = cid
                    prompt_tags = json.dumps(tags.to_dict() if hasattr(tags, "to_dict") else tags)

                self.db.record_query(
                    run_id=result.run_id,
                    model_provider=provider,
                    model_name=model_name,
                    prompt=prompt,
                    response_text=response,
                    mentions=enriched_mentions,
                    prompt_tags=prompt_tags,
                    canonical_id=canonical_id,
                )
                with self._result_lock:
                    result.successful_queries += 1
                success = True
                break
            except Exception as e:
                error_msg = str(e)
                time.sleep(2**attempt)

        if not success:
            with self._result_lock:
                result.failed_queries += 1

        return success, error_msg, mentions, last_sentiment

    def _run_post_batch_sentiment(
        self, result: RunResult, run_metadata: dict, verbose: bool
    ) -> None:
        """Post-batch fast mode: extract contexts and run 1 LLM call per brand."""
        records = self.db.get_by_run(result.run_id)
        if not records:
            return

        brand_responses = defaultdict(list)
        for record in records:
            mentions = json.loads(record.get("mentions_json") or "{}")
            response_text = record.get("response_text", "")
            for brand in mentions:
                if response_text:
                    brand_responses[brand].append(
                        {"record_id": record["id"], "response_text": response_text}
                    )

        if not brand_responses:
            return

        if verbose:
            console.print("\n[bold]Running post-batch sentiment analysis (fast mode)...[/bold]")

        sentiment_data = {}
        for brand, responses in brand_responses.items():
            all_contexts = []
            for resp in responses:
                contexts = self.context_extractor.extract(resp["response_text"], brand)
                for ctx in contexts:
                    all_contexts.append(ctx)

            if not all_contexts:
                continue

            sentiment_result = self.sentiment_analyzer.analyze_fast(brand, all_contexts)
            sentiment_data[brand] = {
                "prominence": round(sentiment_result.prominence, 3),
                "sentiment": round(sentiment_result.sentiment, 3),
                "composite": round(sentiment_result.composite_score, 3),
                "sample_size": len(all_contexts),
                "summary": sentiment_result.summary,
            }

            if verbose:
                comp = sentiment_result.composite_score
                color = "green" if comp >= 0.3 else "red" if comp <= -0.3 else "yellow"
                console.print(
                    f"  [{color}]{brand}: composite={comp:+.3f} "
                    f"(prominence={sentiment_result.prominence:.2f}, "
                    f"sentiment={sentiment_result.sentiment:+.2f})[/{color}]"
                )

        if sentiment_data:
            run_metadata["sentiment"] = sentiment_data

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

    def _print_model_comparison(self, run_id: int) -> None:
        """Print side-by-side model comparison table for a specific run."""
        records = self.db.get_by_run(run_id)

        if not records:
            return

        # Aggregate by model
        model_stats: Dict[str, Dict[str, int]] = {}
        for record in records:
            model_name = record["model_name"]
            mentions = json.loads(record.get("mentions_json") or "{}")

            if model_name not in model_stats:
                model_stats[model_name] = {"queries": 0, "mentions": 0}

            model_stats[model_name]["queries"] += 1
            # Count if any brand was mentioned
            if mentions:
                model_stats[model_name]["mentions"] += 1

        if len(model_stats) < 2:
            return  # No comparison needed for single model

        from rich.table import Table

        table = Table(title=f"Model Comparison \u2014 Run #{run_id}")
        table.add_column("Model", style="cyan")
        table.add_column("Mention Rate", style="green", justify="right")
        table.add_column("Queries", style="blue", justify="right")
        table.add_column("Mentions", style="magenta", justify="right")
        table.add_column("Delta", style="yellow", justify="right")

        # Sort by mention rate descending
        sorted_models = sorted(
            model_stats.items(),
            key=lambda x: x[1]["mentions"] / max(x[1]["queries"], 1),
            reverse=True,
        )

        best_rate = None
        for model_name, stats in sorted_models:
            rate = (stats["mentions"] / stats["queries"] * 100) if stats["queries"] > 0 else 0

            if best_rate is None:
                best_rate = rate
                delta_str = "\u2014"
            else:
                delta = rate - best_rate
                delta_str = f"{delta:+.1f}%"

            table.add_row(
                model_name,
                f"{rate:.1f}%",
                str(stats["queries"]),
                str(stats["mentions"]),
                delta_str,
            )

        console.print(table)

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
