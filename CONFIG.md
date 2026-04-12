# Configuration Guide

## Quick Reference

### Change Query Model
Edit `configs/default.yaml`:
```yaml
models:
  - provider: "ollama"
    model: "gemma4:e2b"  # Default model
    enabled: true
```

### Change Query Count (for statistical significance)
```yaml
tracking:
  queries_per_prompt: 50  # Run each prompt 50 times
```

### Enable Multiple Models (parallel comparison)
```yaml
models:
  - provider: "ollama"
    model: "gemma4:e2b"
    enabled: true
    description: "Default"
    
  - provider: "ollama"
    model: "nemotron-3-nano:4b"
    enabled: true
    description: "Fast comparison"
```

Both models will run independently, allowing you to compare results.

## Full Configuration Options

### Brand Configuration
```yaml
brands:
  - name: "Your Brand"
    keywords: ["keyword1", "keyword2"]  # Case-insensitive matching
    competitors:
      - name: "Competitor 1"
        keywords: ["comp1", "comp-1"]
```

### Model Configuration
| Field | Description | Default |
|-------|-------------|---------|
| `provider` | `ollama`, `openai`, `anthropic`, `huggingface` | Required |
| `model` | Model name | Required |
| `endpoint` | Ollama URL (for Ollama only) | `http://localhost:11434` |
| `enabled` | Enable/disable model | `true` |
| `temperature` | Generation temperature | `0.7` |
| `api_key_env` | Env var for API key (OpenAI/Anthropic) | Required for cloud APIs |

### Tracking Settings
| Field | Description | Default |
|-------|-------------|---------|
| `queries_per_prompt` | Repeat each prompt N times for variance | `10` |
| `max_retries` | Retry failed queries | `3` |
| `detection_method` | `keyword`, `llm`, or `both` | `both` |
| `llm_detection.model` | Model for LLM-based detection | `gemma4:e2b` |

### Analysis LLM
| Field | Description | Default |
|-------|-------------|---------|
| `analysis.provider` | Provider for analysis tasks (detection, sentiment) | `ollama` |
| `analysis.model` | Model for analysis (separate from test models) | `gemma4:e2b` |
| `analysis.temperature` | Temperature for analysis calls | `0.1` |
| `analysis.endpoint` | Custom endpoint (Ollama) | `http://localhost:11434` |

### Sentiment Analysis
| Field | Description | Default |
|-------|-------------|---------|
| `sentiment.mode` | `fast` (post-batch), `detailed` (per-query), or `off` | `fast` |

**Fast mode** (default): After the tracking run completes, runs 1 LLM call per brand to assess overall sentiment. Cheap, stored in run metadata.

**Detailed mode**: Runs sentiment analysis on every query response using the analysis LLM. Tracks convergence on composite score (prominence × sentiment). More LLM calls but analysis uses the free local model.

### Prompts

The `configs/users/prompts.yaml` file supports two formats:

#### Old format (flat strings, still accepted)

```yaml
brand_mentions:
  - "What are the best athletic footwear brands for running?"
  - "Compare Nike vs Adidas for basketball shoes"
```

#### New format (structured with classification tags)

```yaml
prompts:
  - canonical_id: "cmp_run_001"
    prompts:
      - "What are the best athletic footwear brands for running?"
      - "Which running shoe brands are considered the best?"
      - "Top athletic footwear options for runners in 2026?"
    tags:
      intent: comparison
      purchase_stage: awareness
      topic: running
      query_type: unbranded

  - canonical_id: "rec_bball_002"
    prompts:
      - "Recommend a Nike basketball shoe for outdoor courts"
      - "What Nike basketball shoe would you suggest for outdoor play?"
    tags:
      intent: recommendation
      purchase_stage: decision
      topic: basketball
      query_type: branded
```

**Tag dimensions:**

| Dimension | Valid Values |
|---|---|
| `intent` | `comparison`, `recommendation`, `informational`, `purchase_intent`, `awareness` |
| `purchase_stage` | `awareness`, `consideration`, `decision`, `retention` |
| `topic` | Free-form (e.g., `running`, `basketball`, `sustainability`) |
| `query_type` | `branded`, `unbranded` (auto-detected if omitted) |

**Canonical IDs** follow the format `{intent_abbrev}_{topic_abbrev}_{sequence}` (e.g., `cmp_run_001`).

**Generate with the CLI:**
```bash
pvt prompts generate --brand Nike --keywords running,basketball,sustainability
```

**Classify existing prompts:**
```bash
pvt prompts classify --brand Nike
```

You can also merge prompts from files:
```yaml
prompts_from_files:
  - configs/prompts/brand.yaml
  - configs/prompts/topic.yaml
```

## Statistical Significance Guide

For meaningful statistical results:

| Queries/Prompt | Confidence Interval (@ 95%) | Use Case |
|----------------|----------------------------|----------|
| 10 | ±30% | Quick testing |
| 30 | ±17% | Development |
| 100 | ±10% | Production analysis |
| 500+ | ±4% | Research grade |

Example for production:
```yaml
tracking:
  queries_per_prompt: 100
```

## CLI Model Selection

Override or add models at runtime without editing config files:

```bash
# Run only a specific model (overrides config)
pvt run --model-only ollama:gemma4:e2b

# Add a model alongside configured models
pvt run --model ollama:nemotron-3-nano:4b

# Add multiple models
pvt run --model ollama:nemotron-3-nano:4b --model openai:gpt-4o

# Combine with other flags
pvt run --model-only ollama:gemma4:e2b --enable-variations --verbose
```

Format: `provider:model_name` (e.g., `ollama:gemma4:e2b`, `openai:gpt-4o`, `anthropic:claude-3-sonnet-20240229`).

## Sentiment Analysis

Enable sentiment detection to measure how brands are portrayed in LLM responses, not just whether they're mentioned.

### Fast mode (default)

```bash
# Post-batch sentiment — 1 LLM call per brand after the run completes
pvt run --sentiment-mode fast
```

```yaml
# Or in config:
sentiment:
  mode: "fast"
```

Results are stored in run metadata and displayed in the Sentiment tab.

### Detailed mode

```bash
# Per-query sentiment — analyzes every response using the analysis LLM
pvt run --sentiment-mode detailed
```

```bash
# Use a different analysis model
pvt run --sentiment-mode detailed --analysis-model ollama:nemotron-3-nano:4b
```

Detailed mode provides per-response composite scores (prominence × sentiment, range -1 to +1) and tracks convergence. The analysis LLM is separate from the test model, so analysis calls are free when using a local model.

### Composite Score

`composite = prominence × sentiment`

- **Prominence** (0-1): How prominently the brand is featured (position, frequency)
- **Sentiment** (-1 to +1): Positive, neutral, or negative portrayal
- **Composite** (-1 to +1): Combined score used for convergence tracking in detailed mode

Dashboard color coding: Green (+0.3 to +1.0), Yellow (-0.3 to +0.3), Red (-1.0 to -0.3).

## Using Fast Models (Nemotron example)

For rapid iteration, use a smaller, faster model:

```yaml
models:
  - provider: "ollama"
    model: "nemotron-3-nano:4b"  # Fast model (~1-2s/query)
    enabled: true
    description: "Fast iteration"
```

Recommended fast model settings:
```yaml
tracking:
  queries_per_prompt: 50    # More queries for same time
  temperature: 0.7
```

Production with quality:
```yaml
models:
  - provider: "ollama"
    model: "qwen3.5:122b"  # High quality (~15-30s/query)
    enabled: true
```

## Environment Variables

Copy `.env.example` to `.env`:
```bash
OPENAI_API_KEY=sk-...        # For OpenAI models
ANTHROPIC_API_KEY=...        # For Anthropic models
OLLAMA_HOST=http://localhost:11434  # Custom Ollama endpoint
```

## Export Configuration
```bash
# View current config
pvt config

# Export configuration as JSON
pvt config --json > config.json
```

## Segment Analysis

When prompts are classified with tags (via `pvt prompts generate` or `pvt prompts classify`), visibility data can be segmented by any dimension.

### API Endpoints

| Endpoint | Description |
|---|---|
| `GET /visibility-by-segment?brand=Nike&dimension=intent&days=30` | Mention rate per intent value with CIs |
| `GET /segment-comparison?brands=Nike,Adidas&dimension=purchase_stage&days=30` | Side-by-side mention rates per brand per stage |
| `GET /variation-drift?canonical_id=cmp_run_001&brand=Nike` | Per-variation mention rates for a canonical prompt |

### Dashboard

The Segments tab in the web dashboard provides:
- Dimension picker (Intent / Purchase Stage / Topic / Query Type)
- Grouped bar chart with confidence intervals
- Segment breakdown table
- Empty state with CLI instructions when no tagged data exists
