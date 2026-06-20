"""Idempotent demo seeding — the single source of truth for demo data.

Used by both the CLI script (scripts/seed_demo.py) and the optional
SEED_ON_STARTUP hook in app.api.main. Populates a small, realistic run
(issues + sessions + metrics) so the dashboard has content.

Safe to call repeatedly: by default it no-ops when sessions already exist.
On ephemeral hosts the DB resets on cold start, so the startup hook
re-populates automatically. GitHub owner/repo come from settings (.env).
"""
import uuid

from app.core.config import settings
from app.core.database import db
from app.models.schemas import SessionStatus, IssueStatus
from app.services.metrics import MetricsCollector

# (dependency, CVE, severity, outcome, acu, human_msgs)
PROCESSED = [
    ("flask",           "CVE-2023-30861",      "HIGH",     "finished",         3.4, 0),
    ("cryptography",    "CVE-2023-49083",      "CRITICAL", "finished",         6.1, 1),
    ("sqlparse",        "CVE-2023-30608",      "MEDIUM",   "waiting_for_user", 2.2, 2),
    ("@babel/traverse", "GHSA-67hx-6x53-jw92", "CRITICAL", "error",            8.7, 0),
    ("postcss",         "GHSA-7fh5-64p2-3v2j", "MEDIUM",   "finished",         4.0, 0),
]
# extra issues left in the queue (no session yet) so the Issues view isn't empty
PENDING = [
    ("lodash",  "CVE-2021-23337", "HIGH"),
    ("urllib3", "CVE-2023-43804", "MEDIUM"),
]


def seed_demo_data(force: bool = False) -> dict:
    """Insert the demo dataset. No-ops if sessions already exist (unless force)."""
    if not force and db.get_all_sessions():
        return {"status": "skipped", "reason": "sessions already present"}

    owner_repo = f"{settings.github_repo_owner}/{settings.github_repo_name}"
    repo_url = f"https://github.com/{owner_repo}.git"

    for i, (dep, cve, sev, outcome, acu, hmsgs) in enumerate(PROCESSED):
        n = 100 + i
        issue_url = f"https://github.com/{owner_repo}/issues/{n}"
        db.insert_issue(issue_url=issue_url, title=f"Dependency vulnerability: {dep}",
                        finding_type="dependency", dependency_name=dep,
                        vulnerability_id=cve, severity=sev)
        sid = str(uuid.uuid4())
        branch = f"fix/dependency/{sid[:8]}"
        db.insert_session(sid, issue_url, repo_url, branch=branch, status="created")
        if outcome == "finished":
            pr = f"https://github.com/{owner_repo}/pull/{1000 + i}"
            db.update_session(sid, status=SessionStatus.FINISHED.value, status_detail="finished",
                              acu_used=acu, human_msgs=hmsgs, pr_url=pr)
            db.update_issue(issue_url, session_id=sid, status=IssueStatus.COMPLETED.value)
        elif outcome == "waiting_for_user":
            db.update_session(sid, status=SessionStatus.WAITING_FOR_USER.value,
                              status_detail="needs_human", acu_used=acu, human_msgs=hmsgs)
            db.update_issue(issue_url, session_id=sid, status=IssueStatus.IN_PROGRESS.value)
        else:
            db.update_session(sid, status=SessionStatus.ERROR.value, status_detail="error",
                              acu_used=acu, human_msgs=hmsgs,
                              error_message="Build failed after version bump (peer-dep conflict).")
            db.update_issue(issue_url, session_id=sid, status=IssueStatus.FAILED.value)

    for j, (dep, cve, sev) in enumerate(PENDING):
        n = 200 + j
        db.insert_issue(issue_url=f"https://github.com/{owner_repo}/issues/{n}",
                        title=f"Dependency vulnerability: {dep}", finding_type="dependency",
                        dependency_name=dep, vulnerability_id=cve, severity=sev)

    summary = MetricsCollector().calculate_metrics()
    _seed_metric_history(summary)
    return {"status": "seeded", "processed": len(PROCESSED), "pending": len(PENDING),
            "autonomy_rate": summary.autonomy_rate, "total_acu": summary.total_acu_used}


def _seed_metric_history(summary) -> None:
    """Insert a synthetic per-metric time series so the dashboard charts have data
    to plot (ramps up to the current value with a small deterministic wiggle)."""
    from datetime import datetime, timedelta

    series = {
        "total_sessions": summary.total_sessions,
        "active_sessions": max(summary.active_sessions, 1),
        "autonomy_rate": summary.autonomy_rate,
        "outcome_rate": summary.outcome_rate,
        "avg_cycle_time": summary.avg_cycle_time or 45.0,
        "total_acu_used": summary.total_acu_used,
    }
    now = datetime.now()
    points = 12
    with db.get_connection() as conn:
        cur = conn.cursor()
        for name, target in series.items():
            for i in range(points):
                ts = (now - timedelta(hours=points - 1 - i)).isoformat()
                frac = 0.5 + 0.5 * (i / (points - 1))         # ramp toward current
                wig = 1 + (((i * 37) % 11) - 5) / 100.0        # deterministic ±5%
                val = round(float(target) * frac * wig, 2)
                cur.execute(
                    "INSERT INTO metrics (metric_name, metric_value, timestamp) VALUES (?, ?, ?)",
                    (name, val, ts),
                )
        conn.commit()
