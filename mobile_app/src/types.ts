export type BestWindow = {
  available: boolean;
  rank: number;
  start: string;
  end: string;
  score: number;
  title: string;
  reason: string;
  cautions: string[];
};

export type AlternativeWindow = {
  rank: number;
  start: string;
  end: string;
  score: number;
  reason: string;
};

export type Advice = {
  ok: boolean;
  decision: string;
  analysis_period: string;
  crop: string;
  active_substance: string;
  best_window: BestWindow;
  alternatives: AlternativeWindow[];
  warnings: string[];
  farmer_summary: string;
  detailed_report: string;
  whatsapp_summary: string;
  practical_notes: string[];
};

export type AdviceResponse = {
  ok: boolean;
  error?: string;
  input: {
    active_substance: string;
    crop: string;
    analysis_days: number;
    min_window_hours: number;
  };
  forecast_meta: {
    generated_at: string;
    successful_sources: string[];
    failed_sources: string[];
    candidate_window_count: number;
  };
  advice?: Advice;
  fallback?: Partial<Advice>;
};

export type SendWhatsAppResponse = {
  ok: boolean;
  sent: boolean;
  target: "default" | "custom";
};
