"use client";

import { useEffect, useState, type ReactNode, type ComponentType } from "react";
import {
  LayoutDashboard,
  Activity,
  AlertTriangle,
  GitPullRequest,
  Play,
  RefreshCw,
  Sun,
  Moon,
  Copy,
  Check,
} from "lucide-react";

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
  state: string;
  head_ref: string;
  base_ref: string;
  additions: number;
  deletions: number;
  mergeable: boolean | null;
  mergeable_state: string;
  reviewers: string[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const NAV: { id: string; label: string; icon: ComponentType<{ className?: string }> }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "sessions", label: "Sessions", icon: Activity },
  { id: "issues", label: "Issues", icon: AlertTriangle },
  { id: "pull-requests", label: "Pull Requests", icon: GitPullRequest },
  { id: "run", label: "Start a Run", icon: Play },
];

const BADGE = "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium";
function statusBadge(status: string) {
  const s = status.toLowerCase();
  if (s === "finished" || s === "completed") return `${BADGE} bg-[var(--ok-bg)] text-[var(--ok-fg)]`;
  if (s === "error" || s === "failed") return `${BADGE} bg-[var(--err-bg)] text-[var(--err-fg)]`;
  if (s.startsWith("waiting") || s === "running" || s === "in_progress")
    return `${BADGE} bg-[var(--warn-bg)] text-[var(--warn-fg)]`;
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
  const [sessions, setSessions] = useState<Session[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [pullRequests, setPullRequests] = useState<PullRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState("overview");
  const [dark, setDark] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/metrics`);
      setMetrics(await res.json());
    } catch (error) {
      console.error("Failed to fetch metrics:", error);
    }
  };

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`);
      const data = await res.json();
      setSessions(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    }
  };

  const fetchIssues = async () => {
    try {
      const res = await fetch(`${API_BASE}/issues`);
      const data = await res.json();
      setIssues(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Failed to fetch issues:", error);
    }
  };

  const fetchPullRequests = async () => {
    try {
      const res = await fetch(`${API_BASE}/pull-requests`);
      const data = await res.json();
      setPullRequests(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Failed to fetch pull requests:", error);
    }
  };

  const refreshAll = () => {
    fetchMetrics();
    fetchSessions();
    fetchIssues();
    fetchPullRequests();
  };

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

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
    refreshAll();
    setLoading(false);
    const interval = setInterval(refreshAll, 30000);
    return () => clearInterval(interval);
  }, []);

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

  const copyApi = () => {
    navigator.clipboard?.writeText(API_BASE);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const mergeText = (m: boolean | null, state: string) =>
    m === true ? "Mergeable" : m === false ? "Conflicts" : state === "draft" ? "Draft" : "Checking";

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
        <div className="flex items-center gap-2.5 px-5 py-5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--accent)] text-[var(--accent-fg)]">
            <Activity className="h-4 w-4" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-fg">Devin Automation</div>
            <div className="text-xs text-faint">Superset remediation</div>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 px-3 py-2">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => goTo(id)}
              className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition ${
                active === id
                  ? "bg-[var(--hover)] font-medium text-fg"
                  : "text-muted hover:bg-[var(--hover)] hover:text-fg"
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
          <div className="flex items-center gap-1.5 text-xs text-faint">
            <span>Dashboard</span>
            <span>/</span>
            <span className="capitalize text-muted">{active.replace(/-/g, " ")}</span>
          </div>
          <div className="mt-1 flex items-end justify-between gap-4">
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-fg">Devin Automation</h1>
              <p className="mt-0.5 text-sm text-muted">
                Event-driven Devin sessions remediating Superset dependency issues.
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <code className="rounded-md border border-line bg-[var(--thead)] px-2 py-1 text-xs text-muted">
                {API_BASE}
              </code>
              <button
                onClick={copyApi}
                title="Copy API base URL"
                className="rounded-md border border-line p-1.5 text-muted transition hover:bg-[var(--hover)] hover:text-fg"
              >
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>
        </header>

        <div className="space-y-8 px-8 py-7">
          {/* Overview */}
          <section id="overview" className="scroll-mt-28">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <MetricCard title="Total Sessions" value={metrics?.total_sessions ?? 0} subtitle="All time" icon={<Activity className="h-4 w-4" />} />
              <MetricCard title="Active" value={metrics?.active_sessions ?? 0} subtitle="Currently running" icon={<Play className="h-4 w-4" />} />
              <MetricCard title="Autonomy Rate" value={`${(metrics?.autonomy_rate ?? 0).toFixed(1)}%`} subtitle="Finished without a human" icon={<LayoutDashboard className="h-4 w-4" />} />
              <MetricCard title="Outcome Rate" value={`${(metrics?.outcome_rate ?? 0).toFixed(1)}%`} subtitle="Successful completions" icon={<GitPullRequest className="h-4 w-4" />} />
              <MetricCard title="Avg Cycle Time" value={`${(metrics?.avg_cycle_time ?? 0).toFixed(0)}s`} subtitle="Per session" icon={<RefreshCw className="h-4 w-4" />} />
              <MetricCard title="ACU Used" value={(metrics?.total_acu_used ?? 0).toFixed(2)} subtitle="Compute units consumed" icon={<AlertTriangle className="h-4 w-4" />} />
            </div>
          </section>

          {/* Sessions */}
          <Panel id="sessions" title="Sessions" count={sessions.length} onRefresh={refreshAll}>
            {sessions.length === 0 ? (
              <Empty>No sessions yet.</Empty>
            ) : (
              <Table head={["Session", "Status", "Issue", "Branch", "ACU", "Created"]}>
                {sessions.map((s) => (
                  <tr key={s.session_id} className="border-t border-line transition hover:bg-[var(--hover)]">
                    <td className={`${TD} ${MONO}`}>{s.session_id.substring(0, 8)}</td>
                    <td className={TD}><span className={statusBadge(s.status)}>{s.status}</span></td>
                    <td className={TD}><a href={s.issue_url} target="_blank" rel="noopener noreferrer" className={LINK}>Issue</a></td>
                    <td className={`${TD} ${MONO}`}>{s.branch || "—"}</td>
                    <td className={`${TD} tabular-nums`}>{s.acu_used.toFixed(2)}</td>
                    <td className={`${TD} text-muted`}>{new Date(s.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </Table>
            )}
          </Panel>

          {/* Issues */}
          <Panel id="issues" title="Issues" count={issues.length} onRefresh={refreshAll}>
            {issues.length === 0 ? (
              <Empty>No issues yet.</Empty>
            ) : (
              <Table head={["Title", "Type", "Dependency", "Severity", "Status", "Created"]}>
                {issues.map((i) => (
                  <tr key={i.issue_url} className="border-t border-line transition hover:bg-[var(--hover)]">
                    <td className={TD}><a href={i.issue_url} target="_blank" rel="noopener noreferrer" className={LINK}>{i.title}</a></td>
                    <td className={`${TD} text-muted`}>{i.finding_type}</td>
                    <td className={`${TD} ${MONO}`}>{i.dependency_name || "—"}</td>
                    <td className={TD}>{i.severity ? <span className={severityBadge(i.severity)}>{i.severity}</span> : "—"}</td>
                    <td className={TD}><span className={statusBadge(i.status)}>{i.status}</span></td>
                    <td className={`${TD} text-muted`}>{new Date(i.created_at).toLocaleString()}</td>
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

          <footer className="pb-2 text-center text-xs text-faint">Auto-refreshes every 30s.</footer>
        </div>
      </main>
    </div>
  );
}

function Panel({
  id,
  title,
  count,
  onRefresh,
  children,
}: {
  id: string;
  title: string;
  count?: number;
  onRefresh?: () => void;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-28">
      <div className="card overflow-hidden rounded-xl">
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-fg">{title}</h2>
            {count != null && (
              <span className="rounded-full bg-[var(--neutral-bg)] px-2 py-0.5 text-xs font-medium text-[var(--neutral-fg)] tabular-nums">
                {count}
              </span>
            )}
          </div>
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
              <th key={idx} className={`${TH} ${idx === head.length - 1 ? "text-right" : ""}`}>
                {h}
              </th>
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

function MetricCard({
  title,
  value,
  subtitle,
  icon,
}: {
  title: string;
  value: ReactNode;
  subtitle: string;
  icon: ReactNode;
}) {
  return (
    <div className="card rounded-xl p-5">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-faint">{title}</span>
        <span className="text-faint">{icon}</span>
      </div>
      <div className="text-2xl font-semibold tabular-nums text-fg">{value}</div>
      <div className="mt-1 text-xs text-faint">{subtitle}</div>
    </div>
  );
}
