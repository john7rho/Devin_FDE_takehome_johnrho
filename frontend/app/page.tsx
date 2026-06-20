"use client";

import { useEffect, useState } from "react";
import { Activity, GitPullRequest, AlertTriangle, Clock, Zap, BarChart3 } from "lucide-react";

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
  user: string;
  created_at: string;
  updated_at: string;
  mergeable: boolean | null;
  mergeable_state: string;
  head_ref: string;
  base_ref: string;
  additions: number;
  deletions: number;
  commits: number;
  reviewers: string[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [pullRequests, setPullRequests] = useState<PullRequest[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchMetrics = async () => {
    try {
      const response = await fetch(`${API_BASE}/metrics`);
      const data = await response.json();
      setMetrics(data);
    } catch (error) {
      console.error("Failed to fetch metrics:", error);
    }
  };

  const fetchSessions = async () => {
    try {
      const response = await fetch(`${API_BASE}/sessions`);
      const data = await response.json();
      setSessions(data);
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    }
  };

  const fetchIssues = async () => {
    try {
      const response = await fetch(`${API_BASE}/issues`);
      const data = await response.json();
      setIssues(data);
    } catch (error) {
      console.error("Failed to fetch issues:", error);
    }
  };

  const fetchPullRequests = async () => {
    try {
      const response = await fetch(`${API_BASE}/pull-requests`);
      const data = await response.json();
      setPullRequests(data);
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
      const response = await fetch(`${API_BASE}/runs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ scan_only: scanOnly }),
      });
      const data = await response.json();
      alert(`Run started: ${data.run_id}`);
      setTimeout(refreshAll, 2000);
    } catch (error) {
      console.error("Failed to start run:", error);
      alert("Failed to start run");
    }
  };

  const addReviewer = async (prNumber: number, reviewer: string) => {
    try {
      const response = await fetch(`${API_BASE}/pull-requests/${prNumber}/reviewers`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reviewer }),
      });
      if (response.ok) {
        alert(`Added ${reviewer} as reviewer`);
        setTimeout(refreshAll, 2000);
      } else {
        alert("Failed to add reviewer");
      }
    } catch (error) {
      console.error("Failed to add reviewer:", error);
      alert("Failed to add reviewer");
    }
  };

  const removeReviewer = async (prNumber: number, reviewer: string) => {
    try {
      const response = await fetch(`${API_BASE}/pull-requests/${prNumber}/reviewers/${reviewer}`, {
        method: "DELETE",
      });
      if (response.ok) {
        alert(`Removed ${reviewer} as reviewer`);
        setTimeout(refreshAll, 2000);
      } else {
        alert("Failed to remove reviewer");
      }
    } catch (error) {
      console.error("Failed to remove reviewer:", error);
      alert("Failed to remove reviewer");
    }
  };

  const requestDevinReview = async (prNumber: number) => {
    try {
      const response = await fetch(`${API_BASE}/pull-requests/${prNumber}/review`, {
        method: "POST",
      });
      if (response.ok) {
        const data = await response.json();
        alert(`Devin review started: ${data.session_id}`);
        setTimeout(refreshAll, 2000);
      } else {
        alert("Failed to request Devin review");
      }
    } catch (error) {
      console.error("Failed to request Devin review:", error);
      alert("Failed to request Devin review");
    }
  };

  useEffect(() => {
    refreshAll();
    setLoading(false);
    const interval = setInterval(refreshAll, 30000);
    return () => clearInterval(interval);
  }, []);

  const getMergeStatusColor = (mergeable: boolean | null, mergeable_state: string) => {
    if (mergeable === true) return "bg-green-100 text-green-800";
    if (mergeable === false) return "bg-red-100 text-red-800";
    if (mergeable_state === "draft") return "bg-gray-100 text-gray-800";
    return "bg-yellow-100 text-yellow-800";
  };

  const getMergeStatusText = (mergeable: boolean | null, mergeable_state: string) => {
    if (mergeable === true) return "Mergeable";
    if (mergeable === false) return "Conflicts";
    if (mergeable_state === "draft") return "Draft";
    return "Checking";
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "finished":
        return "bg-green-100 text-green-800";
      case "running":
        return "bg-blue-100 text-blue-800";
      case "error":
        return "bg-red-100 text-red-800";
      default:
        return "bg-yellow-100 text-yellow-800";
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-xl">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 mb-8 border border-white/20">
          <h1 className="text-4xl font-bold text-white mb-2">Devin Automation Dashboard</h1>
          <p className="text-white/70">Event-driven automation using Devin API for Superset issue remediation</p>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          <MetricCard
            title="Total Sessions"
            value={metrics?.total_sessions || 0}
            subtitle="All time"
            icon={<Activity className="w-6 h-6" />}
            color="from-blue-500 to-blue-600"
          />
          <MetricCard
            title="Active Sessions"
            value={metrics?.active_sessions || 0}
            subtitle="Currently running"
            icon={<Zap className="w-6 h-6" />}
            color="from-yellow-500 to-orange-500"
          />
          <MetricCard
            title="Autonomy Rate"
            value={`${metrics?.autonomy_rate?.toFixed(1) || 0}%`}
            subtitle="% finished without human"
            icon={<BarChart3 className="w-6 h-6" />}
            color="from-green-500 to-emerald-500"
          />
          <MetricCard
            title="Outcome Rate"
            value={`${metrics?.outcome_rate?.toFixed(1) || 0}%`}
            subtitle="% successful completions"
            icon={<GitPullRequest className="w-6 h-6" />}
            color="from-purple-500 to-pink-500"
          />
          <MetricCard
            title="Avg Cycle Time"
            value={`${metrics?.avg_cycle_time?.toFixed(0) || 0}s`}
            subtitle="Seconds per session"
            icon={<Clock className="w-6 h-6" />}
            color="from-cyan-500 to-blue-500"
          />
          <MetricCard
            title="Total ACU Used"
            value={metrics?.total_acu_used?.toFixed(2) || 0}
            subtitle="Compute units consumed"
            icon={<AlertTriangle className="w-6 h-6" />}
            color="from-red-500 to-orange-500"
          />
        </div>

        {/* Sessions Table */}
        <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 mb-8 border border-white/20">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-white">Sessions</h2>
            <button
              onClick={refreshAll}
              className="px-4 py-2 bg-white/20 hover:bg-white/30 text-white rounded-lg transition"
            >
              Refresh
            </button>
          </div>
          {sessions.length === 0 ? (
            <div className="text-center text-white/50 py-8">No sessions found</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-white/70 border-b border-white/20">
                    <th className="pb-4">Session ID</th>
                    <th className="pb-4">Status</th>
                    <th className="pb-4">Issue URL</th>
                    <th className="pb-4">Branch</th>
                    <th className="pb-4">ACU Used</th>
                    <th className="pb-4">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((session) => (
                    <tr key={session.session_id} className="border-b border-white/10">
                      <td className="py-4 text-white font-mono text-sm">
                        {session.session_id.substring(0, 8)}
                      </td>
                      <td className="py-4">
                        <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(session.status)}`}>
                          {session.status}
                        </span>
                      </td>
                      <td className="py-4">
                        <a href={session.issue_url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300">
                          Issue
                        </a>
                      </td>
                      <td className="py-4 text-white font-mono text-sm">{session.branch || "-"}</td>
                      <td className="py-4 text-white">{session.acu_used.toFixed(2)}</td>
                      <td className="py-4 text-white/70 text-sm">{new Date(session.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Issues Table */}
        <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 mb-8 border border-white/20">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-white">Issues</h2>
            <button
              onClick={refreshAll}
              className="px-4 py-2 bg-white/20 hover:bg-white/30 text-white rounded-lg transition"
            >
              Refresh
            </button>
          </div>
          {issues.length === 0 ? (
            <div className="text-center text-white/50 py-8">No issues found</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-white/70 border-b border-white/20">
                    <th className="pb-4">Title</th>
                    <th className="pb-4">Type</th>
                    <th className="pb-4">Dependency</th>
                    <th className="pb-4">Severity</th>
                    <th className="pb-4">Status</th>
                    <th className="pb-4">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {issues.map((issue) => (
                    <tr key={issue.issue_url} className="border-b border-white/10">
                      <td className="py-4">
                        <a href={issue.issue_url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300">
                          {issue.title}
                        </a>
                      </td>
                      <td className="py-4 text-white">{issue.finding_type}</td>
                      <td className="py-4 text-white">{issue.dependency_name || "-"}</td>
                      <td className="py-4 text-white">{issue.severity || "-"}</td>
                      <td className="py-4">
                        <span className="px-3 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                          {issue.status}
                        </span>
                      </td>
                      <td className="py-4 text-white/70 text-sm">{new Date(issue.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pull Requests */}
        <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 mb-8 border border-white/20">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-white">Pull Requests</h2>
            <button
              onClick={refreshAll}
              className="px-4 py-2 bg-white/20 hover:bg-white/30 text-white rounded-lg transition"
            >
              Refresh
            </button>
          </div>
          {pullRequests.length === 0 ? (
            <div className="text-center text-white/50 py-8">No pull requests found</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-white/70 border-b border-white/20">
                    <th className="pb-4">PR #</th>
                    <th className="pb-4">Title</th>
                    <th className="pb-4">Branch</th>
                    <th className="pb-4">Status</th>
                    <th className="pb-4">Merge Status</th>
                    <th className="pb-4">Reviewers</th>
                    <th className="pb-4">Changes</th>
                    <th className="pb-4">Created</th>
                    <th className="pb-4">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {pullRequests.map((pr) => (
                    <tr key={pr.number} className="border-b border-white/10">
                      <td className="py-4 text-white font-mono text-sm">#{pr.number}</td>
                      <td className="py-4">
                        <a href={pr.html_url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300">
                          {pr.title}
                        </a>
                      </td>
                      <td className="py-4 text-white font-mono text-sm">{pr.head_ref} → {pr.base_ref}</td>
                      <td className="py-4">
                        <span className="px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          {pr.state}
                        </span>
                      </td>
                      <td className="py-4">
                        <span className={`px-3 py-1 rounded-full text-xs font-medium ${getMergeStatusColor(pr.mergeable, pr.mergeable_state)}`}>
                          {getMergeStatusText(pr.mergeable, pr.mergeable_state)}
                        </span>
                      </td>
                      <td className="py-4">
                        <div className="flex flex-wrap gap-1">
                          {pr.reviewers && pr.reviewers.length > 0 ? (
                            pr.reviewers.map((reviewer) => (
                              <span key={reviewer} className="px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs flex items-center gap-1">
                                {reviewer}
                                <button
                                  onClick={() => removeReviewer(pr.number, reviewer)}
                                  className="ml-1 hover:text-red-600"
                                  title="Remove reviewer"
                                >
                                  ×
                                </button>
                              </span>
                            ))
                          ) : (
                            <span className="text-white/50 text-sm">No reviewers</span>
                          )}
                        </div>
                        <div className="mt-2 flex gap-2">
                          <input
                            type="text"
                            placeholder="Add reviewer..."
                            className="px-2 py-1 bg-white/10 border border-white/20 rounded text-white text-sm w-32 placeholder-white/30"
                            onKeyPress={(e) => {
                              if (e.key === 'Enter') {
                                const target = e.target as HTMLInputElement;
                                if (target.value.trim()) {
                                  addReviewer(pr.number, target.value.trim());
                                  target.value = '';
                                }
                              }
                            }}
                          />
                        </div>
                      </td>
                      <td className="py-4 text-white text-sm">
                        <span className="text-green-400">+{pr.additions}</span>
                        <span className="text-red-400 ml-2">-{pr.deletions}</span>
                      </td>
                      <td className="py-4 text-white/70 text-sm">{new Date(pr.created_at).toLocaleString()}</td>
                      <td className="py-4">
                        <div className="flex gap-2">
                          <a
                            href={pr.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-3 py-1 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white text-sm font-medium rounded-lg transition"
                          >
                            View PR
                          </a>
                          <button
                            onClick={() => requestDevinReview(pr.number)}
                            className="px-3 py-1 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white text-sm font-medium rounded-lg transition"
                            title="Request Devin review"
                          >
                            🤖 Review
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Start New Run */}
        <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 border border-white/20">
          <h2 className="text-2xl font-bold text-white mb-6">Start New Run</h2>
          <div className="flex gap-4">
            <button
              onClick={() => startRun(false)}
              className="px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white font-medium rounded-lg transition"
            >
              Scan & Process
            </button>
            <button
              onClick={() => startRun(true)}
              className="px-6 py-3 bg-white/20 hover:bg-white/30 text-white font-medium rounded-lg transition"
            >
              Scan Only
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value, subtitle, icon, color }: any) {
  return (
    <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 hover:bg-white/15 transition">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 rounded-lg bg-gradient-to-br ${color}`}>{icon}</div>
      </div>
      <div className="text-3xl font-bold text-white mb-2">{value}</div>
      <div className="text-white/70 text-sm">{title}</div>
      <div className="text-white/50 text-xs mt-1">{subtitle}</div>
    </div>
  );
}
