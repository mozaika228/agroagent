"use client";

import { FormEvent, useMemo, useState } from "react";

import { AuthPanel, ChatPanel, ComparePanel, DocumentsPanel, EvalsPanel, HeroPanel } from "./components/panels";
import { CompareResult, EvalItem, Msg, Source, UploadItem } from "./components/types";

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
      <HeroPanel apiBase={API_BASE} role={role} sessionId={sessionId} />

      <section className="grid two">
        <AuthPanel
          email={email}
          password={password}
          onEmailChange={setEmail}
          onPasswordChange={setPassword}
          onRegister={() => onRegister().catch((e) => setError(String(e)))}
          onLogin={() => onLogin().catch((e) => setError(String(e)))}
        />
        <DocumentsPanel
          uploads={uploads}
          canUpload={!!file && !!token}
          onUploadSubmit={onUploadDoc}
          onSelectFile={setFile}
          onRefresh={refreshDocument}
        />
      </section>

      <section className="grid two">
        <ChatPanel
          text={text}
          messages={messages}
          queryProfile={queryProfile}
          canSend={canSend}
          sending={sending}
          onTextChange={setText}
          onProfileChange={setQueryProfile}
          onSendChat={onSendChat}
          onRagQuery={onRagQuery}
          onCompare={onCompareRag}
        />
        <ComparePanel runId={lastCompareRunId} results={compareResults} />
      </section>

      <EvalsPanel
        evals={evals}
        evalRunId={evalRunId}
        canQuery={!!token}
        onLoadEvals={onLoadEvals}
        onEvalRunIdChange={setEvalRunId}
        onFetchById={onFetchEvalById}
      />

      {error && <section className="panel error">Error: {error}</section>}
    </main>
  );
}
