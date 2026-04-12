// src/lib/api.ts
// Client-side API calls

export interface KPIData {
  total_runs: number;
  total_records: number;
  unique_models: number;
  total_mentions: number;
}

export interface ModelStat {
  model_provider: string;
  model_name: string;
  total_runs: number;
  total_mentions: number;
  mention_rate_pct: number;
}

export interface TrendData {
  date: string;
  model_name: string;
  total_queries: number;
  mention_count: number;
}

export interface ApiData {
  stats: KPIData | null;
  modelStats: ModelStat[];
  trends: TrendData[];
  error?: string;
}

export interface VisibilityScoreData {
  brand: string;
  score: number;
  total_prompts: number;
  successful_prompts: number;
  by_model: ModelVisibility[];
  confidence_interval: [number, number] | null;
}

export interface ModelVisibility {
  model_name: string;
  model_provider: string;
  score: number;
  total_prompts: number;
  successful_prompts: number;
  confidence_interval: [number, number] | null;
}

export interface CompetitorComparison {
  target_brand: string;
  target_score: number;
  competitors: BrandScore[];
  all_brands: BrandScore[];
  period_days: number;
}

export interface BrandScore {
  name: string;
  score: number;
  total_prompts: number;
  successful_prompts: number;
  mention_count?: number;
  is_target?: boolean;
}

export interface PromptResult {
  id: number;
  run_id: number;
  model_provider: string;
  model_name: string;
  prompt: string;
  response_text: string;
  mentions: { [brand: string]: number };
  detected_at: string;
  is_success: boolean;
}

export interface PromptListData {
  prompts: PromptResult[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
  filters: {
    brand: string;
    model: string | null;
    days: number;
    success_filter: boolean | null;
  };
}

export interface PromptDetailData {
  id: number;
  run_id: number;
  model_provider: string;
  model_name: string;
  prompt: string;
  response_text: string;
  highlighted_response: string;
  mentions: { [brand: string]: number };
  detected_at: string;
  target_brand: string;
}

export interface RunHistoryEntry {
  run_id: number;
  started_at: string;
  completed_at: string;
  duration: string | null;
  total_queries: number;
  successful_queries: number;
  success_rate: number;
  models_used: string[];
  all_mentions: { [brand: string]: number };
}

export interface StatisticalSummary {
  brand: string;
  period_days: number;
  n_runs: number;
  mean_mention_rate: number;
  std_deviation: number;
  std_error: number;
  confidence_interval_95: [number, number] | null;
  coefficient_of_variation: number;
  min_rate: number;
  max_rate: number;
  rate_range: number;
  anomalies: {
    run_index: number;
    run_id: number;
    rate: number;
    deviation: number;
  }[];
  interpretation: string;
}

async function fetchApi(endpoint: string, params: Record<string, any>): Promise<any> {
  const queryString = new URLSearchParams(params).toString();
  const res = await fetch(`/api/data?${queryString}`);
  const data = await res.json();
  
  if (data.error && !data.stats && !data.score) {
    throw new Error(data.error);
  }
  
  return data;
}

export async function fetchData(brand: string, days: number): Promise<ApiData> {
  try {
    const data = await fetchApi('data', { brand, days, endpoint: 'default' });
    
    return {
      stats: data.stats,
      modelStats: data.modelStats || [],
      trends: data.trends || []
    };
  } catch (err) {
    return {
      stats: null,
      modelStats: [],
      trends: [],
      error: err instanceof Error ? err.message : 'Failed to fetch data'
    };
  }
}

export async function fetchVisibilityScore(brand: string, days: number): Promise<VisibilityScoreData> {
  try {
    const data = await fetchApi('data', { brand, days, endpoint: 'visibility-score' });
    return data;
  } catch (err) {
    return {
      brand,
      score: 0,
      total_prompts: 0,
      successful_prompts: 0,
      by_model: [],
      confidence_interval: null
    };
  }
}

export async function fetchCompetitorComparison(targetBrand: string, days: number): Promise<CompetitorComparison> {
  try {
    const data = await fetchApi('data', { brand: targetBrand, days, endpoint: 'competitors' });
    // Ensure all_brands is always present
    if (!data.all_brands) {
      data.all_brands = [
        { name: targetBrand, score: data.target_score || 0, total_prompts: 0, successful_prompts: 0, is_target: true },
        ...(data.competitors || []).map((c: any) => ({ ...c, is_target: false }))
      ].sort((a: any, b: any) => b.score - a.score);
    }
    return data;
  } catch (err) {
    return {
      target_brand: targetBrand,
      target_score: 0,
      competitors: [],
      all_brands: [],
      period_days: days
    };
  }
}

export async function fetchPromptList(
  brand: string,
  days: number,
  page: number = 1,
  limit: number = 25,
  model: string | null = null,
  successFilter: boolean | null = null
): Promise<PromptListData> {
  try {
    const params: Record<string, any> = {
      brand,
      days,
      page,
      limit,
      endpoint: 'prompts'
    };
    
    if (model) params.model = model;
    if (successFilter !== null) params.success = successFilter;
    
    const data = await fetchApi('data', params);
    return data;
  } catch (err) {
    return {
      prompts: [],
      pagination: { page, limit, total: 0, total_pages: 0 },
      filters: { brand, model, days, success_filter: successFilter }
    };
  }
}

export async function fetchPromptDetail(recordId: number): Promise<PromptDetailData | null> {
  try {
    const data = await fetchApi('data', { id: recordId, endpoint: 'prompt-detail' });
    return data;
  } catch (err) {
    return null;
  }
}

export async function fetchRunHistory(days: number = 30): Promise<RunHistoryEntry[]> {
  try {
    const data = await fetchApi('data', { days, endpoint: 'run-history' });
    return data;
  } catch (err) {
    return [];
  }
}

export interface ConvergenceStatus {
  run_id: number;
  adaptive_enabled: boolean;
  target_ci_width: number;
  max_queries: number;
  convergence_scope: string;
  overall_converged: boolean;
  pairs: ConvergencePair[];
  summary: {
    total_pairs: number;
    converged_pairs: number;
    total_queries: number;
    estimated_queries_saved: number;
  };
}

export interface ConvergencePair {
  model: string;
  prompt: string;
  brand: string;
  queries_completed: number;
  converged: boolean;
  ci_width: number | null;
  mean_score: number;
  ci: [number, number] | null;
}

export interface ModelComparisonModel {
  model_name: string;
  mention_rate: number;
  total_runs: number;
  mentions: number;
  confidence_interval: [number, number] | null;
  standard_error: number;
  statistical_significance: string;
}

export interface ModelComparisonData {
  brand: string;
  models: ModelComparisonModel[];
}

export async function fetchModelComparison(brand: string, days: number): Promise<ModelComparisonData> {
  try {
    const data = await fetchApi('data', { brand, days, endpoint: 'model-comparison' });
    return data;
  } catch (err) {
    return { brand, models: [] };
  }
}

export async function fetchConvergenceStatus(runId: number): Promise<ConvergenceStatus | null> {
  try {
    const data = await fetchApi('data', { run_id: runId, endpoint: 'convergence-status' });
    return data;
  } catch (err) {
    return null;
  }
}

export interface SentimentBrandData {
  prominence: number;
  sentiment: number;
  composite: number;
  sample_size?: number;
  summary?: string;
  avg_prominence?: number;
  avg_sentiment?: number;
  avg_composite?: number;
  scores?: { prominence: number; sentiment: number; composite: number }[];
}

export interface SentimentData {
  run_id: number;
  mode: "fast" | "detailed" | "none";
  started_at: string;
  completed_at: string;
  brands: { [brand: string]: SentimentBrandData };
  message?: string;
}

export async function fetchSentiment(runId: number): Promise<SentimentData | null> {
  try {
    const data = await fetchApi('data', { run_id: runId, endpoint: 'sentiment' });
    return data;
  } catch (err) {
    return null;
  }
}

export async function fetchLatestSentiment(): Promise<SentimentData | null> {
  try {
    const data = await fetchApi('data', { endpoint: 'sentiment-latest' });
    return data;
  } catch (err) {
    return null;
  }
}

export async function fetchStatisticalSummary(brand: string, days: number): Promise<StatisticalSummary> {
  try {
    const data = await fetchApi('data', { brand, days, endpoint: 'statistical-summary' });
    return data;
  } catch (err) {
    return {
      brand,
      period_days: days,
      n_runs: 0,
      mean_mention_rate: 0,
      std_deviation: 0,
      std_error: 0,
      confidence_interval_95: null,
      coefficient_of_variation: 0,
      min_rate: 0,
      max_rate: 0,
      rate_range: 0,
      anomalies: [],
      interpretation: 'No data'
    };
  }
}

// --- Segment Analysis Types and Functions ---

export interface SegmentItem {
  segment_value: string;
  total_queries: number;
  mention_count: number;
  mention_rate: number;
  confidence_interval: [number, number] | null;
}

export interface SegmentData {
  brand: string;
  dimension: string;
  days: number;
  segments: SegmentItem[];
}

export async function fetchVisibilityBySegment(
  brand: string,
  dimension: string,
  days: number
): Promise<SegmentData> {
  try {
    const data = await fetchApi('data', { brand, dimension, days, endpoint: 'visibility-by-segment' });
    return data;
  } catch (err) {
    return { brand, dimension, days, segments: [] };
  }
}

export interface SegmentBrandData {
  segment_value: string;
  total_queries: number;
  mention_count: number;
  mention_rate: number;
  confidence_interval: [number, number] | null;
}

export interface SegmentComparison {
  dimension: string;
  days: number;
  brands: Record<string, SegmentBrandData[]>;
}

export async function fetchSegmentComparison(
  brands: string[],
  dimension: string,
  days: number
): Promise<SegmentComparison> {
  try {
    const data = await fetchApi('data', {
      brands: brands.join(','),
      dimension,
      days,
      endpoint: 'segment-comparison',
    });
    return data;
  } catch (err) {
    return { dimension, days, brands: {} };
  }
}

export interface VariationDriftItem {
  prompt: string;
  total_queries: number;
  mention_count: number;
  mention_rate: number;
}

export interface VariationDriftData {
  canonical_id: string;
  brand: string;
  days: number;
  canonical_rate: number;
  total_queries: number;
  variations: VariationDriftItem[];
}

export async function fetchVariationDrift(
  canonicalId: string,
  brand: string,
  days: number
): Promise<VariationDriftData | null> {
  try {
    const data = await fetchApi('data', { canonical_id: canonicalId, brand, days, endpoint: 'variation-drift' });
    return data;
  } catch (err) {
    return null;
  }
}
