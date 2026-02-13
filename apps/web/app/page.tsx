"use client";

import { FormEvent, useMemo, useState } from "react";

type Source = { doc_id: string; chunk_id: string; score: number };
type Msg = { role: "user" | "assistant"; text: string; sources?: Source[] };
type EvalItem = {
  run_id: string;
  dataset: string;
  model: string;
  status: string;
  sample_size: number;
  created_at: string;
};
type CompareResult = { profile: string; answer: string; sources: Source[] };
type UploadItem = { document_id: string; status: string; chunks?: number | null };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function HomePage() {
  const [email, setEmail] = useState("admin@agroagent.local");
  const [password, setPassword] = useState("pass1234");
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [uploads, setUploads] = useState<UploadItem[]>([]);

  const [queryProfile, setQueryProfile] = useState("balanced");
  const [compareResults, setCompareResults] = useState<CompareResult[]>([]);
  const [lastCompareRunId, setLastCompareRunId] = useState<string | null>(null);

  const [evals, setEvals] = useState<EvalItem[]>([]);
  const [evalRunId, setEvalRunId] = useState("");

  const canSend = useMemo(() => text.trim().length > 0 && !sending && !!token, [text, sending, token]);
  const authHeaders: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};

  function jsonHeaders(): HeadersInit {
    return token
      ? { "Content-Type": "application/json", Authorization: `Bearer ${token}` }
      : { "Content-Type": "application/json" };
  }

  function asErr(err: unknown) {
    return err instanceof Error ? err.message : "unknown error";
  }

  async function onRegister() {
    setError(null);
    const response = await fetch(`${API_BASE}/v1/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, role: "admin", locale: "ru" })
    });
    if (!response.ok) throw new Error(`register failed (${response.status})`);
    const data = await response.json();
    setToken(data.access_token as string);
    setRole(data.role as string);
    setMessages([]);
    setSessionId(null);
  }

  async function onLogin() {
    setError(null);
    const response = await fetch(`${API_BASE}/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    if (!response.ok) throw new Error(`login failed (${response.status})`);
    const data = await response.json();
    setToken(data.access_token as string);
    setRole(data.role as string);
    setMessages([]);
    setSessionId(null);
  }

  async function ensureSession(): Promise<string> {
    if (sessionId) return sessionId;

    const response = await fetch(`${API_BASE}/v1/chat/sessions`, {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({ locale: "ru" })
    });

    if (!response.ok) throw new Error(`session create failed (${response.status})`);

    const data = await response.json();
    setSessionId(data.session_id as string);
    return data.session_id as string;
  }

  async function onSendChat(event: FormEvent) {
    event.preventDefault();
    if (!canSend) return;

    const prompt = text.trim();
    setText("");
    setError(null);
    setSending(true);
    setMessages((prev) => [...prev, { role: "user", text: prompt }]);

    try {
      const sid = await ensureSession();
      const response = await fetch(`${API_BASE}/v1/chat/messages`, {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify({ session_id: sid, text: prompt, locale: "ru", attachments: [] })
      });

      if (!response.ok) throw new Error(`message send failed (${response.status})`);
      const data = await response.json();
      setMessages((prev) => [...prev, { role: "assistant", text: data.answer as string, sources: (data.sources ?? []) as Source[] }]);
    } catch (err) {
      setError(asErr(err));
      setMessages((prev) => [...prev, { role: "assistant", text: "API error. Check backend logs." }]);
    } finally {
      setSending(false);
    }
  }

  async function onUploadDoc(event: FormEvent) {
    event.preventDefault();
    if (!file || !token) return;
    setError(null);

    try {
      const form = new FormData();
      form.append("file", file);
      form.append("title", file.name);
      form.append("language", "ru");
      const response = await fetch(`${API_BASE}/v1/documents`, {
        method: "POST",
        headers: authHeaders,
        body: form
      });
      if (!response.ok) throw new Error(`upload failed (${response.status})`);
      const data = await response.json();
      setUploads((prev) => [{ document_id: data.document_id, status: data.status, chunks: data.chunks ?? null }, ...prev]);
      setFile(null);
    } catch (err) {
      setError(asErr(err));
    }
  }

  async function refreshDocument(documentId: string) {
    if (!token) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/documents/${documentId}`, { headers: authHeaders });
      if (!response.ok) throw new Error(`document refresh failed (${response.status})`);
      const data = await response.json();
      setUploads((prev) => prev.map((u) => (u.document_id === documentId ? { document_id: data.document_id, status: data.status, chunks: data.chunks ?? null } : u)));
    } catch (err) {
      setError(asErr(err));
    }
  }

  async function onRagQuery() {
    if (!text.trim() || !token) return;
    setSending(true);
    setError(null);
    try {
      const question = text.trim();
      const response = await fetch(`${API_BASE}/v1/rag/query`, {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify({ question, top_k: 5, locale: "ru", profile: queryProfile })
      });
      if (!response.ok) throw new Error(`rag query failed (${response.status})`);
      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        { role: "user", text: question },
        { role: "assistant", text: data.answer as string, sources: (data.sources ?? []) as Source[] }
      ]);
      setText("");
    } catch (err) {
      setError(asErr(err));
    } finally {
      setSending(false);
    }
  }

  async function onCompareRag() {
    if (!text.trim() || !token) return;
    setSending(true);
    setError(null);
    try {
      const question = text.trim();
      const response = await fetch(`${API_BASE}/v1/rag/compare`, {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify({
          question,
          top_k: 5,
          locale: "ru",
          profiles: ["balanced", "semantic_heavy", "lexical_heavy"],
          save_eval: true,
          dataset: "zko_farmers_v1",
          model: "retriever_hybrid_v1"
        })
      });
      if (!response.ok) throw new Error(`rag compare failed (${response.status})`);
      const data = await response.json();
      setCompareResults((data.results ?? []) as CompareResult[]);
      setLastCompareRunId((data.run_id as string | null) ?? null);
    } catch (err) {
      setError(asErr(err));
    } finally {
      setSending(false);
    }
  }

  async function onLoadEvals() {
    if (!token) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/evals?limit=20`, { headers: authHeaders });
      if (!response.ok) throw new Error(`eval list failed (${response.status})`);
      const data = await response.json();
      setEvals((data.items ?? []) as EvalItem[]);
    } catch (err) {
      setError(asErr(err));
    }
  }

  async function onFetchEvalById() {
    if (!evalRunId.trim() || !token) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/evals/${evalRunId.trim()}`, { headers: authHeaders });
      if (!response.ok) throw new Error(`eval detail failed (${response.status})`);
      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Eval ${data.run_id}\nDataset: ${data.dataset}\nModel: ${data.model}\nStatus: ${data.status}\nMetrics: ${JSON.stringify(data.metrics)}`
        }
      ]);
    } catch (err) {
      setError(asErr(err));
    }
  }

  return (
    <main className="layout">
      <header className="hero">
        <div>
          <h1>AgroAgent Fullstack Console</h1>
          <p>Chat, document ingestion, RAG query/compare, and eval tracking in one interface.</p>
        </div>
        <div className="meta">
          <div><span>API</span><code>{API_BASE}</code></div>
          <div><span>Role</span><code>{role ?? "not authenticated"}</code></div>
          <div><span>Session</span><code>{sessionId ?? "none"}</code></div>
        </div>
      </header>

      <section className="grid two">
        <article className="panel">
          <h2>Auth</h2>
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" />
          <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" type="password" />
          <div className="row">
            <button type="button" onClick={() => onRegister().catch((e) => setError(String(e)))}>Register</button>
            <button type="button" onClick={() => onLogin().catch((e) => setError(String(e)))}>Login</button>
          </div>
        </article>

        <article className="panel">
          <h2>Documents</h2>
          <form onSubmit={onUploadDoc} className="stack">
            <input type="file" accept=".pdf,.txt,.md" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            <button type="submit" disabled={!file || !token}>Upload</button>
          </form>
          <div className="table">
            {uploads.length === 0 && <p className="muted">No uploaded documents yet.</p>}
            {uploads.map((u) => (
              <div key={u.document_id} className="row spread">
                <code>{u.document_id.slice(0, 12)}...</code>
                <span>{u.status}</span>
                <span>{u.chunks ?? "-"} chunks</span>
                <button type="button" onClick={() => refreshDocument(u.document_id)}>Refresh</button>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="grid two">
        <article className="panel">
          <h2>Agent Chat</h2>
          <form onSubmit={onSendChat} className="stack">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={4}
              placeholder="What to sow in Uralsk in May?"
            />
            <div className="row">
              <button type="submit" disabled={!canSend}>{sending ? "Sending..." : "Send Chat"}</button>
              <select value={queryProfile} onChange={(e) => setQueryProfile(e.target.value)}>
                <option value="balanced">balanced</option>
                <option value="semantic_heavy">semantic_heavy</option>
                <option value="lexical_heavy">lexical_heavy</option>
              </select>
              <button type="button" onClick={onRagQuery} disabled={!canSend}>RAG Query</button>
              <button type="button" onClick={onCompareRag} disabled={!canSend}>Compare</button>
            </div>
          </form>

          <div className="chat">
            {messages.length === 0 && <p className="muted">No messages yet.</p>}
            {messages.map((m, i) => (
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

        <article className="panel">
          <h2>RAG Compare</h2>
          {lastCompareRunId && <p><strong>Saved Eval Run:</strong> <code>{lastCompareRunId}</code></p>}
          {compareResults.length === 0 && <p className="muted">Run compare to see profile outputs.</p>}
          {compareResults.map((r) => (
            <div key={r.profile} className="compareCard">
              <h3>{r.profile}</h3>
              <p>{r.answer}</p>
              <p className="muted">Sources: {r.sources.length}</p>
            </div>
          ))}
        </article>
      </section>

      <section className="panel">
        <h2>Eval History</h2>
        <div className="row">
          <button type="button" onClick={onLoadEvals} disabled={!token}>Load Last 20</button>
          <input value={evalRunId} onChange={(e) => setEvalRunId(e.target.value)} placeholder="run_id" />
          <button type="button" onClick={onFetchEvalById} disabled={!evalRunId.trim() || !token}>Load By Run ID</button>
        </div>
        <div className="table">
          {evals.length === 0 && <p className="muted">No eval runs loaded.</p>}
          {evals.map((r) => (
            <div key={r.run_id} className="row spread">
              <code>{r.run_id.slice(0, 10)}...</code>
              <span>{r.dataset}</span>
              <span>{r.model}</span>
              <span>{r.status}</span>
            </div>
          ))}
        </div>
      </section>

      {error && <section className="panel error">Error: {error}</section>}
    </main>
  );
}
