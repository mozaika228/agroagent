import { FormEvent } from "react";
import { CompareResult, DebateMetrics, DebateRun, DebateStep, EvalItem, JobItem, Msg, UploadItem } from "./types";

export function HeroPanel(props: { apiBase: string; role: string | null; sessionId: string | null }) {
  return (
    <header className="hero">
      <div>
        <h1>AgroAgent Fullstack Console</h1>
        <p>Chat, document ingestion, RAG query/compare, and eval tracking in one interface.</p>
      </div>
      <div className="meta">
        <div><span>API</span><code>{props.apiBase}</code></div>
        <div><span>Role</span><code>{props.role ?? "not authenticated"}</code></div>
        <div><span>Session</span><code>{props.sessionId ?? "none"}</code></div>
      </div>
    </header>
  );
}

export function AuthPanel(props: {
  email: string;
  password: string;
  onEmailChange: (v: string) => void;
  onPasswordChange: (v: string) => void;
  onRegister: () => void;
  onLogin: () => void;
  onLogout: () => void;
  isAuthed: boolean;
}) {
  return (
    <article className="panel">
      <h2>Auth</h2>
      <input value={props.email} onChange={(e) => props.onEmailChange(e.target.value)} placeholder="email" />
      <input value={props.password} onChange={(e) => props.onPasswordChange(e.target.value)} placeholder="password" type="password" />
      <div className="row">
        <button type="button" onClick={props.onRegister}>Register</button>
        <button type="button" onClick={props.onLogin}>Login</button>
        <button type="button" onClick={props.onLogout} disabled={!props.isAuthed}>Logout</button>
      </div>
    </article>
  );
}

export function DocumentsPanel(props: {
  uploads: UploadItem[];
  canUpload: boolean;
  onUploadSubmit: (e: FormEvent) => void;
  onSelectFile: (f: File | null) => void;
  onRefresh: (documentId: string) => void;
}) {
  return (
    <article className="panel">
      <h2>Documents</h2>
      <form onSubmit={props.onUploadSubmit} className="stack">
        <input type="file" accept=".pdf,.txt,.md" onChange={(e) => props.onSelectFile(e.target.files?.[0] ?? null)} />
        <button type="submit" disabled={!props.canUpload}>Upload</button>
      </form>
      <div className="table">
        {props.uploads.length === 0 && <p className="muted">No uploaded documents yet.</p>}
        {props.uploads.map((u) => (
          <div key={u.document_id} className="row spread">
            <code>{u.document_id.slice(0, 12)}...</code>
            <span>{u.status}</span>
            <span>{u.chunks ?? "-"} chunks</span>
            <button type="button" onClick={() => props.onRefresh(u.document_id)}>Refresh</button>
          </div>
        ))}
      </div>
    </article>
  );
}

export function ChatPanel(props: {
  text: string;
  messages: Msg[];
  queryProfile: string;
  canSend: boolean;
  sending: boolean;
  onTextChange: (v: string) => void;
  onProfileChange: (v: string) => void;
  onSendChat: (e: FormEvent) => void;
  onRagQuery: () => void;
  onCompare: () => void;
}) {
  return (
    <article className="panel">
      <h2>Agent Chat</h2>
      <form onSubmit={props.onSendChat} className="stack">
        <textarea
          value={props.text}
          onChange={(e) => props.onTextChange(e.target.value)}
          rows={4}
          placeholder="What to sow in Uralsk in May?"
        />
        <div className="row">
          <button type="submit" disabled={!props.canSend}>{props.sending ? "Sending..." : "Send Chat"}</button>
          <select value={props.queryProfile} onChange={(e) => props.onProfileChange(e.target.value)}>
            <option value="balanced">balanced</option>
            <option value="semantic_heavy">semantic_heavy</option>
            <option value="lexical_heavy">lexical_heavy</option>
          </select>
          <button type="button" onClick={props.onRagQuery} disabled={!props.canSend}>RAG Query</button>
          <button type="button" onClick={props.onCompare} disabled={!props.canSend}>Compare</button>
        </div>
      </form>

      <div className="chat">
        {props.messages.length === 0 && <p className="muted">No messages yet.</p>}
        {props.messages.map((m, i) => (
          <div key={`${m.role}-${i}`} className={`bubble ${m.role}`}>
            <strong>{m.role === "user" ? "You" : "Agent"}</strong>
            <p>{m.text}</p>
            {!!m.sources?.length && (
              <div className="sources">
                {m.sources.map((s) => (
                  <small key={`${s.doc_id}-${s.chunk_id}`}>{s.doc_id.slice(0, 8)}:{s.chunk_id.slice(0, 8)} ({s.score.toFixed(3)})</small>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </article>
  );
}

export function ComparePanel(props: { runId: string | null; results: CompareResult[] }) {
  return (
    <article className="panel">
      <h2>RAG Compare</h2>
      {props.runId && <p><strong>Saved Eval Run:</strong> <code>{props.runId}</code></p>}
      {props.results.length === 0 && <p className="muted">Run compare to see profile outputs.</p>}
      {props.results.map((r) => (
        <div key={r.profile} className="compareCard">
          <h3>{r.profile}</h3>
          <p>{r.answer}</p>
          <p className="muted">Sources: {r.sources.length}</p>
        </div>
      ))}
    </article>
  );
}

export function EvalsPanel(props: {
  evals: EvalItem[];
  evalRunId: string;
  canQuery: boolean;
  onLoadEvals: () => void;
  onEvalRunIdChange: (v: string) => void;
  onFetchById: () => void;
}) {
  return (
    <section className="panel">
      <h2>Eval History</h2>
      <div className="row">
        <button type="button" onClick={props.onLoadEvals} disabled={!props.canQuery}>Load Last 20</button>
        <input value={props.evalRunId} onChange={(e) => props.onEvalRunIdChange(e.target.value)} placeholder="run_id" />
        <button type="button" onClick={props.onFetchById} disabled={!props.evalRunId.trim() || !props.canQuery}>Load By Run ID</button>
      </div>
      <div className="table">
        {props.evals.length === 0 && <p className="muted">No eval runs loaded.</p>}
        {props.evals.map((r) => (
          <div key={r.run_id} className="row spread">
            <code>{r.run_id.slice(0, 10)}...</code>
            <span>{r.dataset}</span>
            <span>{r.model}</span>
            <span>{r.status}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function JobsPanel(props: {
  jobs: JobItem[];
  polling: boolean;
  canQuery: boolean;
  onTogglePolling: () => void;
  onLoadJobs: () => void;
}) {
  return (
    <section className="panel">
      <h2>Jobs</h2>
      <div className="row">
        <button type="button" onClick={props.onLoadJobs} disabled={!props.canQuery}>Load Jobs</button>
        <button type="button" onClick={props.onTogglePolling} disabled={!props.canQuery}>
          {props.polling ? "Stop Polling" : "Start Polling"}
        </button>
      </div>
      <div className="table">
        {props.jobs.length === 0 && <p className="muted">No jobs loaded.</p>}
        {props.jobs.map((j) => (
          <div key={j.job_id} className="row spread">
            <code>{j.job_id.slice(0, 10)}...</code>
            <span>{j.job_type}</span>
            <span>{j.status}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function DebatePanel(props: {
  question: string;
  rounds: number;
  traceIdInput: string;
  run: DebateRun | null;
  traceSteps: DebateStep[];
  metrics: DebateMetrics | null;
  loading: boolean;
  canRun: boolean;
  canQuery: boolean;
  onQuestionChange: (v: string) => void;
  onRoundsChange: (v: number) => void;
  onTraceIdChange: (v: string) => void;
  onRunDebate: () => void;
  onLoadTrace: () => void;
  onLoadMetrics: () => void;
}) {
  return (
    <section className="panel">
      <h2>Agent Debate Trace</h2>
      <div className="stack">
        <textarea
          value={props.question}
          onChange={(e) => props.onQuestionChange(e.target.value)}
          rows={3}
          placeholder="Drought strategy for spring wheat in WKO"
        />
        <div className="row">
          <label>
            Rounds
            <input
              type="number"
              min={1}
              max={4}
              value={props.rounds}
              onChange={(e) => props.onRoundsChange(Number(e.target.value || 1))}
            />
          </label>
          <button type="button" onClick={props.onRunDebate} disabled={!props.canRun}>
            {props.loading ? "Running..." : "Run Debate"}
          </button>
          <button type="button" onClick={props.onLoadMetrics} disabled={!props.canQuery}>
            Load Metrics
          </button>
        </div>
      </div>

      {props.run && (
        <div className="compareCard">
          <p><strong>Trace:</strong> <code>{props.run.trace_id}</code></p>
          <p><strong>Digest:</strong> <code>{props.run.trace_digest}</code></p>
          <p><strong>Rounds:</strong> {props.run.rounds}</p>
          <p><strong>Spawned:</strong> {props.run.spawned_agents.join(", ")}</p>
          <p><strong>Safety:</strong> {props.run.safety.action} ({props.run.safety.level})</p>
          {props.run.safety.reasons.length > 0 && <p className="muted">{props.run.safety.reasons.join(" | ")}</p>}
          <p><strong>Winner:</strong> {props.run.winner} | A: {props.run.score_a.toFixed(3)} | B: {props.run.score_b.toFixed(3)}</p>
          <p>{props.run.answer}</p>
        </div>
      )}

      {props.metrics && (
        <div className="compareCard">
          <p><strong>Total runs:</strong> {props.metrics.total_runs}</p>
          <p><strong>Blocked runs:</strong> {props.metrics.blocked_runs}</p>
          <p><strong>Winner split:</strong> A={props.metrics.winner_a}, B={props.metrics.winner_b}</p>
          <p><strong>Avg latency:</strong> {props.metrics.avg_latency_ms.toFixed(2)} ms</p>
          <p><strong>Avg rounds:</strong> {props.metrics.avg_rounds.toFixed(2)} | <strong>Avg steps:</strong> {props.metrics.avg_steps.toFixed(2)}</p>
          {props.metrics.last_trace_id && <p><strong>Last trace:</strong> <code>{props.metrics.last_trace_id}</code></p>}
        </div>
      )}

      <div className="row">
        <input value={props.traceIdInput} onChange={(e) => props.onTraceIdChange(e.target.value)} placeholder="trace_id" />
        <button type="button" onClick={props.onLoadTrace} disabled={!props.traceIdInput.trim() || !props.canQuery}>
          Load Trace
        </button>
      </div>

      <div className="table">
        {props.traceSteps.length === 0 && <p className="muted">No trace loaded.</p>}
        {props.traceSteps.map((step) => (
          <div key={step.step_id} className="traceStep">
            <div className="row spread">
              <strong>{step.agent_name}</strong>
              <span>{step.step_type}</span>
            </div>
            <small>hash: {step.step_hash.slice(0, 16)}...</small>
            <small>parent: {step.parent_hash ? `${step.parent_hash.slice(0, 16)}...` : "GENESIS"}</small>
          </div>
        ))}
      </div>
    </section>
  );
}
