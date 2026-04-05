# AI Visibility Tracker — Implementation Brief

**Project Goal:** Build a production-ready open-source tool that proves tools like Profound can be built in a weekend. Track brand mentions in AI-generated responses across multiple models, visualize trends, and export data.

---

## Context & Philosophy

This tool exists to demonstrate that "AI visibility tracking" is not magic — it's just querying LLMs and counting results. Key principles:

- **Honest data:** Show variance, standard deviation, model differences. No fake "rankings."
- **Configurable:** Users define their brands, prompts, models, API keys.
- **Multi-model:** Run the same prompts across different LLMs to expose non-determinism.
- **Open source:** Clean architecture, MIT license, zero vendor lock-in.
- **Functional:** Not a demo — genuinely useful for tracking brand mentions.

---

## Target Environment

Shaun will implement this using:
- **Opencode** (Claude Code-like environment) running in PyCharm
- **Qwen3.5:122b** running locally via Ollama
- **Local development** (not Pyodide) — full pip install available
- **Optional:** Next.js/React frontend later, start with CLI + Streamlit

---

## Core Features (MVP)

### Phase 1: Core Tracking Engine
- Query multiple AI models with configured prompts
- Detect brand mentions in responses (simple keyword matching + optional LLM-based extraction)
- Store results in SQLite database
- Export to CSV/JSON

### Phase 2: Scheduling & Automation
- Cron-like scheduling (run every X hours)
- Run history tracking
- Alert thresholds (optional)

### Phase 3: Dashboard & Visualization
- Streamlit dashboard (MVP) or Next.js (Phase 2)
- Trend charts (mention rate over time)
- Model comparison (variance analysis)
- Brand/competitor breakdown

### Phase 4: Advanced Features
- LLM-based mention detection (more nuanced than keyword matching)
- Sentiment analysis (positive/negative/neutral mentions)
- Prompt library sharing (community prompts)
- API endpoint for external integrations

---

## File Structure

```
prompt-visibility-tracker/
├── pyproject.toml                    # Project config, dependencies
├── README.md                         # Installation, usage, philosophy
├── LICENSE                           # MIT License
│
├── .env.example                      # Example environment variables
├── .gitignore
│
├── configs/
│   ├── default.yaml                  # Main configuration file
│   └── prompts/
│       ├── brand.yaml               # Brand mention prompts
│       ├── topic.yaml               # Industry topic prompts
│       └── custom.yaml              # User custom prompts
│
├── src/
│   ├── __init__.py
│   │
│   ├── tracker.py                    # Core engine: orchestrate queries
│   │   - VisibilityTracker class
│   │   - Run batch queries
│   │   - Aggregate results
│   │
│   ├── models.py                     # Model adapters
│   │   - ModelAdapter base class
│   │   - OpenAIAdapter
│   │   - AnthropicAdapter
│   │   - OllamaAdapter
│   │   - HuggingFaceAdapter
│   │
│   ├── storage.py                    # Database + export
│   │   - TrackDatabase class
│   │   - SQLite operations
│   │   - CSV/JSON export
│   │
│   ├── analyzer.py                   # Data analysis
│   │   - Mention detection (keyword + LLM)
│   │   - Variance calculation
│   │   - Trend analysis
│   │
│   └── dashboard.py                  # Streamlit app
│       - Dashboard UI
│       - Charts, tables, exports
│
├── data/
│   └── tracks.db                     # SQLite database (auto-created)
│
├── logs/
│   └── tracker.log                   # Run logs
│
└── tests/
    ├── test_tracker.py
    ├── test_models.py
    └── test_analyzer.py
```

---

## Configuration Schema

### configs/default.yaml
```yaml
# Brand Configuration
brands:
  - name: "Wayfinder AI"
    keywords: ["Wayfinder", "Wayfinder AI", "WayfinderAI"]
    # Optional: competitors to track alongside
    competitors:
      - name: "Compass"
        keywords: ["Compass"]
      - name: "Mapper"
        keywords: ["Mapper"]

# Model Configuration (can use multiple)
models:
  - provider: "openai"
    model: "gpt-4o"
    api_key_env: "OPENAI_API_KEY"
    enabled: true
    temperature: 0.7
    
  - provider: "anthropic"
    model: "claude-3-sonnet-20240229"
    api_key_env: "ANTHROPIC_API_KEY"
    enabled: true
    temperature: 0.7
    
  - provider: "ollama"
    model: "qwen3.5:122b"
    endpoint: "http://localhost:11434"
    enabled: true
    temperature: 0.7

# Prompts
prompts:
  brand_mentions:
    - "What are the best AI SEO tools available in 2024?"
    - "Which platforms offer AI visibility tracking?"
    - "Name companies that do AI navigation audits"
    - "What is the leading answer engine optimisation platform?"
  
  topic_authority:
    - "How do I optimize my website for AI agents?"
    - "What is answer engine optimisation?"
    - "How do I audit my site for AI discoverability?"

# Tracking Settings
tracking:
  # Run each prompt N times to capture model variance
  queries_per_prompt: 10
  
  # Schedule: how often to run the batch
  run_interval_hours: 24
  
  # Keep this much history
  max_history_days: 90
  
  # Mention detection method
  detection_method: "keyword"  # or "llm" for smarter extraction
  
  # Optional: LLM-based detection config
  llm_detection:
    model: "ollama"
    prompt_template: |
      Analyze this response and extract any brand mentions.
      Response: {response}
      Return as JSON: {"mentions": ["brand1", "brand2"]}

# Output
output:
  database_path: "data/tracks.db"
  export_format: ["csv", "json"]
  logs_dir: "logs"
```

---

## Implementation Tasks (Weekend Schedule)

### Saturday: Core Engine (4-6 hours)

**Task 1: Project Setup** (30 mins)
- Create project structure
- Write pyproject.toml with dependencies
- Set up environment variables (.env.example)
- Initialize git repo

**Task 2: Model Adapters** (1.5 hours)
- Create src/models.py
- Implement base ModelAdapter class
- Implement OllamaAdapter (local testing)
- Implement OpenAIAdapter (production)
- Add health_check() method to each
- Test against local Ollama instance

**Task 3: Storage Layer** (1 hour)
- Create src/storage.py
- SQLite schema design
- CRUD operations for visibility_records
- CSV/JSON export functions
- Test with sample data

**Task 4: Core Tracker** (1.5 hours)
- Create src/tracker.py
- VisibilityTracker class
- Batch query orchestration
- Progress logging
- Error handling (retry failed queries)

**Task 5: Analyzer** (1 hour)
- Create src/analyzer.py
- Keyword-based mention detection
- LLM-based mention detection (optional)
- Variance/standard deviation calculation
- Export aggregation functions

### Sunday: Dashboard & Polish (4-6 hours)

**Task 6: Streamlit Dashboard** (2 hours)
- Create src/dashboard.py
- Load data from SQLite
- KPI cards (brands tracked, query count, mention rate)
- Trend chart (mention rate over time)
- Model comparison table
- Export buttons
- Test dashboard locally

**Task 7: CLI Interface** (1 hour)
- Create main.py
- Click-based CLI
- Commands: `run`, `dashboard`, `export`, `config`
- Progress bars for long-running batches

**Task 8: Configuration & Prompts** (1 hour)
- Finalize configs/default.yaml
- Create configs/prompts/*.yaml files
- Add validation for config loading
- Config examples for common use cases

**Task 9: Documentation** (1 hour)
- Write comprehensive README.md
- Installation guide
- Configuration guide
- Usage examples
- Philosophy section (why this exists)
- Contributing guide

**Task 10: Testing & Polish** (1 hour)
- Run full end-to-end test
- Fix bugs
- Add error messages
- Write tests for critical paths
- Clean up code comments

---

## Technical Decisions to Make Early

1. **Mention Detection:**
   - Keyword matching (fast, simple, false positives)
   - LLM-based extraction (slower, smarter, costs API calls)
   - Hybrid approach: keyword first, LLM for confirmation

2. **Response Storage:**
   - Store full response text (enables later analysis)
   - Or store only boolean + metadata (smaller DB)
   - Recommendation: store full response (SQLite handles it fine)

3. **Scheduling:**
   - Cron-based (system cron or APScheduler)
   - Or manual trigger + user runs externally
   - Recommendation: APScheduler for simplicity

4. **Frontend:**
   - Start with Streamlit (single file, zero DevOps)
   - Phase 2: Next.js if needed (better UX, more control)

5. **Deployment:**
   - Docker Compose for one-command deploy
   - Or just "pip install + run" simplicity
   - Recommendation: both (Docker optional)

---

## Example Usage

```bash
# Install
pip install -e .

# Configure
mv .env.example .env
# Edit .env with API keys

# Run initial batch
python main.py run --config configs/default.yaml

# Launch dashboard
python main.py dashboard

# Export data
python main.py export --format csv --output results.csv

# Run with custom prompts
python main.py run --prompts configs/prompts/custom.yaml
```

---

## Key Design Patterns

1. **Adapter Pattern for Models:** Easy to add new LLM providers
2. **Repository Pattern for Storage:** Easy to swap SQLite for PostgreSQL
3. **Config-Driven:** No code changes needed to add brands/prompts
4. **Functional Core, Imperative Shell:** Pure functions for analysis, I/O isolated
5. **Progressive Disclosure:** Simple CLI first, dashboard second, advanced features later

---

## Anti-Patterns to Avoid

1. **"AI Ranking" Scores:** Don't calculate fake rankings. Show raw data.
2. **Over-Marketing:** Be honest about what this measures (mentions, not performance).
3. **Vendor Lock-in:** No proprietary APIs required. Local models work fine.
4. **Data Opacity:** Show the raw response text, not just "mentioned: true/false".
5. **False Precision:** Report variance and standard deviation prominently.

---

## Success Criteria

By end of weekend:
- ✅ Can run `python main.py run` and track 10 brands across 3 models
- ✅ Dashboard shows trends, model variance, mention rates
- ✅ Export to CSV/JSON works
- ✅ README is clear enough for non-technical users
- ✅ Code is clean enough to open-source (tests, docs, license)

---

## Future Enhancements (Post-Weekend)

- Next.js frontend (better UX than Streamlit)
- Webhook alerts when brand mentioned/not mentioned
- Team collaboration (multiple users, shared dashboards)
- API for external integrations
- Community prompt marketplace
- Integration with Wayfinder Compass/Mapper for combined insights

---

## Notes for Opencode

When implementing:

1. **Start with OllamaAdapter** — Shaun has Qwen3.5:122b running locally
2. **Test incrementally** — Get each adapter working before adding more
3. **Error handling matters** — API failures should retry gracefully
4. **Progress logging** — Long batches should show progress
5. **Code comments** — Future self (and open-source contributors) need to understand design decisions

---

## Contact & Context

- **Project Owner:** Shaun (Wayfinder AI)
- **Context:** Proving AI visibility tools are simple enough to build in a weekend
- **Philosophy:** "I'd rather build tools for the thing that actually matters, can AI even access your content, than make prompt tracker number 459 because the market says that's what sells."
- **Related Work:** Profound ($96M raised), Peec AI, Otterly AI — all selling "AI visibility" dashboards
- **Differentiation:** This tool is open-source, honest about limitations, and focuses on data transparency over "rankings."

---

Ready to start implementation. Copy this entire brief into Opencode and begin with **Task 1: Project Setup**.
