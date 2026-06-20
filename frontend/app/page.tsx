"use client";

import { Fragment, useCallback, useEffect, useRef, useState, type ReactNode, type ComponentType } from "react";
import {
  LayoutDashboard,
  Activity,
  AlertTriangle,
  GitPullRequest,
  Play,
  RefreshCw,
  Sun,
  Moon,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Github,
  Database,
  ExternalLink,
  Loader2,
  CheckCircle2,
  XCircle,
  Info,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

interface Metrics {
  total_sessions: number;
  active_sessions: number;
  autonomy_rate: number;
  outcome_rate: number;
  avg_cycle_time: number;
  total_acu_used: number;
  completed_sessions?: number;
  blocked_sessions?: number;
  failed_sessions?: number;
  outcome_breakdown?: { success?: number; blocked?: number; failed?: number };
}

interface StructuredOutput {
  summary?: string;
  pr_url?: string | null;
  files_changed?: string[];
  tests_run?: string[];
  test_result?: string;
  evidence?: string;
  needs_human?: boolean;
}

interface LogEntry {
  timestamp?: string;
  level?: string;
  event?: string;
  [key: string]: unknown;
}

interface Session {
  session_id: string;
  status: string;
  status_detail?: string | null;
  issue_url: string;
  repo_url?: string;
  branch: string;
  acu_used: number;
  human_msgs?: number;
  pr_url?: string | null;
  structured_output?: StructuredOutput | null;
  created_at: string;
  devin_session_id?: string | null;
}

interface Issue {
  issue_url: string;
  title: string;
  finding_type: string;
  dependency_name: string;
  severity: string;
  status: string;
  created_at: string;
}

interface PullRequest {
  number: number;
  title: string;
  html_url: string;
  head_ref: string;
  base_ref: string;
  additions: number;
  deletions: number;
  mergeable: boolean | null;
  mergeable_state: string;
  merged?: boolean;
  merged_at?: string | null;
}

type Point = { t: string; v: number };

type ToastVariant = "success" | "error" | "info";
interface Toast {
  id: number;
  variant: ToastVariant;
  title: string;
  message?: string;
}

interface Consumption {
  enabled: boolean;
  reason: string | null;
  total_acus: number | null;
  cap_per_session?: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const SUPERSET_URL = process.env.NEXT_PUBLIC_SUPERSET_URL || "";

const NAV: { id: string; label: string; icon: ComponentType<{ className?: string }> }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "sessions", label: "Sessions", icon: Activity },
  { id: "issues", label: "Issues", icon: AlertTriangle },
  { id: "pull-requests", label: "Pull Requests", icon: GitPullRequest },
  { id: "run", label: "Start a Run", icon: Play },
  { id: "superset", label: "Preview Superset", icon: Database },
];

const METRICS: { key: string; label: string; fmt: (v: number) => string; get: (m: Metrics | null) => number }[] = [
  { key: "total_sessions", label: "Total Sessions", fmt: (v) => String(Math.round(v)), get: (m) => m?.total_sessions ?? 0 },
  { key: "active_sessions", label: "Active Sessions", fmt: (v) => String(Math.round(v)), get: (m) => m?.active_sessions ?? 0 },
  { key: "autonomy_rate", label: "Autonomy Rate", fmt: (v) => `${v.toFixed(1)}%`, get: (m) => m?.autonomy_rate ?? 0 },
  { key: "outcome_rate", label: "Outcome Rate", fmt: (v) => `${v.toFixed(1)}%`, get: (m) => m?.outcome_rate ?? 0 },
  { key: "avg_cycle_time", label: "Avg Cycle Time", fmt: (v) => `${v.toFixed(0)}s`, get: (m) => m?.avg_cycle_time ?? 0 },
  { key: "total_acu_used", label: "ACU Used", fmt: (v) => v.toFixed(2), get: (m) => m?.total_acu_used ?? 0 },
];

const BADGE = "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium";
function statusBadge(status: string) {
  const s = status.toLowerCase();
  if (s === "finished" || s === "completed") return `${BADGE} bg-[var(--ok-bg)] text-[var(--ok-fg)]`;
  if (s === "error" || s === "failed") return `${BADGE} bg-[var(--err-bg)] text-[var(--err-fg)]`;
  if (s.startsWith("waiting") || s === "running" || s === "in_progress") return `${BADGE} bg-[var(--warn-bg)] text-[var(--warn-fg)]`;
  return `${BADGE} bg-[var(--neutral-bg)] text-[var(--neutral-fg)]`;
}
function severityBadge(sev: string) {
  const s = (sev || "").toLowerCase();
  if (s === "critical" || s === "high") return `${BADGE} bg-[var(--err-bg)] text-[var(--err-fg)]`;
  if (s === "medium") return `${BADGE} bg-[var(--warn-bg)] text-[var(--warn-fg)]`;
  return `${BADGE} bg-[var(--neutral-bg)] text-[var(--neutral-fg)]`;
}

const TH = "px-5 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-faint";
const TD = "px-5 py-3 align-middle text-fg";
const LINK = "text-[var(--accent)] hover:underline underline-offset-2";
const MONO = "font-mono text-xs text-muted";

const TOAST_STYLE: Record<ToastVariant, { Icon: LucideIcon; color: string }> = {
  success: { Icon: CheckCircle2, color: "var(--ok-fg)" },
  error: { Icon: XCircle, color: "var(--err-fg)" },
  info: { Icon: Info, color: "var(--accent)" },
};

export default function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [histories, setHistories] = useState<Record<string, Point[]>>({});
  const [sessions, setSessions] = useState<Session[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [pullRequests, setPullRequests] = useState<PullRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState("overview");
  const [dark, setDark] = useState(false);
  const [sessionQuery, setSessionQuery] = useState("");
  const [issueQuery, setIssueQuery] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [logs, setLogs] = useState<Record<string, LogEntry[]>>({});
  const [running, setRunning] = useState<null | "full" | "scan">(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastSeq = useRef(0);
  const [consumption, setConsumption] = useState<Consumption | null>(null);

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/metrics`);
      setMetrics(await res.json());
    } catch (error) {
      console.error("Failed to fetch metrics:", error);
    }
  }, []);

  const fetchHistories = useCallback(async () => {
    const out: Record<string, Point[]> = {};
    await Promise.all(
      METRICS.map(async (m) => {
        try {
          const res = await fetch(`${API_BASE}/metrics/history/${m.key}?hours=48`);
          const data = await res.json();
          const rows: { timestamp: string; metric_value: number }[] = Array.isArray(data) ? data : [];
          out[m.key] = rows
            .map((d) => ({ ts: new Date(d.timestamp).getTime(), v: d.metric_value }))
            .sort((a, b) => a.ts - b.ts)
            .map((p) => ({ t: new Date(p.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), v: p.v }));
        } catch (error) {
          console.error("Failed to fetch history:", m.key, error);
        }
      })
    );
    setHistories(out);
  }, []);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`);
      const data = await res.json();
      setSessions(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    }
  }, []);

  const fetchIssues = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/issues`);
      const data = await res.json();
      setIssues(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Failed to fetch issues:", error);
    }
  }, []);

  const fetchPullRequests = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/pull-requests`);
      const data = await res.json();
      setPullRequests(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Failed to fetch pull requests:", error);
    }
  }, []);

  const fetchConsumption = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/consumption`);
      setConsumption(await res.json());
    } catch (error) {
      console.error("Failed to fetch consumption:", error);
    }
  }, []);

  const refreshAll = useCallback(() => {
    fetchMetrics();
    fetchHistories();
    fetchSessions();
    fetchIssues();
    fetchPullRequests();
    fetchConsumption();
  }, [fetchConsumption, fetchHistories, fetchIssues, fetchMetrics, fetchPullRequests, fetchSessions]);

  const dismissToast = (id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const pushToast = (variant: ToastVariant, title: string, message?: string) => {
    const id = ++toastSeq.current;
    setToasts((prev) => [...prev, { id, variant, title, message }]);
    setTimeout(() => dismissToast(id), variant === "error" ? 6000 : 4000);
  };

  const startRun = async (scanOnly: boolean) => {
    setRunning(scanOnly ? "scan" : "full");
    try {
      const res = await fetch(`${API_BASE}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scan_only: scanOnly }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      pushToast(
        "success",
        scanOnly ? "Scan started" : "Scan & process started",
        data.run_id
          ? `Run ${String(data.run_id).slice(0, 8)} dispatched — results refresh below shortly.`
          : undefined
      );
      setTimeout(refreshAll, 2000);
    } catch (error) {
      console.error("Failed to start run:", error);
      pushToast("error", "Couldn't start run", "The backend didn't accept the request. Is the API running?");
    } finally {
      setRunning(null);
    }
  };

  const devinLink = (prompt: string) =>
    `https://app.devin.ai/?prompt=${encodeURIComponent(prompt)}`;

  const restartPrompt = (s: Session) =>
    `Re-run dependency remediation for this Superset issue: ${s.issue_url}. ` +
    `Re-investigate the vulnerability, implement the smallest safe fix on a new branch, ` +
    `run the targeted tests, and open or update a pull request against ${s.repo_url || "the fork"}. ` +
    `Prefer minimal changes and include test evidence in the PR body.`;

  const fetchSessionLogs = useCallback(async (sessionId: string) => {
    try {
      const res = await fetch(`${API_BASE}/logs/${sessionId}`);
      const data = await res.json();
      setLogs((prev) => ({ ...prev, [sessionId]: Array.isArray(data) ? data : [] }));
    } catch (error) {
      console.error("Failed to fetch session logs:", error);
    }
  }, []);

  const toggleSession = (s: Session) => {
    const next = expanded === s.session_id ? null : s.session_id;
    setExpanded(next);
    if (next && logs[s.session_id] === undefined) fetchSessionLogs(s.session_id);
  };

  const startSupersetPreview = async () => {
    if (!confirm("This starts a fresh Devin session that boots Superset in its sandbox (incurs Devin usage). Continue?")) return;
    try {
      const res = await fetch(`${API_BASE}/superset-preview`, { method: "POST" });
      if (!res.ok) {
        pushToast("error", "Couldn't start preview", "Is DEVIN_API_KEY configured on the backend?");
        return;
      }
      const data = await res.json();
      if (data.session_url) {
        window.open(data.session_url, "_blank", "noopener");
        pushToast(
          "info",
          "Fresh Devin session opened",
          "In the session, click “Approve” to expose Superset — Devin then posts a public URL (admin / admin)."
        );
      } else {
        pushToast("success", "Devin session created", data.session_id);
      }
    } catch (error) {
      console.error("Failed to start Superset preview:", error);
      pushToast("error", "Failed to start Superset preview");
    }
  };

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
    // Instant paint from last-known data so repeat visits aren't blank during a
    // cold backend start; refreshAll() below replaces it once the API responds.
    try {
      const cached = localStorage.getItem("dash_cache");
      if (cached) {
        const c = JSON.parse(cached);
        if (c.metrics) setMetrics(c.metrics);
        if (c.sessions) setSessions(c.sessions);
        if (c.issues) setIssues(c.issues);
        if (c.pullRequests) setPullRequests(c.pullRequests);
        if (c.histories) setHistories(c.histories);
      }
    } catch {
      /* ignore corrupt cache */
    }
    refreshAll();
    setLoading(false);
    const interval = setInterval(refreshAll, 30000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  // Persist last-known data to power the instant-paint above.
  useEffect(() => {
    try {
      localStorage.setItem(
        "dash_cache",
        JSON.stringify({ metrics, sessions, issues, pullRequests, histories })
      );
    } catch {
      /* quota or serialization issue — non-fatal */
    }
  }, [metrics, sessions, issues, pullRequests, histories]);

  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && setActive(e.target.id)),
      { rootMargin: "-45% 0px -50% 0px" }
    );
    NAV.forEach((n) => {
      const el = document.getElementById(n.id);
      if (el) obs.observe(el);
    });
    return () => obs.disconnect();
  }, [loading]);

  const goTo = (id: string) => {
    setActive(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const toggleTheme = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  };

  const mergeText = (m: boolean | null, state: string) =>
    m === true ? "Mergeable" : m === false ? "Conflicts" : state === "draft" ? "Draft" : "Checking";

  const sq = sessionQuery.toLowerCase();
  const filteredSessions = sessions.filter((s) =>
    [s.session_id, s.branch, s.status, s.issue_url].join(" ").toLowerCase().includes(sq)
  );
  const iq = issueQuery.toLowerCase();
  const filteredIssues = issues.filter((i) =>
    [i.title, i.dependency_name, i.severity, i.status, i.finding_type].join(" ").toLowerCase().includes(iq)
  );

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted">
        Loading dashboard…
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-line bg-[var(--sidebar)]">
        <div className="px-5 py-6" />

        <nav className="flex-1 space-y-0.5 px-3 py-2">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => goTo(id)}
              className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition ${
                active === id ? "bg-[var(--hover)] font-medium text-fg" : "text-muted hover:bg-[var(--hover)] hover:text-fg"
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </nav>

        <div className="border-t border-line p-3">
          <button
            onClick={toggleTheme}
            className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-muted transition hover:bg-[var(--hover)] hover:text-fg"
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            {dark ? "Light mode" : "Dark mode"}
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 border-b border-line bg-app px-8 py-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 text-xs text-faint">
              <span>Dashboard</span>
              <span>/</span>
              <span className="capitalize text-muted">{active.replace(/-/g, " ")}</span>
            </div>
            <a
              href="https://github.com/john7rho/superset"
              target="_blank"
              rel="noopener noreferrer"
              title="View the Superset fork on GitHub"
              className="inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1 text-xs font-medium text-muted transition hover:bg-[var(--hover)] hover:text-fg"
            >
              <Github className="h-3.5 w-3.5" />
              john7rho/superset
            </a>
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-fg">
              <span aria-hidden>🦫</span>
              Devin Demo on Superset
            </h1>
          </div>
        </header>

        <div className="space-y-8 px-8 py-7">
          {/* Overview — metric carousel */}
          <section id="overview" className="scroll-mt-28 space-y-5">
            <MetricsCarousel metrics={metrics} histories={histories} consumption={consumption} />
            <OutcomePanel metrics={metrics} pullRequests={pullRequests} />
          </section>

          {/* Sessions */}
          <Panel
            id="sessions"
            title="Sessions"
            count={filteredSessions.length}
            onRefresh={refreshAll}
            search={<SearchInput value={sessionQuery} onChange={setSessionQuery} placeholder="Search sessions…" />}
          >
            {filteredSessions.length === 0 ? (
              <Empty>{sessions.length === 0 ? "No sessions yet." : "No matching sessions."}</Empty>
            ) : (
              <Table head={["Session", "Status", "Issue", "Branch", "ACU", "Created", ""]}>
                {filteredSessions.map((s) => (
                  <Fragment key={s.session_id}>
                    <tr
                      onClick={() => toggleSession(s)}
                      className="cursor-pointer border-t border-line transition hover:bg-[var(--hover)]"
                    >
                      <td className={`${TD} ${MONO}`}>
                        <span className="inline-flex items-center gap-1.5">
                          <ChevronDown
                            className={`h-3.5 w-3.5 text-faint transition-transform ${expanded === s.session_id ? "rotate-180" : ""}`}
                          />
                          {s.session_id.substring(0, 8)}
                        </span>
                      </td>
                      <td className={TD}><span className={statusBadge(s.status)}>{s.status}</span></td>
                      <td className={TD}><a href={s.issue_url} onClick={(e) => e.stopPropagation()} target="_blank" rel="noopener noreferrer" className={LINK}>Issue</a></td>
                      <td className={`${TD} ${MONO}`}>{s.branch || "—"}</td>
                      <td className={`${TD} tabular-nums`}>{s.acu_used.toFixed(2)}</td>
                      <td className={`${TD} text-muted whitespace-nowrap`}>{new Date(s.created_at).toLocaleString()}</td>
                      <td className={`${TD} text-right`}>
                        {s.devin_session_id ? (
                          <a
                            href={`https://app.devin.ai/sessions/${s.devin_session_id.replace(/^devin-/, "")}`}
                            onClick={(e) => e.stopPropagation()}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-block whitespace-nowrap rounded-md border border-[var(--accent)] px-2.5 py-1 text-xs font-medium text-[var(--accent)] transition hover:bg-[var(--accent-soft-bg)]"
                          >
                            Open in Devin
                          </a>
                        ) : (
                          <span className="text-faint">—</span>
                        )}
                      </td>
                    </tr>
                    {expanded === s.session_id && (
                      <tr className="bg-[var(--thead)]">
                        <td colSpan={7} className="px-5 py-4">
                          <SessionDetail
                            session={s}
                            logs={logs[s.session_id]}
                            restartHref={devinLink(restartPrompt(s))}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </Table>
            )}
          </Panel>

          {/* Issues */}
          <Panel
            id="issues"
            title="Issues"
            count={filteredIssues.length}
            onRefresh={refreshAll}
            search={<SearchInput value={issueQuery} onChange={setIssueQuery} placeholder="Search issues…" />}
          >
            {filteredIssues.length === 0 ? (
              <Empty>{issues.length === 0 ? "No issues yet." : "No matching issues."}</Empty>
            ) : (
              <Table head={["Title", "Type", "Dependency", "Severity", "Status", "Created", ""]}>
                {filteredIssues.map((i) => (
                  <tr key={i.issue_url} className="border-t border-line transition hover:bg-[var(--hover)]">
                    <td className={TD}><a href={i.issue_url} target="_blank" rel="noopener noreferrer" className={LINK}>{i.title}</a></td>
                    <td className={`${TD} text-muted`}>{i.finding_type}</td>
                    <td className={`${TD} ${MONO}`}>{i.dependency_name || "—"}</td>
                    <td className={TD}>{i.severity ? <span className={severityBadge(i.severity)}>{i.severity}</span> : "—"}</td>
                    <td className={TD}><span className={statusBadge(i.status)}>{i.status}</span></td>
                    <td className={`${TD} text-muted`}>{new Date(i.created_at).toLocaleString()}</td>
                    <td className={`${TD} text-right`}>
                      <a
                        href={devinLink(`Work on this Superset issue: ${i.title} (${i.issue_url}). Investigate and fix the ${i.dependency_name} dependency vulnerability, then open a pull request.`)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-block whitespace-nowrap rounded-md border border-[var(--accent)] px-2.5 py-1 text-xs font-medium text-[var(--accent)] transition hover:bg-[var(--accent-soft-bg)]"
                      >
                        Open in Devin
                      </a>
                    </td>
                  </tr>
                ))}
              </Table>
            )}
          </Panel>

          {/* Pull Requests */}
          <Panel id="pull-requests" title="Pull Requests" count={pullRequests.length} onRefresh={refreshAll}>
            {pullRequests.length === 0 ? (
              <Empty>No pull requests yet.</Empty>
            ) : (
              <Table head={["PR", "Title", "Branch", "Merge", "Changes", ""]}>
                {pullRequests.map((pr) => (
                  <tr key={pr.number} className="border-t border-line transition hover:bg-[var(--hover)]">
                    <td className={`${TD} ${MONO}`}>#{pr.number}</td>
                    <td className={TD}><a href={pr.html_url} target="_blank" rel="noopener noreferrer" className={LINK}>{pr.title}</a></td>
                    <td className={`${TD} ${MONO}`}>{pr.head_ref} → {pr.base_ref}</td>
                    <td className={TD}>
                      {pr.merged ? (
                        <span className={`${BADGE} bg-[var(--ok-bg)] text-[var(--ok-fg)]`}>Merged</span>
                      ) : (
                        <span className={`${BADGE} bg-[var(--neutral-bg)] text-[var(--neutral-fg)]`}>{mergeText(pr.mergeable, pr.mergeable_state)}</span>
                      )}
                    </td>
                    <td className={`${TD} tabular-nums`}>
                      <span className="text-[var(--ok-fg)]">+{pr.additions}</span>
                      <span className="ml-2 text-[var(--err-fg)]">−{pr.deletions}</span>
                    </td>
                    <td className={`${TD} text-right`}>
                      <a href={pr.html_url} target="_blank" rel="noopener noreferrer" className="rounded-md border border-line px-2.5 py-1 text-xs font-medium text-fg transition hover:bg-[var(--hover)]">View</a>
                    </td>
                  </tr>
                ))}
              </Table>
            )}
          </Panel>

          {/* Start a Run */}
          <section id="run" className="scroll-mt-28">
            <div className="card rounded-xl p-6">
              <h2 className="text-sm font-semibold text-fg">Start a Run</h2>
              <p className="mt-1 text-sm text-muted">Scan the Superset fork for dependency issues and optionally dispatch Devin sessions.</p>
              <div className="mt-4 flex flex-wrap gap-2.5">
                <button
                  onClick={() => startRun(false)}
                  disabled={running !== null}
                  className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-fg)] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {running === "full" ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" /> Scanning…
                    </>
                  ) : (
                    "Scan & process"
                  )}
                </button>
                <button
                  onClick={() => startRun(true)}
                  disabled={running !== null}
                  className="inline-flex items-center gap-2 rounded-lg border border-line px-4 py-2 text-sm font-medium text-fg transition hover:bg-[var(--hover)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {running === "scan" ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" /> Scanning…
                    </>
                  ) : (
                    "Scan only"
                  )}
                </button>
              </div>
            </div>
          </section>

          {/* Preview Superset */}
          <section id="superset" className="scroll-mt-28">
            <div className="card rounded-xl p-6">
              <h2 className="text-sm font-semibold text-fg">Preview Superset</h2>
              <p className="mt-1 text-sm text-muted">Verify the remediated Superset itself, with example data loaded.</p>
              {SUPERSET_URL ? (
                <a href={SUPERSET_URL} target="_blank" rel="noopener noreferrer" className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-fg)] transition hover:opacity-90">
                  <ExternalLink className="h-4 w-4" /> Open Superset
                </a>
              ) : (
                <div className="mt-4 space-y-4">
                  <div>
                    <div className="text-xs font-medium uppercase tracking-wider text-faint">Option A · run locally with Docker</div>
                    <pre className="mt-2 overflow-x-auto rounded-lg border border-line bg-[var(--thead)] px-4 py-3 text-xs text-fg">{`cd superset-preview && docker compose up
# first boot loads example dashboards (a few min)
# then open http://localhost:8088   (admin / admin)`}</pre>
                  </div>
                  <div>
                    <div className="text-xs font-medium uppercase tracking-wider text-faint">Option B · spin it up in a Devin session</div>
                    <p className="mt-1 text-sm text-muted">Boots Superset + example data in a fresh Devin sandbox and opens the session. Click <span className="font-medium text-fg">Approve</span> in the session to expose the port; Devin then posts a public URL (admin / admin). Sessions are ephemeral.</p>
                    <button onClick={startSupersetPreview} className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent)] transition hover:bg-[var(--accent-soft-bg)]">
                      <ExternalLink className="h-4 w-4" /> Spin up Superset in Devin
                    </button>
                  </div>
                </div>
              )}
            </div>
          </section>

          <footer className="pb-2 text-center text-xs text-faint">Auto-refreshes every 30s.</footer>
        </div>
      </main>

      <ToastViewport toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

function MetricsCarousel({ metrics, histories, consumption }: { metrics: Metrics | null; histories: Record<string, Point[]>; consumption: Consumption | null }) {
  const [idx, setIdx] = useState(0);
  const m = METRICS[idx];
  const data = histories[m.key] || [];
  const move = (d: number) => setIdx((idx + d + METRICS.length) % METRICS.length);
  const isAcu = m.key === "total_acu_used";
  const acuUnavailable = isAcu && !(consumption?.enabled && consumption.total_acus != null);
  const cap = consumption?.cap_per_session;

  return (
    <div className="card rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs font-medium uppercase tracking-wider text-faint">{m.label}</div>
          {acuUnavailable ? (
            <>
              <div className="mt-1 text-3xl font-semibold tabular-nums text-faint">—</div>
              <div className="mt-0.5 text-xs text-faint">Consumed: not entitled (403){cap ? ` · cap ${cap}/session` : ""}</div>
            </>
          ) : (
            <>
              <div className="mt-1 text-3xl font-semibold tabular-nums text-fg">{m.fmt(m.get(metrics))}</div>
              <div className="mt-0.5 text-xs text-faint">Last 48 hours</div>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => move(-1)} aria-label="Previous metric" className="rounded-md border border-line p-1.5 text-muted transition hover:bg-[var(--hover)] hover:text-fg">
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-xs tabular-nums text-faint">{idx + 1} / {METRICS.length}</span>
          <button onClick={() => move(1)} aria-label="Next metric" className="rounded-md border border-line p-1.5 text-muted transition hover:bg-[var(--hover)] hover:text-fg">
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="mt-4 w-full" style={{ height: 220 }}>
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={data} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
              <defs>
                <linearGradient id="metricFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.22} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" vertical={false} />
              <XAxis dataKey="t" tick={{ fontSize: 11, fill: "var(--faint)" }} tickLine={false} axisLine={false} minTickGap={28} />
              <YAxis tick={{ fontSize: 11, fill: "var(--faint)" }} tickLine={false} axisLine={false} width={44} />
              <Tooltip
                contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12, color: "var(--fg)" }}
                labelStyle={{ color: "var(--muted)" }}
                formatter={(value) => [m.fmt(Number(value ?? 0)), m.label]}
              />
              <Area type="monotone" dataKey="v" stroke="#3b82f6" strokeWidth={2} fill="url(#metricFill)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-[220px] items-center justify-center text-sm text-faint">No history yet.</div>
        )}
      </div>

      <div className="mt-3 flex justify-center gap-1.5">
        {METRICS.map((_, i) => (
          <button
            key={i}
            onClick={() => setIdx(i)}
            aria-label={`Go to metric ${i + 1}`}
            className={`h-1.5 rounded-full transition-all ${i === idx ? "w-5 bg-[var(--accent)]" : "w-1.5 bg-[var(--line)]"}`}
          />
        ))}
      </div>
    </div>
  );
}

function SearchInput({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-48 rounded-md border border-line bg-transparent py-1.5 pl-8 pr-2.5 text-xs text-fg placeholder:text-faint focus:border-[var(--muted)] focus:outline-none"
      />
    </div>
  );
}

function Panel({
  id,
  title,
  count,
  onRefresh,
  search,
  children,
}: {
  id: string;
  title: string;
  count?: number;
  onRefresh?: () => void;
  search?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-28">
      <div className="card overflow-hidden rounded-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-fg">{title}</h2>
            {count != null && (
              <span className="rounded-full bg-[var(--neutral-bg)] px-2 py-0.5 text-xs font-medium tabular-nums text-[var(--neutral-fg)]">
                {count}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {search}
            {onRefresh && (
              <button
                onClick={onRefresh}
                className="inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-xs font-medium text-muted transition hover:bg-[var(--hover)] hover:text-fg"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Refresh
              </button>
            )}
          </div>
        </div>
        {children}
      </div>
    </section>
  );
}

function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-[var(--thead)]">
          <tr>
            {head.map((h, idx) => (
              <th key={idx} className={`${TH} ${idx === head.length - 1 ? "text-right" : ""}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <div className="px-5 py-12 text-center text-sm text-faint">{children}</div>;
}

function SessionDetail({
  session,
  logs,
  restartHref,
}: {
  session: Session;
  logs?: LogEntry[];
  restartHref: string;
}) {
  const so = session.structured_output || null;
  const pr = session.pr_url || so?.pr_url || null;
  const devinSessionHref = session.devin_session_id
    ? `https://app.devin.ai/sessions/${session.devin_session_id.replace(/^devin-/, "")}`
    : null;
  const ACTION =
    "rounded-md border border-line px-2.5 py-1 text-xs font-medium text-fg transition hover:bg-[var(--hover)]";

  return (
    <div className="grid gap-5 md:grid-cols-2">
      {/* State + structured output + actions */}
      <div className="space-y-3 text-xs">
        <div className="flex flex-wrap gap-x-6 gap-y-1.5 text-muted">
          <span>Detail: <span className="text-fg">{session.status_detail || "—"}</span></span>
          <span>Human msgs: <span className="tabular-nums text-fg">{session.human_msgs ?? 0}</span></span>
          <span>ACU: <span className="tabular-nums text-fg">{session.acu_used.toFixed(2)}</span></span>
          {so?.test_result && <span>Tests: <span className="text-fg">{so.test_result}</span></span>}
          {so?.needs_human != null && (
            <span>Needs human: <span className="text-fg">{so.needs_human ? "yes" : "no"}</span></span>
          )}
        </div>

        {so?.summary && (
          <div>
            <div className="font-medium uppercase tracking-wider text-faint">Summary</div>
            <p className="mt-1 text-fg">{so.summary}</p>
          </div>
        )}

        {so?.files_changed && so.files_changed.length > 0 && (
          <div>
            <div className="font-medium uppercase tracking-wider text-faint">Files changed</div>
            <ul className="mt-1 space-y-0.5 font-mono text-fg">
              {so.files_changed.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </div>
        )}

        {so?.evidence && (
          <div>
            <div className="font-medium uppercase tracking-wider text-faint">Evidence</div>
            <p className="mt-1 whitespace-pre-wrap text-muted">{so.evidence}</p>
          </div>
        )}

        <div className="flex flex-wrap gap-2 pt-1">
          <a
            href={restartHref}
            onClick={(e) => e.stopPropagation()}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-md border border-[var(--accent)] px-2.5 py-1 text-xs font-medium text-[var(--accent)] transition hover:bg-[var(--accent-soft-bg)]"
          >
            Restart in Devin
          </a>
          {devinSessionHref && (
            <a href={devinSessionHref} onClick={(e) => e.stopPropagation()} target="_blank" rel="noopener noreferrer" className={ACTION}>
              Resume session
            </a>
          )}
          {pr && (
            <a href={pr} onClick={(e) => e.stopPropagation()} target="_blank" rel="noopener noreferrer" className={ACTION}>
              View PR
            </a>
          )}
          <a href={session.issue_url} onClick={(e) => e.stopPropagation()} target="_blank" rel="noopener noreferrer" className={ACTION}>
            View issue
          </a>
        </div>
      </div>

      {/* Logs tagged with this session_id */}
      <div>
        <div className="text-xs font-medium uppercase tracking-wider text-faint">
          Logs <span className="normal-case text-faint">· tagged with session_id</span>
        </div>
        <div className="mt-1 max-h-56 overflow-auto rounded-lg border border-line bg-app p-2 font-mono text-[11px] leading-relaxed">
          {logs === undefined ? (
            <div className="text-faint">Loading logs…</div>
          ) : logs.length === 0 ? (
            <div className="text-faint">No logs tagged with this session_id.</div>
          ) : (
            logs.map((l, i) => (
              <div key={i} className="whitespace-pre-wrap text-muted">
                <span className="text-faint">{l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : ""}</span>{" "}
                <span className="text-fg">{l.event || JSON.stringify(l)}</span>
                {l.level ? <span className="text-faint"> [{l.level}]</span> : null}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function ToastViewport({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  if (toasts.length === 0) return null;
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
      {toasts.map((t) => {
        const { Icon, color } = TOAST_STYLE[t.variant];
        return (
          <div
            key={t.id}
            role="status"
            aria-live="polite"
            className="toast-in card pointer-events-auto flex items-start gap-3 rounded-xl border-l-2 p-3.5 shadow-lg"
            style={{ borderLeftColor: color }}
          >
            <Icon className="mt-0.5 h-4 w-4 shrink-0" style={{ color }} />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-fg">{t.title}</div>
              {t.message && <div className="mt-0.5 break-words text-xs text-muted">{t.message}</div>}
            </div>
            <button
              onClick={() => onDismiss(t.id)}
              aria-label="Dismiss notification"
              className="-m-1 rounded p-1 text-faint transition hover:bg-[var(--hover)] hover:text-fg"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

function OutcomePanel({
  metrics,
  pullRequests,
}: {
  metrics: Metrics | null;
  pullRequests: PullRequest[];
}) {
  const bd = metrics?.outcome_breakdown ?? {};
  const success = bd.success ?? metrics?.completed_sessions ?? 0;
  const blocked = bd.blocked ?? metrics?.blocked_sessions ?? 0;
  const failed = bd.failed ?? metrics?.failed_sessions ?? 0;
  const totalSessions = metrics?.total_sessions ?? success + blocked + failed;

  const merged = pullRequests.filter((p) => p.merged).length;
  const deliveryDenom = totalSessions || pullRequests.length || 1;
  const deliveryPct = Math.round((merged / deliveryDenom) * 100);

  const seg = success + blocked + failed || 1;
  const STATE = [
    { label: "finished", n: success, color: "var(--ok-fg)" },
    { label: "blocked", n: blocked, color: "var(--warn-fg)" },
    { label: "failed", n: failed, color: "var(--err-fg)" },
  ];

  return (
    <div className="card rounded-xl p-5 sm:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-fg">Outcomes &amp; delivery</h2>
        <span className="text-xs tabular-nums text-faint">{totalSessions} sessions</span>
      </div>

      {/* Hero — delivery is the business outcome, the thing that actually matters */}
      <div className="mt-5">
        <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-faint">Delivered to master</div>
        <div className="mt-2 flex items-end justify-between gap-4">
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-semibold leading-none tabular-nums text-fg">{merged}</span>
            <span className="text-2xl font-semibold leading-none tabular-nums text-faint">/ {deliveryDenom}</span>
            <span className="pb-0.5 text-sm text-muted">merged</span>
          </div>
          <span className="text-2xl font-semibold leading-none tabular-nums text-[var(--ok-fg)]">{deliveryPct}%</span>
        </div>
        <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[var(--neutral-bg)]">
          <div
            className="h-full rounded-full bg-[var(--ok-fg)] transition-[width] duration-500"
            style={{ width: `${deliveryPct}%` }}
          />
        </div>
        <div className="mt-2 text-xs text-muted">{merged} findings shipped with regression tests · from GitHub</div>
      </div>

      {/* Secondary — session state, deliberately quiet and contrasted with delivery above */}
      <div className="mt-5 border-t border-line pt-4">
        <div className="flex items-center justify-between gap-3">
          <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-faint">Session state</div>
          <div className="text-[11px] text-faint">all parked at the human merge gate</div>
        </div>
        <div className="mt-2 flex h-1.5 w-full overflow-hidden rounded-full bg-[var(--neutral-bg)]">
          {STATE.map((s) =>
            s.n > 0 ? <div key={s.label} style={{ width: `${(s.n / seg) * 100}%`, background: s.color }} /> : null
          )}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          {STATE.map((s) => (
            <span key={s.label} className="inline-flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.color }} />
              <span className="tabular-nums text-fg">{s.n}</span> {s.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
