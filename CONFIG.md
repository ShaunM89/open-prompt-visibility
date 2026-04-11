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
```yaml
prompts:
  category_name:
    - "Query 1"
    - "Query 2"
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
