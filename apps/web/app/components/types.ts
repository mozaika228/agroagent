export type Source = { doc_id: string; chunk_id: string; score: number };
export type Msg = { role: "user" | "assistant"; text: string; sources?: Source[] };

export type EvalItem = {
  run_id: string;
  dataset: string;
  model: string;
  status: string;
  sample_size: number;
  created_at: string;
};

export type CompareResult = { profile: string; answer: string; sources: Source[] };
export type UploadItem = { document_id: string; status: string; chunks?: number | null };
export type JobItem = {
  job_id: string;
  job_type: string;
  status: string;
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  error?: string | null;
};

export type DebateStep = {
  step_id: string;
  agent_name: string;
  step_type: string;
  step_hash: string;
  parent_hash?: string | null;
  payload: Record<string, unknown>;
};

export type DebateRun = {
  trace_id: string;
  trace_digest: string;
  answer: string;
  winner: string;
  score_a: number;
  score_b: number;
  rounds: number;
  spawned_agents: string[];
  safety: {
    policy_version: string;
    level: string;
    original_action: string;
    effective_action: string;
    overridden: boolean;
    override_reason?: string | null;
    reasons: string[];
    rules_triggered: string[];
  };
  steps: DebateStep[];
};

export type DebateMetrics = {
  total_runs: number;
  blocked_runs: number;
  overridden_runs: number;
  winner_a: number;
  winner_b: number;
  avg_latency_ms: number;
  avg_rounds: number;
  avg_steps: number;
  last_trace_id?: string | null;
};

export type SafetyEvalResult = {
  run_id?: string | null;
  dataset: string;
  total: number;
  accuracy: number;
  block_precision: number;
  block_recall: number;
  warn_precision: number;
  warn_recall: number;
  allow_precision: number;
  allow_recall: number;
  mismatches: Array<{
    index: number;
    locale: string;
    question: string;
    expected_action: string;
    predicted_action: string;
    rules_triggered: string[];
  }>;
};
