"use client";

import { FormEvent, useMemo, useState } from "react";

type Msg = { role: "user" | "assistant"; text: string };
type EvalItem = {
  run_id: string;
  dataset: string;
  model: string;
  status: string;
  sample_size: number;
  created_at: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function HomePage() {
  const [email, setEmail] = useState("farmer@example.com");
  const [password, setPassword] = useState("pass1234");
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadInfo, setUploadInfo] = useState<string>("");
  const [evals, setEvals] = useState<EvalItem[]>([]);
  const [evalRunId, setEvalRunId] = useState("");

  const canSend = useMemo(() => text.trim().length > 0 && !sending, [text, sending]);
  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

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
  }

  async function ensureSession(): Promise<string> {
    if (sessionId) return sessionId;

    const response = await fetch(`${API_BASE}/v1/chat/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify({ user_id: crypto.randomUUID(), locale: "ru" }) // user_id ignored in auth mode
    });

    if (!response.ok) {
      throw new Error(`session create failed (${response.status})`);
    }

    const data = await response.json();
    setSessionId(data.session_id);
    return data.session_id as string;
  }

  async function onSubmit(event: FormEvent) {
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
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ session_id: sid, text: prompt, locale: "ru", attachments: [] })
      });

      if (!response.ok) {
        throw new Error(`message send failed (${response.status})`);
      }

      const data = await response.json();
      setMessages((prev) => [...prev, { role: "assistant", text: data.answer as string }]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "unknown error";
      setError(msg);
      setMessages((prev) => [...prev, { role: "assistant", text: "API error. Check backend logs." }]);
    } finally {
      setSending(false);
    }
  }

  async function onUploadDoc(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("title", file.name);
      form.append("language", "ru");
      const response = await fetch(`${API_BASE}/v1/documents`, {
        method: "POST",
        headers: { ...authHeaders },
        body: form
      });
      if (!response.ok) {
        throw new Error(`upload failed (${response.status})`);
      }
      const data = await response.json();
      setUploadInfo(`Uploaded: ${data.document_id}, chunks: ${data.chunks ?? "n/a"}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "upload error");
    }
  }

  async function onRagQuery() {
    if (!text.trim()) return;
    setSending(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/rag/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ question: text.trim(), top_k: 5, locale: "ru" })
      });
      if (!response.ok) {
        throw new Error(`rag query failed (${response.status})`);
      }
      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        { role: "user", text: text.trim() },
        { role: "assistant", text: `${data.answer}\n\nSources: ${data.sources.length}` }
      ]);
      setText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "rag query error");
    } finally {
      setSending(false);
    }
  }

  async function onCompareRag() {
    if (!text.trim()) return;
    setSending(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/rag/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          question: text.trim(),
          top_k: 5,
          locale: "ru",
          profiles: ["balanced", "semantic_heavy", "lexical_heavy"]
        })
      });
      if (!response.ok) {
        throw new Error(`rag compare failed (${response.status})`);
      }
      const data = await response.json();
      const summary = (data.results as Array<{ profile: string; answer: string }>).map(
        (r) => `${r.profile}: ${r.answer.slice(0, 220)}...`
      );
      const maybeRunId = data.run_id ? `\n\nSaved run_id: ${data.run_id}` : "";
      setMessages((prev) => [
        ...prev,
        { role: "user", text: text.trim() },
        { role: "assistant", text: `A/B compare:\n${summary.join("\n\n")}${maybeRunId}` }
      ]);
      setText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "rag compare error");
    } finally {
      setSending(false);
    }
  }

  async function onLoadEvals() {
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/evals?limit=20`, { headers: { ...authHeaders } });
      if (!response.ok) {
        throw new Error(`eval list failed (${response.status})`);
      }
      const data = await response.json();
      setEvals((data.items ?? []) as EvalItem[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "eval list error");
    }
  }

  async function onFetchEvalById() {
    if (!evalRunId.trim()) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/evals/${evalRunId.trim()}`, { headers: { ...authHeaders } });
      if (!response.ok) {
        throw new Error(`eval detail failed (${response.status})`);
      }
      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Eval ${data.run_id}\nDataset: ${data.dataset}\nModel: ${data.model}\nStatus: ${data.status}\nMetrics: ${JSON.stringify(data.metrics)}`
        }
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "eval detail error");
    }
  }

  return (
    <main>
      <h1>AgroAgent MVP Chat</h1>
      <div className="card">
        <p>API: <code>{API_BASE}</code></p>
        <p>Role: <code>{role ?? "not authenticated"}</code></p>
        <p>Session: <code>{sessionId ?? "not created"}</code></p>
      </div>

      <div className="card">
        <h2>Auth</h2>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" style={{ width: "100%", marginBottom: 8 }} />
        <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" type="password" style={{ width: "100%", marginBottom: 8 }} />
        <button type="button" onClick={() => onRegister().catch((e) => setError(String(e)))} style={{ marginRight: 8 }}>Register</button>
        <button type="button" onClick={() => onLogin().catch((e) => setError(String(e)))}>Login</button>
      </div>

      <div className="card" style={{ minHeight: 240 }}>
        {messages.length === 0 && <p>No messages yet.</p>}
        {messages.map((m, i) => (
          <p key={`${m.role}-${i}`}><strong>{m.role === "user" ? "You" : "Agent"}:</strong> {m.text}</p>
        ))}
      </div>

      <form className="card" onSubmit={onSubmit}>
        <label htmlFor="prompt">Question</label>
        <textarea
          id="prompt"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          placeholder="What to sow in Uralsk in May?"
          style={{ width: "100%", marginTop: 8 }}
        />
        <button type="submit" disabled={!canSend} style={{ marginTop: 10, marginRight: 8 }}>
          {sending ? "Sending..." : "Send"}
        </button>
        <button type="button" disabled={!canSend} onClick={onRagQuery} style={{ marginTop: 10 }}>
          RAG Query
        </button>
        <button type="button" disabled={!canSend} onClick={onCompareRag} style={{ marginTop: 10, marginLeft: 8 }}>
          Compare Profiles
        </button>
        {error && <p style={{ color: "#8a1e1e" }}>Error: {error}</p>}
      </form>

      <form className="card" onSubmit={onUploadDoc}>
        <label htmlFor="doc">Upload PDF/TXT for RAG</label>
        <input
          id="doc"
          type="file"
          accept=".pdf,.txt,.md"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          style={{ display: "block", marginTop: 8 }}
        />
        <button type="submit" disabled={!file} style={{ marginTop: 10 }}>
          Upload
        </button>
        {uploadInfo && <p>{uploadInfo}</p>}
      </form>

      <div className="card">
        <h2>Eval History</h2>
        <button type="button" onClick={onLoadEvals}>Load Last 20</button>
        <div style={{ marginTop: 10 }}>
          <input
            value={evalRunId}
            onChange={(e) => setEvalRunId(e.target.value)}
            placeholder="run_id"
            style={{ width: "100%", marginBottom: 8 }}
          />
          <button type="button" onClick={onFetchEvalById} disabled={!evalRunId.trim()}>
            Load By Run ID
          </button>
        </div>
        {evals.length > 0 && (
          <div style={{ marginTop: 12 }}>
            {evals.map((r) => (
              <p key={r.run_id}>
                <code>{r.run_id}</code> | {r.dataset} | {r.model} | {r.status}
              </p>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
