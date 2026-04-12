# AI Visibility Tracker

Track how often AI chatbots mention your brand. Query multiple LLMs with test prompts, detect brand mentions in responses, and measure your visibility with statistical confidence.

## What It Does

When someone asks ChatGPT, Claude, or a local model "What are the best running shoes?", does your brand get mentioned? This tool answers that question systematically:

1. **Sends test prompts** to one or more LLMs (Ollama, OpenAI, Anthropic, HuggingFace)
2. **Detects brand mentions** using keyword matching and/or LLM-based analysis
3. **Calculates visibility scores** with Wilson confidence intervals
4. **Compares against competitors** to see where you stand
5. **Tracks trends over time** to see if visibility is improving
6. **Segments visibility** by intent, purchase stage, topic, and query type

## Key Features

- **Multi-model support** -- query Ollama (local), OpenAI, Anthropic, and HuggingFace from one config
- **Statistical analysis** -- confidence intervals, variance analysis, anomaly detection
- **Sentiment detection** -- analyze how brands are portrayed (positive/neutral/negative) with decoupled analysis LLM
- **Adaptive sampling** -- automatically stop querying when confidence intervals narrow enough
- **Structured prompt sets** -- generate and classify prompts across 4 dimensions (intent, purchase stage, topic, query type) with phrasing variations grouped under canonical IDs
- **Segmented visibility analysis** -- see how visibility differs by intent, topic, purchase stage, and branded vs unbranded queries
- **CLI + Web Dashboard** -- command-line interface and Next.js dashboard with Segments tab
- **SQLite storage** -- all results stored locally, exportable to CSV/JSON

## Prerequisites

- **Python 3.9+** -- [python.org/downloads](https://www.python.org/downloads/)
- **Ollama** (recommended) -- [ollama.com/download](https://ollama.com/download)
- **Node.js 18+** (optional, for the web dashboard) -- [nodejs.org](https://nodejs.org/)

## Quick Start

### 1. Install

```bash
git clone https://github.com/ShaunM89/open-prompt-visibility.git
cd open-prompt-visibility
pip install -e .
```

### 2. Set up Ollama

```bash
# Install Ollama from https://ollama.com/download, then:
ollama pull gemma4:e2b
```

### 3. Configure your brands

Edit `configs/users/brands.yaml` with your brand and competitors:

```yaml
brands:
  - name: "YourBrand"
    keywords: ["YourBrand", "your brand"]
    competitors:
      - name: "Competitor1"
        keywords: ["Competitor1"]
      - name: "Competitor2"
        keywords: ["Competitor2"]
```

### 4. Generate a structured prompt set

```bash
# Generate 50 classified prompts across your brand's topics
pvt prompts generate --brand YourBrand --keywords keyword1,keyword2,keyword3
```

This creates a structured `configs/users/prompts.yaml` with prompts tagged by intent, purchase stage, topic, and query type. Each prompt gets 2-3 phrasing variations for robust testing.

### 5. Run tracking

```bash
pvt run --config configs/default.yaml
```

### 6. View results

```bash
# View brand trends with confidence intervals
pvt trends "YourBrand" --days 30 --ci 95

# View database statistics
pvt stats

# Export results
pvt export --format csv --output results.csv
```

## CLI Reference

### Tracking Commands

| Command | Description |
|---------|-------------|
| `pvt run` | Run a tracking batch across all configured models |
| `pvt run --model-only ollama:gemma4:e2b` | Run with only the specified model |
| `pvt run --model ollama:gemma4:e2b` | Add a model alongside configured models |
| `pvt run --enable-variations` | Run with auto-generated prompt variations |
| `pvt run --enable-auto-gen` | Run with auto-generated brand prompts |
| `pvt run --sentiment-mode fast` | Run with post-batch sentiment analysis |
| `pvt run --sentiment-mode detailed` | Run with per-query sentiment analysis |
| `pvt run --analysis-model ollama:gemma4:e2b` | Override the analysis LLM |
| `pvt run --target-ci-width 15` | Set adaptive sampling CI target |
| `pvt stats` | Show database statistics |
| `pvt trends "Brand"` | Show mention trends with confidence intervals |
| `pvt export -f csv -o out.csv` | Export results to CSV or JSON |
| `pvt config` | Display the active configuration |
| `pvt serve` | Start the API server (for the web dashboard) |

### Prompt Management Commands

| Command | Description |
|---------|-------------|
| `pvt prompts generate --brand Nike --keywords running,basketball` | Generate a classified prompt set (50 prompts) via LLM |
| `pvt prompts generate --brand Nike --keywords running --num-prompts 100` | Generate more prompts |
| `pvt prompts classify --brand Nike` | Classify existing untagged prompts via LLM |
| `pvt prompts list` | Display current prompt set with tags and variation counts |
| `pvt prompts list --filter-intent comparison` | Filter by intent type |
| `pvt prompts list --filter-topic running` | Filter by topic |
| `pvt prompts validate` | Check all prompts have complete tags and valid IDs |

## Web Dashboard

The project includes a Next.js dashboard for visual analysis.

### Setup

```bash
# Terminal 1: Start the API server
pvt serve

# Terminal 2: Start the dashboard
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the dashboard.

The dashboard provides:
- Visibility score with confidence intervals
- Competitor comparison charts
- Paginated prompt results with filtering
- Run history with success rates
- Statistical summary with anomaly detection
- Sentiment analysis with color-coded brand cards
- **Segments tab** -- visibility by intent, purchase stage, topic, and query type with drill-down

## Configuration

The tool uses YAML configuration files in `configs/`:

- `configs/default.yaml` -- main config entry point
- `configs/tool/config.yaml` -- model settings, tracking parameters, detection method
- `configs/users/brands.yaml` -- your brands and competitors
- `configs/users/prompts.yaml` -- structured test prompts (generated by `pvt prompts generate`)

See [CONFIG.md](CONFIG.md) for the full configuration reference.

### Environment Variables

For cloud LLM providers, set API keys in a `.env` file (see `.env.example`):

```bash
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=your-key
OLLAMA_HOST=http://localhost:11434  # optional, defaults to localhost
```

## Prompt Classification

Prompts are classified across 4 dimensions for segmented visibility analysis:

| Dimension | Values | Source |
|---|---|---|
| **Intent** | `comparison`, `recommendation`, `informational`, `purchase_intent`, `awareness` | LLM-classified or generated |
| **Purchase Stage** | `awareness`, `consideration`, `decision`, `retention` | LLM-classified or generated |
| **Topic** | Free-form from brand keywords (e.g. `running`, `basketball`, `sustainability`) | Derived from input keywords |
| **Query Type** | `branded`, `unbranded` | Auto-detected (does the prompt contain a brand name?) |

### Structured prompts.yaml Format

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
```

The first prompt is the canonical version; the rest are phrasing variations. All variations share the same `canonical_id` and tags, enabling grouped analysis.

### Typical Workflow

```bash
# 1. Generate classified prompts
pvt prompts generate --brand Nike --keywords running,basketball,sustainability --num-prompts 50

# 2. Review and optionally edit
pvt prompts list

# 3. Validate completeness
pvt prompts validate

# 4. Run a tracking batch
pvt run --verbose

# 5. Analyze segments via API
# GET /visibility-by-segment?brand=Nike&dimension=intent&days=30
```

## How It Works

```
configs/ --> VisibilityTracker --> ModelAdapters (Ollama/OpenAI/Anthropic/HF)
                   |                        |
                   v                        v
           PromptCompiler            LLM Responses
                   |                        |
                   v                        v
            MentionDetector -----> TrackDatabase (SQLite)
                                           |
                                           v
                                    AnalyticsEngine --> CLI / API / Dashboard
```

1. **PromptCompiler** generates and classifies structured prompt sets with canonical IDs and variations
2. **VisibilityTracker** loads config and orchestrates the tracking run
3. **ModelAdapters** send prompts to configured LLMs
4. **MentionDetector** scans responses for brand mentions (keyword + LLM hybrid)
5. **SentimentAnalyzer** assesses how brands are portrayed using a separate analysis LLM
6. **AdaptiveSampler** stops querying when confidence intervals converge
7. **TrackDatabase** stores all results with prompt tags and canonical IDs in SQLite
8. **AnalyticsEngine** calculates statistics, confidence intervals, anomalies, and segment analysis
9. Results are surfaced via CLI commands, FastAPI endpoints, or the Next.js dashboard

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.

## License

MIT -- see [LICENSE](LICENSE) for details.
