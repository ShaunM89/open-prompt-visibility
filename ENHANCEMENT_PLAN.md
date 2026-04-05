# AI Visibility Dashboard Enhancement Plan

**Created:** April 4, 2026  
**Status:** Planning Phase  
**Priority:** High

---

## Executive Summary

This plan outlines enhancements to the AI Visibility Tracker dashboard to provide comprehensive performance visualization and strengthen the underlying data pipeline with statistical rigor and automated data generation.

---

## Part 1: Dashboard Visualizations

### 1.1 Overall Visibility Score/Percentage

**Objective:** Calculate and display a single visibility metric representing brand performance.

**Implementation:**
- **Formula:** `Visibility Score = (Successful Prompts / Total Prompts) × 100`
- **Definition of "Success":** A prompt is successful if the target brand is mentioned in the LLM response
- **Display:** Large KPI card at top of dashboard showing percentage with trend indicator
- **Breakdown:** Show per-model visibility scores in a stacked bar or radar chart

**Data Requirements:**
- Already available in `visibility_records` table via `mentions_json` field
- Need query to count non-empty mentions per brand across all prompts

---

### 1.2 Competitor Comparison (Bar Chart)

**Objective:** Visual comparison of brand vs. competitor mention rates across all models.

**Implementation:**
- **Chart Type:** Grouped/clustered bar chart
  - X-axis: Brand names (target brand + all competitors)
  - Y-axis: Mention rate percentage
  - Groups: Can filter by model or show aggregate
- **Alternative:** Stacked bar showing mention distribution
- **Interactive:** Click on bars to drill down to specific model performance

**Data Requirements:**
- Existing `brands.yaml` defines competitor relationships
- Query all brands (target + competitors) mention rates
- Use `analyticsEngine.compare_models()` with modifications to include all brands

---

### 1.3 Detailed Prompt List View

**Objective:** Table showing all prompts tested for the selected brand with success/fail status.

**Implementation:**
- **Table Columns:**
  - Prompt text (truncated with expand)
  - Model used
  - Date/time
  - Success indicator (✓/✗ or color-coded)
  - Mentioned brands (from `mentions_json`)
  - Actions (expand for details)
- **Filters:**
  - By model
  - By date range
  - By success/fail
  - Search in prompt text
- **Pagination:** 25-50 rows per page

**Data Requirements:**
- Query `visibility_records` with filters
- Need to parse `mentions_json` for mentioned brands display

---

### 1.4 Expandable Prompt Details with Brand Highlights

**Objective:** When expanding a prompt row, show full response text with highlighted brand mentions.

**Implementation:**
- **Expandable Row Pattern:** Accordion/collapsible row expansion
- **Content to Display:**
  - Full prompt text
  - Full LLM response text (formatted/prettified)
  - Highlighted mentions: Wrap brand names in `<mark>` or colored spans
  - Metadata: Model, temperature, response time (if tracked)
- **Highlight Logic:**
  - Parse `mentions_json` to get mentioned brands
  - Use brand keywords from config to find and highlight in response text
  - Different colors for target brand vs. competitors

**Technical Approach:**
```typescript
// Highlight mentions in response text
function highlightMentions(text: string, mentions: {[brand: string]: number}, brands: Brand[]) {
  // Replace brand keywords with highlighted spans
  // Target brand: Green highlight
  // Competitors: Orange/amber highlight
}
```

---

## Part 2: Data Pipeline Enhancements

### 2.1 Statistical Robustness: Multiple Attempts & Confidence Windows

**Current State:**
- `queries_per_prompt: 10` in config
- Runs 10 queries per prompt per model
- Basic Wilson score interval calculation exists but not surfaced in UI

**Gap Analysis:**
- No explicit handling of probabilistic "wobble" (LLM non-determinism)
- Confidence intervals calculated but not visualized
- No statistical significance testing between models/brands
- No run-to-run comparison to detect drift

**Recommended Enhancements:**

#### 2.1.1 Per-Prompt Statistical Aggregation
Add aggregation layer that calculates:
- **Mean mention rate** across multiple runs
- **Standard deviation** of mention rates
- **Confidence intervals** (95% Wilson score) for each brand/model
- **Coefficient of variation** to measure stability

**Implementation:**
```python
# New method in AnalyticsEngine
def calculate_statistical_summary(self, brand_keyword: str, days: int = 30) -> Dict:
    """Calculate comprehensive stats with confidence windows."""
    # Group by: model, prompt category, run
    # Calculate: mean, std, CI for mention rates
    # Return: structured summary for dashboard
```

#### 2.1.2 Run History Comparison
- Add run history table showing each batch run
- Compare mention rates across runs to detect drift
- Flag statistically significant changes (>2σ from mean)

#### 2.1.3 Visual Confidence Intervals
- Add error bars to trend lines (±1σ, ±2σ)
- Shaded areas showing 95% CI bands
- Statistical significance badges when comparing models

---

### 2.2 Query Fan-Out: Prompt Variations

**Objective:** Transform single prompts into multiple variations to capture topic diversity rather than exact match queries.

**Implementation Strategy:**

#### 2.2.1 Automatic Variation Generation
Use LLM to generate variations of base prompts:

```python
def generate_prompt_variations(base_prompt: str, num_variations: int = 5) -> List[str]:
    """Generate semantically similar variations of a prompt."""
    prompt = f"""
    Generate {num_variations} semantically similar but linguistically diverse 
    variations of this query. Focus on capturing the same intent/topic with 
    different wording, tone, and structure.
    
    Base query: "{base_prompt}"
    
    Return as JSON array of strings.
    """
    # Parse LLM response
    return variations
```

#### 2.2.2 Variation Categories
Generate different types of variations:
1. **Synonym replacement:** "best" → "top-rated", "recommended"
2. **Sentence restructuring:** "What are X?" → "Can you recommend X?"
3. **Context addition:** Add user scenario ("As a runner, what...")
4. **Tone variation:** Formal → casual
5. **Length variation:** Concise → detailed

#### 2.2.3 Configuration
Add to `config.yaml`:
```yaml
tracking:
  queries_per_prompt: 10
  prompt_variations:
    enabled: true
    num_variations: 3  # Generate 3 variations per base prompt
    variation_strategy: "semantic"  # or "synonym", "full"
```

**Benefits:**
- Captures topic popularity, not just exact keyword match
- More robust measurement (averages out wording bias)
- Larger dataset without manual prompt creation
- Reveals if certain phrasings favor specific brands

---

### 2.3 Auto-Generated Prompts from Brand Domain

**Objective:** Automatically generate relevant prompts based on brand domain/industry to increase data depth.

**Implementation Strategy:**

#### 2.3.1 Domain Analysis
Extract brand domain from configuration:
```yaml
brands:
  - name: "Nike"
    domain: "athletic footwear & apparel"
    subtopics:
      - running
      - basketball
      - sustainability
      - innovation
    target_audience: ["athletes", "fitness enthusiasts", "casual wear"]
```

#### 2.3.2 Prompt Template Engine
Create prompt templates based on domain topics:

```python
PROMPT_TEMPLATES = {
    "comparison": "Compare {brand} vs competitors for {use_case}",
    "recommendation": "What {product_category} would you recommend for {use_case}?",
    "trends": "What are the leading {product_category} brands in {year}?",
    "expertise": "Which {brand} is most associated with {attribute}?",
    "purchase_intent": "I'm looking for {product_criteria}, which brand should I choose?",
    "awareness": "Name the top {count} brands in {category}",
}
```

#### 2.3.3 Automated Generation Pipeline
```python
def generate_domain_prompts(brand: dict, num_prompts: int = 20) -> List[str]:
    """Generate relevant prompts based on brand domain."""
    # Use LLM to generate diverse prompts
    prompt = f"""
    Generate {num_prompts} natural user queries that would lead to 
    mentions of {brand['name']} in the context of {brand['domain']}.
    
    Categories:
    - Comparison queries (vs competitors)
    - Recommendation queries
    - "Best of" queries
    - Feature-specific queries
    - Use-case-specific queries
    
    Base prompt templates: {list(PROMPT_TEMPLATES.keys())}
    
    Return as JSON array.
    """
    return parsed_prompts
```

#### 2.3.4 Integration Points
- Add to `prompts.yaml` auto-generation section:
```yaml
auto_generation:
  enabled: true
  per_brand:
    - brand: "Nike"
      num_prompts: 15
      categories: ["comparison", "recommendation", "trends"]
    - brand: "Adidas"
      num_prompts: 15
      categories: ["comparison", "recommendation"]
```

- Run as pre-processing step before tracking run
- Store generated prompts with metadata (source: "auto-generated", seed prompt)

---

## Part 3: Database Schema Considerations

### 3.1 Current Schema Strengths
✅ Already stores full response text (enables re-analysis)
✅ Mentions as JSON (flexible)
✅ Config hash tracking (reproducibility)
✅ Timestamps for all records

### 3.2 Needed Schema Additions

#### 3.2.1 Prompt Variations Tracking
```sql
-- Track prompt generation metadata
CREATE TABLE prompt_versions (
    id INTEGER PRIMARY KEY,
    base_prompt TEXT NOT NULL,
    generated_prompt TEXT NOT NULL,
    variation_type TEXT,  -- 'semantic', 'synonym', etc.
    source_prompt_id INTEGER,  -- if derived from another prompt
    created_at TIMESTAMP
);

-- Link visibility records to prompt versions
ALTER TABLE visibility_records ADD COLUMN prompt_version_id INTEGER;
```

#### 3.2.2 Enhanced Run Metadata
```sql
-- Additional run statistics
CREATE TABLE run_statistics (
    run_id INTEGER PRIMARY KEY,
    total_prompt_variations INTEGER,
    auto_generated_prompts INTEGER,
    manual_prompts INTEGER,
    statistical_summary_json TEXT  -- mean, std, CI data
);
```

---

## Part 4: Implementation Phases

### Phase 1: Dashboard Core Visualizations (Priority: Critical)
**Duration:** 1-2 weeks  
**Deliverables:**
1. Visibility score KPI card ✅
2. Competitor comparison bar chart ✅
3. Detailed prompt list table ✅
4. Expandable row with highlighted mentions ✅

**Files to Modify:**
- `frontend/src/app/page.tsx` - Main dashboard component
- `frontend/src/app/api/data/route.ts` - Add new API endpoints
- `src/analyzer.py` - Add helper methods for dashboard queries

---

### Phase 2: Statistical Enhancements (Priority: High)
**Duration:** 1-2 weeks  
**Deliverables:**
1. Confidence interval visualization (error bars on charts)
2. Run history table with trend comparison
3. Statistical significance indicators
4. Sample size calculator utility

**Files to Modify:**
- `src/analyzer.py` - Enhanced statistical methods
- `frontend/src/app/page.tsx` - Add error bars to charts
- `src/storage.py` - Add run history queries

---

### Phase 3: Query Fan-Out Implementation (Priority: Medium)
**Duration:** 2 weeks  
**Deliverables:**
1. Prompt variation generator module
2. Configuration for variation strategy
3. Database support for variation tracking
4. Integration with tracker.run_batch()

**Files to Create/Modify:**
- `src/prompt_generator.py` - New module for variation generation
- `src/tracker.py` - Integration points
- `configs/tool/config.yaml` - Add variation settings

---

### Phase 4: Auto-Prompt Generation (Priority: Medium)
**Duration:** 2-3 weeks  
**Deliverables:**
1. Domain-based prompt template engine
2. LLM-driven prompt generation
3. Configuration for brand domains
4. Integration into tracking pipeline

**Files to Create/Modify:**
- `src/prompt_generator.py` - Enhance with domain-based generation
- `configs/users/brands.yaml` - Add domain/topic metadata
- `src/tracker.py` - Pre-processing step for auto-generation

---

## Part 5: Testing & Validation

### 5.1 Validation Metrics
- **Statistical:** Compare confidence intervals before/after fan-out
- **Data Quality:** Measure increase in prompt diversity
- **Performance:** Track query time impact of variations
- **Coverage:** Measure % of industry topics covered

### 5.2 Test Cases
1. Verify confidence intervals narrow with increased samples
2. Verify prompt variations capture same topic distribution
3. Verify auto-generated prompts are semantically relevant
4. Dashboard correctly highlights all mentioned brands

---

## Part 6: Configuration Examples

### 6.1 Enhanced Tracking Config
```yaml
# configs/tool/config.yaml
tracking:
  queries_per_prompt: 10  # Statistical baseline
  max_retries: 3
  prompt_variations:
    enabled: true
    num_variations: 3
    strategy: "semantic"  # preserves intent while varying wording
  auto_prompt_generation:
    enabled: true
    per_brand_prompts: 15
    categories: ["comparison", "recommendation", "trends", "expertise"]
  statistical_analysis:
    confidence_level: 95  # 90, 95, or 99
    track_run_history: true
    min_runs_for_significance: 3  # Minimum runs before sig. testing
```

### 6.2 Enhanced Brand Config
```yaml
# configs/users/brands.yaml
brands:
  - name: "Nike"
    keywords: ["Nike", "Just Do It", "Swoosh"]
    domain: "athletic footwear & apparel"
    subtopics:
      - running
      - basketball
      - sustainability
      - innovation
    target_audience: ["athletes", "fitness enthusiasts", "casual"]
    competitors:
      - name: "Adidas"
        keywords: ["Adidas", "Impossible is Nothing"]
      - name: "Reebok"
        keywords: ["Reebok"]
```

---

## Part 7: Success Criteria

### Dashboard Enhancements
- [ ] Visibility score displayed prominently with trend
- [ ] Competitor comparison chart shows relative performance
- [ ] Users can drill down to individual prompt results
- [ ] Brand mentions are visibly highlighted in responses

### Data Pipeline Enhancements
- [ ] Confidence intervals calculated and visualized
- [ ] Prompt variations increase dataset diversity
- [ ] Auto-generated prompts capture relevant topics
- [ ] Statistical significance testing available for comparisons

### Measurable Outcomes
- 30%+ increase in unique prompts tracked (via variations + auto-generation)
- Confidence intervals narrow by ≥20% with variation-based averaging
- Dashboard click-through rate increases (user engagement)
- Time-to-insight decreases (pre-aggregated stats)

---

## Part 8: Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM-based variation generation is costly | Medium | Cache variations, limit num_variations |
| Auto-generated prompts are low quality | Medium | Human review option, quality scoring |
| Database grows rapidly | Low | Partitioning, cleanup policies |
| Statistical complexity overwhelms users | Medium | Progressive disclosure, tooltips |
| Variation strategy biases results | Medium | A/B test variation strategies |

---

## Appendix: API Endpoints Needed

```
GET /api/data?brand=Nike&days=30
  → Existing: stats, modelStats, trends

GET /api/visibility-score?brand=Nike&days=30
  → { score: 72.5, total_prompts: 100, successful: 73 }

GET /api/competitors?brand=Nike&days=30
  → [{ brand: "Nike", rate: 72.5 }, { brand: "Adidas", rate: 65.2 }, ...]

GET /api/prompts?brand=Nike&model=all&page=1&limit=25
  → Pagination of prompt results with success/fail

GET /api/prompt-detail?id=123
  → Full response text with highlighted mentions

GET /api/runs?days=30
  → Run history with statistical summaries

GET /api/statistical-summary?brand=Nike&days=30
  → { mean, std, ci_95, runs_analyzed }
```

---

**Document Version:** 1.0  
**Last Updated:** April 4, 2026  
**Review Cadence:** Pre-implementation review required
