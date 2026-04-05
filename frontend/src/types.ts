// Types for visibility tracking

export interface VisibilityScore {
  brand_score_pct: number;
  by_model: Array<{
    model: string;
    model_name: string;
    mentions: number;
    sample_size: number;
    std: number;
    score: number;
  }>;
  confidence_interval: [number, number] | null;
  sample_size_adq: boolean;
  mean_mention_rate?: number;
  std_deviation?: number;
  n_runs?: number;
  total_queries?: number;
  coefficient_of_variation?: number;
  prompt_count?: number;
  brand_score_count?: number;
}

export interface CompetitorData {
  competitors: Array<{
    competitor: string;
    share: number;
  }>;
  competitor_names: string[];
  max_shares: Record<string, number>;
}

export interface PromptResults {
  prompts: Array<{
    prompt: string;
    response_text: string;
    detected_models: Array<{
      model_name: string;
      model_provider: string;
      mentioned: boolean;
      timestamp: string;
    }>;
    mentions_str: string;
    completed_at: string;
  }>;
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
  };
}
