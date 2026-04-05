// src/lib/schemas.ts
// Database row types matching SQLite schema

export interface VisibilityRecord {
  id: number;
  detected_at: string;
  model_provider: string;
  model_name: string;
  prompt: string;
  response_text: string;
  mentions_json: string | null;
  run_started: string;
}

export interface RunStats {
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

export interface BrandAnalysis {
  brand: string;
  period_days: number;
  total_mentions: number;
  total_queries: number;
  overall_mention_rate: number;
  variance_by_model: Record<string, {
    mention_rate: number;
    total_runs: number;
    total_mentions: number;
    confidence_interval_95: [number, number];
    standard_error: number;
  }>;
}
