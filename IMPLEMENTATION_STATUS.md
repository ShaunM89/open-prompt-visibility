# AI Visibility Tracker - Implementation Status & Next Steps

**Created:** April 5, 2026  
**Last Updated:** April 5, 2026  
**Status:** Backend Complete → Frontend Priority  
**Priority:** High

---

## Current Status Summary

### ✅ Completed (Backend)

| Feature | Implementation | Status |
|---------|---------------|--------|
| **Prompt Variations** | `src/prompt_generator.py` - `generate_variations()` | ✅ Ready |
| **Auto-Generated Prompts** | `src/prompt_generator.py` - `generate_domain_prompts()` | ✅ Ready |
| **CLI Flags** | `main.py` - `--enable-variations`, `--enable-auto-gen` | ✅ Ready |
| **Statistical Analysis** | `src/analyzer.py` - CI, variance, anomalies | ✅ Ready |
| **Run Tracking** | `src/tracker.py` - Integrated prompt prep | ✅ Ready |
| **Testing** | 7 runs, 79 queries executed | ✅ Validated |

### 📊 Latest Run Results

```
Total Runs:     7
Total Queries:  79
Unique Models:  2 (nemotron-3-nano, qwen3.5)
Mentions:       78 detected (98.7% success rate)
```

### 🏗️ Architecture Overview

```
Backend (Complete):
├── src/tracker.py       # Orchestrates runs, integrates prompt gen
├── src/prompt_generator.py  # Variations + auto-generation (289 lines)
├── src/analyzer.py      # Statistics engine (883 lines)
├── src/storage.py       # Database operations
├── src/models.py        # LLM adapters
└── main.py              # CLI with new flags

Frontend (Partial):
├── frontend/src/app/       # Next.js dashboard
├── frontend/src/app/api/   # API routes
└── frontend/src/components/ # React components
```

---

## Next Steps: Frontend Integration Priority

### Phase 1: Dashboard Core Visualizations (CRITICAL)

**Goal:** Complete the visual dashboard with key metrics and interactive views

#### 1.1 Visibility Score KPI Card
- [ ] Calculate overall visibility score per brand
- [ ] Display with trend indicator (↑↓→)
- [ ] Show breakdown by model
- [ ] Click-through to detailed view

#### 1.2 Competitor Comparison Chart
- [ ] Grouped bar chart: Brand vs Competitors
- [ ] Filter by model or aggregate
- [ ] Confidence interval error bars
- [ ] Statistical significance badges

#### 1.3 Detailed Prompt Results Table
- [ ] Paginated table of all prompt results
- [ ] Columns: Prompt, Model, Date, Success, Mentions
- [ ] Filters: model, date, success, search
- [ ] Export to CSV/JSON

#### 1.4 Expandable Row Details
- [ ] Accordion expansion for full response
- [ ] Highlight brand mentions (target=green, competitors=orange)
- [ ] Show metadata (run ID, config hash)

---

### Phase 2: Statistical Enhancements (HIGH)

**Goal:** Surface confidence intervals and run history

#### 2.1 Confidence Interval Visualization
- [ ] Error bars on all trend charts
- [ ] Shaded 95% CI bands on line graphs
- [ ] Toggle CI display on/off
- [ ] Tooltip showing CI values

#### 2.2 Run History Dashboard
- [ ] Table of all tracking runs
- [ ] Compare runs (side-by-side)
- [ ] Detect drift (>2σ changes)
- [ ] Run duration and success metrics

#### 2.3 Statistical Summary Panel
- [ ] Mean, std, coefficient of variation
- [ ] Sample size adequacy indicator
- [ ] Comparison significance testing
- [ ] Export statistical report

---

### Phase 3: Prompt Management UI (MEDIUM)

**Goal:** Visualize and manage prompt generation

#### 3.1 Prompt Variations View
- [ ] Show base prompt → variations tree
- [ ] Indicate variation strategy used
- [ ] Filter by variation type
- [ ] Performance comparison: base vs variations

#### 3.2 Auto-Generated Prompts List
- [ ] Tag auto-generated prompts
- [ ] Show source domain/subtopic
- [ ] Quality score (if available)
- [ ] Link to related prompts

---

### Phase 4: Configuration & Controls (LOW)

**Goal:** Enable runtime control of features

#### 4.1 Dashboard Settings Panel
- [ ] Toggle variations on/off
- [ ] Set num_variations slider
- [ ] Choose variation strategy
- [ ] Enable/disable auto-generation

#### 4.2 Run Control Actions
- [ ] Trigger new run from dashboard
- [ ] Configure run parameters
- [ ] Monitor run progress
- [ ] Cancel/stop running batch

---

## API Endpoints to Implement

### Existing (Working)
```
GET /api/data?brand=Nike&days=30          ✅ Tested
GET /api/visibility-score?brand=Nike&days=30  ✅ Used in tests
GET /api/competitors?brand=Nike&days=30       ✅ Used in tests
GET /api/run-history?brand=Nike&days=30       ✅ Used in tests
GET /api/stats?brand=Nike&days=30             ✅ Used in tests
```

### New Endpoints Required

#### 1. Prompt Results
```
GET /api/prompts
Query Params: brand, model, page, limit, success_only, search
Response:
{
  "total": 79,
  "page": 1,
  "per_page": 25,
  "results": [
    {
      "id": 123,
      "prompt": "What are the best running shoes?",
      "model": "nemotron-3-nano",
      "run_id": 7,
      "timestamp": "2026-04-05T10:30:00Z",
      "success": true,
      "mentions": {"Nike": 2, "Adidas": 1}
    }
  ]
}
```

#### 2. Prompt Detail
```
GET /api/prompt-detail?id=123
Response:
{
  "id": 123,
  "prompt": "What are the best running shoes?",
  "response": "Nike and Adidas are the top brands...",
  "model": "nemotron-3-nano",
  "run_id": 7,
  "mentions": {"Nike": {"count": 2, "positions": [0, 45]}, "Adidas": 1},
  "config_hash": "abc123def456"
}
```

#### 3. Statistical Summary
```
GET /api/statistical-summary?brand=Nike&days=30&ci=95
Response:
{
  "brand": "Nike",
  "period": "30 days",
  "overall": {
    "mean_rate": 95.2,
    "std": 3.1,
    "ci_95": [91.0, 99.4],
    "total_runs": 7,
    "total_queries": 79
  },
  "by_model": [
    {
      "model": "nemotron-3-nano",
      "mean_rate": 98.3,
      "std": 1.2,
      "ci_95": [95.1, 100.0],
      "queries": 58
    }
  ]
}
```

#### 4. Run History
```
GET /api/runs?days=90
Response:
{
  "runs": [
    {
      "run_id": 7,
      "started_at": "2026-04-05T10:00:00Z",
      "completed_at": "2026-04-05T10:15:00Z",
      "total_queries": 79,
      "successful": 78,
      "failed": 1,
      "config_hash": "abc123",
      "prompts_used": 15  # includes variations + auto-gen
    }
  ]
}
```

#### 5. Run Action
```
POST /api/run/start
Body: {
  "enable_variations": true,
  "num_variations": 3,
  "variation_strategy": "semantic",
  "enable_auto_gen": true,
  "auto_gen_per_brand": 5
}
Response: { "run_id": 8, "status": "started" }

GET /api/run/status?id=8
Response: { "status": "running", "progress": 65, "queries_done": 51, "total": 79 }
```

---

## Database Queries Needed

### 1. Visibility Score Calculation
```sql
-- Overall visibility score per brand
SELECT 
    brand_name,
    COUNT(DISTINCT record_id) as total_prompts,
    COUNT(CASE WHEN mentioned > 0 THEN 1 END) as successful_prompts,
    ROUND(CAST(COUNT(CASE WHEN mentioned > 0 THEN 1 END) AS FLOAT) / 
          COUNT(DISTINCT record_id) * 100, 2) as visibility_score
FROM visibility_records 
LEFT JOIN mentions_json ON visibility_records.id = mentions_json.record_id
WHERE brand_name = ?
  AND timestamp >= datetime('now', '-' || ? || ' days')
GROUP BY brand_name;
```

### 2. Competitor Comparison
```sql
-- Compare all brands mention rates
SELECT 
    bm.brand_name,
    COUNT(vr.id) as total_queries,
    SUM(vr.mention_count) as total_mentions,
    ROUND(CAST(SUM(vr.mention_count) AS FLOAT) / COUNT(vr.id) * 100, 2) as mention_rate
FROM visibility_records vr
LEFT JOIN mentions_json bm 
    ON vr.id = bm.record_id 
    AND ? IN (bm.brand_name, bm.mentioned_keywords)
WHERE vr.timestamp >= datetime('now', '-' || ? || ' days')
GROUP BY bm.brand_name
ORDER BY mention_rate DESC;
```

### 3. Run History
```sql
-- All runs with statistics
SELECT 
    run_id,
    started_at,
    completed_at,
    total_queries,
    successful_queries,
    failed_queries,
    config_hash,
    strftime('%H:%M', (julianday(completed_at) - julianday(started_at)) * 24, 'HH:MM') as duration
FROM runs
WHERE started_at >= datetime('now', '-' || ? || ' days')
ORDER BY started_at DESC;
```

---

## Frontend Component Structure

```
frontend/src/app/
├── page.tsx                          # Main dashboard
│   ├── VisibilityScoreCard           # KPI component
│   ├── CompetitorComparisonChart     # Bar chart
│   ├── RunHistoryPanel               # Recent runs table
│   └── QuickStats                    # Summary metrics
├── prompts/
│   └── page.tsx                      # Detailed prompt results
│       ├── PromptTable               # Paginated table
│       └── PromptDetailModal         # Expanded view
├── runs/
│   └── page.tsx                      # Run history
│       ├── RunTable                  # Run list
│       └── RunDetail                 # Run specifics
├── components/
│   ├── ConfidenceIntervalBadge       # CI display
│   ├── MentionHighlighter            # Text with highlights
│   ├── ModelSelector                 # Filter by model
│   └── DateRangePicker               # Time range filter
└── api/
    ├── data/route.ts                 # ✅ Existing
    ├── prompts/route.ts              # ⏠ New
    ├── run-history/route.ts          # ⏠ New
    ├── statistical-summary/route.ts  # ⏠ New
    └── run/start/route.ts            # ⏠ New (trigger runs)
```

---

## Implementation Checklist

### Backend API (Priority: CRITICAL)
- [ ] Create `src/api/prompts.py` - Prompt listing with filters
- [ ] Create `src/api/statistics.py` - Enhanced statistical queries
- [ ] Create `src/api/runs.py` - Run history and control
- [ ] Implement `get_prompt_results()` in `storage.py`
- [ ] Implement `get_run_history()` in `storage.py`
- [ ] Implement `calculate_statistical_summary()` in `analyzer.py`

### Frontend Core (Priority: CRITICAL)
- [ ] Build `VisibilityScoreCard` component
- [ ] Build `CompetitorComparisonChart` (Chart.js/Recharts)
- [ ] Build `PromptTable` with pagination
- [ ] Build `MentionHighlighter` component
- [ ] Implement `api/prompts/route.ts`
- [ ] Implement `api/statistical-summary/route.ts`

### Frontend Enhancements (Priority: HIGH)
- [ ] Add confidence interval error bars to charts
- [ ] Build run history table
- [ ] Implement run status polling
- [ ] Add settings panel for run controls
- [ ] Build prompt detail modal

### Configuration (Priority: LOW)
- [ ] Update `configs/default.yaml` with variation defaults
- [ ] Add domain metadata to `configs/users/brands.yaml`
- [ ] Document new CLI flags
- [ ] Create example auto-generation config

---

## Testing Strategy

### Unit Tests
- [ ] Test visibility score calculations
- [ ] Test CI calculations edge cases
- [ ] Test prompt variation generation
- [ ] Test auto-prompt templates

### Integration Tests
- [ ] Full run with variations enabled
- [ ] Full run with auto-generation
- [ ] API endpoint responses
- [ ] Export functionality

### E2E Tests
- [ ] Dashboard loads with data
- [ ] Filters work correctly
- [ ] Export function works
- [ ] Run trigger starts background process

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Dashboard load time | < 2s | ⏠ TBD |
| API response time | < 500ms | ⏠ TBD |
| Prompt coverage (with variations) | +50% | 0% |
| Auto-generated prompt quality | 80%+ relevant | ⏠ TBD |
| User engagement (time on dashboard) | > 5min | ⏠ TBD |

---

## Blockers & Risks

| Issue | Priority | Mitigation |
|-------|----------|------------|
| Database schema needs prompts table | Medium | Create migration script |
| API routes need authentication | Low | Add after MVP |
| Run control needs background job | Medium | Use asyncio/celery |
| Chart library choice | Low | Review options: Recharts vs Chart.js |

---

## Appendix: Quick Reference Commands

```bash
# Run with variations enabled
python3 main.py run --enable-variations --num-variations 3 --variation-strategy semantic

# Run with auto-generation
python3 main.py run --enable-auto-gen --auto-gen-per-brand 5

# Run both features
python3 main.py run --enable-variations --enable-auto-gen

# View statistics
python3 main.py stats

# View trends
python3 main.py trends "Nike" --days 30 --ci 95

# Export data
python3 main.py export --format csv --output results.csv
```

---

**Document Version:** 2.0  
**Last Updated:** April 5, 2026  
**Next Review:** After Phase 1 completion
