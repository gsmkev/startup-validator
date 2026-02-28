export interface Competitor {
  name: string;
  ruc: string | null;
  source: string;
  detail: string | null;
}

export interface MarketHint {
  hint: string;
  type: "opportunity" | "warning" | "info";
  source: string;
}

export interface IdeaValidationResult {
  idea: string;
  keywords_extracted: string[];
  market_signal: number;
  signal_label: string;
  recommendation: string;
  competitors: Competitor[];
  market_hints: MarketHint[];
  strengths: string[];
  weaknesses: string[];
  action_items: string[];
  pivot_suggestions: string[];
  news_samples: string[];
  sources_queried: string[];
  sources_unavailable: string[];
  scan_duration_ms: number;
  raw_scores: Record<string, number>;
}
