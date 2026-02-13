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
