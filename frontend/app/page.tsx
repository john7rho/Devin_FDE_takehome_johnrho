"use client";

import { useCallback, useEffect, useState, type ReactNode, type ComponentType } from "react";
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
  Github,
  Database,
  ExternalLink,
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
}

interface Session {
  session_id: string;
  status: string;
  issue_url: string;
  branch: string;
  acu_used: number;
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
}

type Point = { t: string; v: number };

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

  const refreshAll = useCallback(() => {
    fetchMetrics();
    fetchHistories();
    fetchSessions();
    fetchIssues();
    fetchPullRequests();
  }, [fetchHistories, fetchIssues, fetchMetrics, fetchPullRequests, fetchSessions]);

  const startRun = async (scanOnly: boolean) => {
    try {
      const res = await fetch(`${API_BASE}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scan_only: scanOnly }),
      });
      const data = await res.json();
      alert(`Run started: ${data.run_id}`);
      setTimeout(refreshAll, 2000);
    } catch (error) {
      console.error("Failed to start run:", error);
      alert("Failed to start run");
    }
  };

  const devinLink = (prompt: string) =>
    `https://app.devin.ai/?prompt=${encodeURIComponent(prompt)}`;

  const startSupersetPreview = async () => {
    if (!confirm("This starts a real Devin session (uses ACUs) that boots Superset in its sandbox. Continue?")) return;
    try {
      const res = await fetch(`${API_BASE}/superset-preview`, { method: "POST" });
      if (!res.ok) {
        alert("Could not start — is DEVIN_API_KEY configured on the backend?");
        return;
      }
      const data = await res.json();
      if (data.session_url) window.open(data.session_url, "_blank", "noopener");
      else alert(`Devin session created: ${data.session_id}`);
    } catch (error) {
      console.error("Failed to start Superset preview:", error);
      alert("Failed to start Superset preview");
    }
  };

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
    refreshAll();
    setLoading(false);
    const interval = setInterval(refreshAll, 30000);
    return () => clearInterval(interval);
  }, [refreshAll]);

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
          <section id="overview" className="scroll-mt-28">
            <MetricsCarousel metrics={metrics} histories={histories} />
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
                  <tr key={s.session_id} className="border-t border-line transition hover:bg-[var(--hover)]">
                    <td className={`${TD} ${MONO}`}>{s.session_id.substring(0, 8)}</td>
                    <td className={TD}><span className={statusBadge(s.status)}>{s.status}</span></td>
                    <td className={TD}><a href={s.issue_url} target="_blank" rel="noopener noreferrer" className={LINK}>Issue</a></td>
                    <td className={`${TD} ${MONO}`}>{s.branch || "—"}</td>
                    <td className={`${TD} tabular-nums`}>{s.acu_used.toFixed(2)}</td>
                    <td className={`${TD} text-muted whitespace-nowrap`}>{new Date(s.created_at).toLocaleString()}</td>
                    <td className={`${TD} text-right`}>
                      {s.devin_session_id ? (
                        <a
                          href={`https://app.devin.ai/sessions/${s.devin_session_id.replace(/^devin-/, "")}`}
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
                    <td className={TD}><span className={`${BADGE} bg-[var(--neutral-bg)] text-[var(--neutral-fg)]`}>{mergeText(pr.mergeable, pr.mergeable_state)}</span></td>
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
                <button onClick={() => startRun(false)} className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-fg)] transition hover:opacity-90">
                  Scan &amp; process
                </button>
                <button onClick={() => startRun(true)} className="rounded-lg border border-line px-4 py-2 text-sm font-medium text-fg transition hover:bg-[var(--hover)]">
                  Scan only
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
                    <p className="mt-1 text-sm text-muted">Devin boots Superset + example data in its sandbox; opens the Devin session to watch or collaborate (needs a Devin seat). Uses ACUs.</p>
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
    </div>
  );
}

function MetricsCarousel({ metrics, histories }: { metrics: Metrics | null; histories: Record<string, Point[]> }) {
  const [idx, setIdx] = useState(0);
  const m = METRICS[idx];
  const data = histories[m.key] || [];
  const move = (d: number) => setIdx((idx + d + METRICS.length) % METRICS.length);

  return (
    <div className="card rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs font-medium uppercase tracking-wider text-faint">{m.label}</div>
          <div className="mt-1 text-3xl font-semibold tabular-nums text-fg">{m.fmt(m.get(metrics))}</div>
          <div className="mt-0.5 text-xs text-faint">Last 48 hours</div>
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
