"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AuthPanel, ChatPanel, ComparePanel, DebatePanel, DocumentsPanel, EvalsPanel, HeroPanel, JobsPanel, SafetyBenchmarkPanel } from "./components/panels";
import { CompareResult, DebateMetrics, DebateRun, DebateStep, EvalItem, JobItem, Msg, SafetyEvalResult, Source, UploadItem } from "./components/types";

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
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [pollJobs, setPollJobs] = useState(false);
  const [debateQuestion, setDebateQuestion] = useState("Drought strategy for spring wheat in WKO");
  const [debateRounds, setDebateRounds] = useState(2);
  const [debateSafetyOverride, setDebateSafetyOverride] = useState(false);
  const [debateOverrideReason, setDebateOverrideReason] = useState("");
  const [debateTraceId, setDebateTraceId] = useState("");
  const [debateRun, setDebateRun] = useState<DebateRun | null>(null);
  const [debateSteps, setDebateSteps] = useState<DebateStep[]>([]);
  const [debateMetrics, setDebateMetrics] = useState<DebateMetrics | null>(null);
  const [debateLoading, setDebateLoading] = useState(false);
  const [debateStreaming, setDebateStreaming] = useState(false);
  const [debateStreamError, setDebateStreamError] = useState<string | null>(null);
  const [safetyEvalRounds, setSafetyEvalRounds] = useState(2);
  const [safetyEvalExportReport, setSafetyEvalExportReport] = useState(true);
  const [safetyEvalLoading, setSafetyEvalLoading] = useState(false);
  const [safetyEvalResult, setSafetyEvalResult] = useState<SafetyEvalResult | null>(null);

  const canSend = useMemo(() => text.trim().length > 0 && !sending && !!token, [text, sending, token]);
  const authHeaders = useMemo(() => {
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return headers;
  }, [token]);

  function jsonHeaders(): HeadersInit {
    return token
      ? { "Content-Type": "application/json", Authorization: `Bearer ${token}` }
      : { "Content-Type": "application/json" };
  }

  function asErr(err: unknown) {
    return err instanceof Error ? err.message : "unknown error";
  }

  useEffect(() => {
    const savedToken = localStorage.getItem("agroagent.token");
    const savedRole = localStorage.getItem("agroagent.role");
    const savedEmail = localStorage.getItem("agroagent.email");
    if (savedToken) setToken(savedToken);
    if (savedRole) setRole(savedRole);
    if (savedEmail) setEmail(savedEmail);
  }, []);

  useEffect(() => {
    if (token) localStorage.setItem("agroagent.token", token);
    else localStorage.removeItem("agroagent.token");
  }, [token]);

  useEffect(() => {
    if (role) localStorage.setItem("agroagent.role", role);
    else localStorage.removeItem("agroagent.role");
  }, [role]);

  useEffect(() => {
    localStorage.setItem("agroagent.email", email);
  }, [email]);

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

  function onLogout() {
    setToken(null);
    setRole(null);
    setSessionId(null);
    setMessages([]);
    setUploads([]);
    setCompareResults([]);
    setLastCompareRunId(null);
    setEvals([]);
    setJobs([]);
    setDebateRun(null);
    setDebateSteps([]);
    setDebateMetrics(null);
    setDebateSafetyOverride(false);
    setDebateOverrideReason("");
    setDebateTraceId("");
    setDebateStreaming(false);
    setDebateStreamError(null);
    setSafetyEvalResult(null);
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

  const onLoadJobs = useCallback(async () => {
    if (!token) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/jobs?limit=20`, { headers: authHeaders });
      if (!response.ok) throw new Error(`jobs list failed (${response.status})`);
      const data = await response.json();
      setJobs((data.items ?? []) as JobItem[]);
    } catch (err) {
      setError(asErr(err));
    }
  }, [token, authHeaders]);

  useEffect(() => {
    if (!pollJobs || !token) return;
    const id = setInterval(() => {
      onLoadJobs().catch(() => undefined);
    }, 5000);
    return () => clearInterval(id);
  }, [pollJobs, token, onLoadJobs]);

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

  async function onRunDebate() {
    if (!debateQuestion.trim() || !token) return;
    setError(null);
    setDebateLoading(true);
    setDebateStreamError(null);
    setDebateRun(null);
    setDebateSteps([]);

    const wsBase = API_BASE.startsWith("https")
      ? API_BASE.replace("https", "wss")
      : API_BASE.replace("http", "ws");

    const runStream = () =>
      new Promise<boolean>((resolve) => {
        const ws = new WebSocket(`${wsBase}/v1/ws/agents/debate?token=${encodeURIComponent(token)}`);
        let resolved = false;
        ws.onopen = () => {
          setDebateStreaming(true);
          ws.send(
            JSON.stringify({
              question: debateQuestion.trim(),
              locale: "ru",
              include_steps: true,
              rounds: debateRounds,
              safety_override: debateSafetyOverride,
              override_reason: debateSafetyOverride ? debateOverrideReason : null
            })
          );
        };
        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data as string);
            if (msg.type === "step") {
              setDebateSteps((prev) => [...prev, msg.data as DebateStep]);
            }
            if (msg.type === "final") {
              const run = msg.data as DebateRun;
              setDebateRun(run);
              setDebateTraceId(run.trace_id);
              setDebateSteps(run.steps ?? []);
              setDebateStreaming(false);
              setDebateLoading(false);
              if (!resolved) {
                resolved = true;
                resolve(true);
              }
              ws.close();
            }
            if (msg.type === "error") {
              setDebateStreamError(String(msg.message ?? "stream error"));
              setDebateStreaming(false);
              setDebateLoading(false);
              if (!resolved) {
                resolved = true;
                resolve(false);
              }
              ws.close();
            }
          } catch (parseErr) {
            setDebateStreamError(String(parseErr));
          }
        };
        ws.onerror = () => {
          setDebateStreamError("websocket failed");
          setDebateStreaming(false);
          setDebateLoading(false);
          if (!resolved) {
            resolved = true;
            resolve(false);
          }
        };
        ws.onclose = () => {
          setDebateStreaming(false);
          setDebateLoading(false);
        };
      });

    const streamOk = await runStream();
    if (streamOk) return;

    try {
      const response = await fetch(`${API_BASE}/v1/agents/debate`, {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify({
          question: debateQuestion.trim(),
          locale: "ru",
          include_steps: true,
          rounds: debateRounds,
          safety_override: debateSafetyOverride,
          override_reason: debateSafetyOverride ? debateOverrideReason : null
        })
      });
      if (!response.ok) throw new Error(`agent debate failed (${response.status})`);
      const data = await response.json();
      const run = data as DebateRun;
      setDebateRun(run);
      setDebateTraceId(run.trace_id);
      setDebateSteps(run.steps ?? []);
    } catch (err) {
      setError(asErr(err));
    } finally {
      setDebateLoading(false);
    }
  }

  async function onLoadDebateTrace() {
    if (!debateTraceId.trim() || !token) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/agents/traces/${debateTraceId.trim()}`, { headers: authHeaders });
      if (!response.ok) throw new Error(`trace load failed (${response.status})`);
      const data = await response.json();
      setDebateSteps((data.steps ?? []) as DebateStep[]);
    } catch (err) {
      setError(asErr(err));
    }
  }

  async function onLoadDebateMetrics() {
    if (!token) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/agents/metrics`, { headers: authHeaders });
      if (!response.ok) throw new Error(`metrics load failed (${response.status})`);
      const data = await response.json();
      setDebateMetrics(data as DebateMetrics);
    } catch (err) {
      setError(asErr(err));
    }
  }

  async function onRunSafetyEval() {
    if (!token) return;
    setError(null);
    setSafetyEvalLoading(true);
    try {
      const response = await fetch(`${API_BASE}/v1/agents/safety/evals/run`, {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify({
          rounds: safetyEvalRounds,
          save_eval: true,
          model: "safety_policy_v1",
          export_report: safetyEvalExportReport
        })
      });
      if (!response.ok) throw new Error(`safety eval failed (${response.status})`);
      const data = await response.json();
      setSafetyEvalResult(data as SafetyEvalResult);
    } catch (err) {
      setError(asErr(err));
    } finally {
      setSafetyEvalLoading(false);
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
          onLogout={onLogout}
          isAuthed={!!token}
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

      <JobsPanel
        jobs={jobs}
        polling={pollJobs}
        canQuery={!!token}
        onLoadJobs={() => onLoadJobs().catch((e) => setError(String(e)))}
        onTogglePolling={() => setPollJobs((v) => !v)}
      />

      <DebatePanel
        question={debateQuestion}
        rounds={debateRounds}
        safetyOverride={debateSafetyOverride}
        overrideReason={debateOverrideReason}
        traceIdInput={debateTraceId}
        run={debateRun}
        traceSteps={debateSteps}
        metrics={debateMetrics}
        loading={debateLoading}
        streaming={debateStreaming}
        streamError={debateStreamError}
        canRun={
          !!token &&
          !debateLoading &&
          debateQuestion.trim().length > 0 &&
          (!debateSafetyOverride || debateOverrideReason.trim().length >= 8)
        }
        canQuery={!!token}
        onQuestionChange={setDebateQuestion}
        onRoundsChange={(v) => setDebateRounds(Math.max(1, Math.min(4, v || 1)))}
        onSafetyOverrideChange={setDebateSafetyOverride}
        onOverrideReasonChange={setDebateOverrideReason}
        onTraceIdChange={setDebateTraceId}
        onRunDebate={() => onRunDebate().catch((e) => setError(String(e)))}
        onLoadTrace={() => onLoadDebateTrace().catch((e) => setError(String(e)))}
        onLoadMetrics={() => onLoadDebateMetrics().catch((e) => setError(String(e)))}
      />

      <SafetyBenchmarkPanel
        rounds={safetyEvalRounds}
        exportReport={safetyEvalExportReport}
        loading={safetyEvalLoading}
        canRun={!!token && !safetyEvalLoading}
        result={safetyEvalResult}
        onRoundsChange={(v) => setSafetyEvalRounds(Math.max(1, Math.min(4, v || 1)))}
        onExportReportChange={setSafetyEvalExportReport}
        onRun={() => onRunSafetyEval().catch((e) => setError(String(e)))}
      />

      {error && <section className="panel error">Error: {error}</section>}
    </main>
  );
}
