import asyncio
from typing import List, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.core.database import db
from app.models.schemas import SessionResponse, IssueResponse, MetricsSummary
from app.services.orchestrator import Orchestrator
from app.services.metrics import MetricsCollector
from app.utils.logger import get_logger
from app.services.repo_checkout import resolve_scan_repo_path
from app.services import superset_preview

router = APIRouter()
logger = get_logger()


@router.post("/superset-preview")
async def start_superset_preview():
    """Create a Devin session that boots Superset + example data and exposes it
    publicly (Devin expose_port -> *.devinapps.com). Returns the session id +
    Devin session URL; poll GET /superset-preview/{id} for the public preview URL.
    NOTE: starts a REAL Devin session and consumes ACUs."""
    if not superset_preview.is_configured():
        raise HTTPException(status_code=503, detail="DEVIN_API_KEY not configured")
    try:
        return superset_preview.create_preview_session()
    except Exception as e:
        logger.error("superset-preview create failed", error=str(e))
        raise HTTPException(status_code=502, detail="Failed to create Devin session")


@router.get("/superset-preview/{session_id}")
async def poll_superset_preview(session_id: str):
    """Poll the Devin session for the public Superset URL (devinapps.com)."""
    try:
        return superset_preview.get_preview_url(session_id)
    except Exception as e:
        logger.error("superset-preview poll failed", error=str(e))
        raise HTTPException(status_code=502, detail="Failed to poll Devin session")


class RunCreate(BaseModel):
    repo_path: Optional[str] = None
    scan_only: bool = False


class RunResponse(BaseModel):
    run_id: str
    status: str
    message: str
    scan_only: Optional[bool] = None
    issues_found: Optional[int] = None
    sessions_started: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    error_message: Optional[str] = None


@router.post("/runs", response_model=RunResponse)
async def create_run(run: RunCreate, background_tasks: BackgroundTasks):
    """Start a new run: scan dependencies and process issues."""
    import uuid
    
    run_id = str(uuid.uuid4())
    logger.info("Creating run", run_id=run_id, scan_only=run.scan_only)
    db.insert_run(run_id, status="running", scan_only=run.scan_only)

    orchestrator = Orchestrator()

    async def execute_run():
        # Tag every line in this run with run_id (covers the pre-session scan +
        # GitHub logs that have no session_id yet).
        structlog.contextvars.bind_contextvars(run_id=run_id)
        issues_found = 0
        sessions_started = 0
        try:
            # Resolve the scan target server-side (the browser can't supply a path).
            # Defaults to a fresh checkout of the fork; done here, not in the request
            # handler, so any clone/fetch runs in the background task rather than
            # blocking the POST. to_thread keeps the blocking git calls off the loop.
            repo_path = run.repo_path or await asyncio.to_thread(resolve_scan_repo_path)
            if repo_path:
                # Scan the checkout and create issues for findings.
                issue_urls = await orchestrator.scan_and_create_issues(repo_path)
                issues_found = len(issue_urls)
                logger.info("Scan completed", run_id=run_id, issues_created=issues_found, repo_path=repo_path)
            else:
                logger.info("No scan target available (set scan_repo_path or github_fork_url); skipping scan", run_id=run_id)

            # scan_only must be honored regardless of repo_path. The old code only
            # checked it inside the repo_path branch, so "Scan only" with no checkout
            # fell through to dispatching a Devin session for EVERY pending issue.
            if not run.scan_only:
                session_ids = await orchestrator.process_pending_issues(repo_path)
                sessions_started = len(session_ids)
                logger.info("Processing completed", run_id=run_id, sessions=sessions_started)
            db.update_run(run_id, status="completed", issues_found=issues_found, sessions_started=sessions_started)
        except Exception as e:
            logger.error("Run failed", run_id=run_id, error=str(e))
            db.update_run(run_id, status="error", error_message=str(e),
                          issues_found=issues_found, sessions_started=sessions_started)
        finally:
            structlog.contextvars.unbind_contextvars("run_id")

    background_tasks.add_task(execute_run)

    return RunResponse(
        run_id=run_id,
        status="started",
        message="Run started in background",
        scan_only=run.scan_only,
    )


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: str):
    """Get the status of a run from the runs state table."""
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunResponse(
        run_id=run["run_id"],
        status=run["status"],
        message=f"Run {run['status']}",
        scan_only=bool(run.get("scan_only")),
        issues_found=run.get("issues_found"),
        sessions_started=run.get("sessions_started"),
        created_at=str(run.get("created_at")) if run.get("created_at") else None,
        updated_at=str(run.get("updated_at")) if run.get("updated_at") else None,
        error_message=run.get("error_message"),
    )


@router.get("/sessions", response_model=List[SessionResponse])
async def get_sessions(status: Optional[str] = None):
    """Get all sessions, optionally filtered by status."""
    sessions = db.get_all_sessions(status=status)
    return [SessionResponse(**s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get a specific session by ID."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(**session)


@router.get("/issues", response_model=List[IssueResponse])
async def get_issues():
    """Get all issues (any status) so processed outcomes stay visible."""
    issues = db.get_all_issues()
    return [IssueResponse(**i) for i in issues]


@router.get("/metrics", response_model=MetricsSummary)
async def get_metrics():
    """Get current metrics summary."""
    collector = MetricsCollector()
    return collector.calculate_metrics()


@router.get("/metrics/history/{metric_name}")
async def get_metrics_history(metric_name: str, hours: int = 24):
    """Get historical metrics for a specific metric."""
    collector = MetricsCollector()
    history = collector.get_metrics_history(metric_name, hours)
    return history


@router.get("/consumption")
async def get_consumption():
    """Aggregate ACU consumption from the Devin consumption API, plus whether the
    account is entitled to it (per-session ACU is not exposed by the Devin API)."""
    from app.services import consumption
    return consumption.get_status()


@router.get("/logs/{session_id}")
async def get_session_logs(session_id: str):
    """Get logs for a specific session."""
    collector = MetricsCollector()
    logs = collector.get_session_logs(session_id)
    return logs


@router.get("/pull-requests")
async def get_pull_requests():
    """Get all pull requests from the fork."""
    from app.services.github_client import GitHubClient
    
    try:
        github_client = GitHubClient()
        repo = github_client.get_repo()

        def serialize(pr, merged: bool):
            return {
                "number": pr.number,
                "title": pr.title,
                "html_url": pr.html_url,
                "state": "merged" if merged else pr.state,
                "merged": merged,
                "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                "user": pr.user.login,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
                "mergeable": pr.mergeable,
                "mergeable_state": "merged" if merged else pr.mergeable_state,
                "head_ref": pr.head.ref,
                "base_ref": pr.base.ref,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "commits": pr.commits,
                "reviewers": [reviewer.login for reviewer in pr.requested_reviewers],
            }

        # Open PRs are in-flight work; recently merged PRs are delivered work. The
        # dashboard needs both so it can show a delivery rate, not just the backlog.
        # merged_at is in the list payload, so the filter is cheap; only the few
        # actually-merged PRs get fully serialized.
        open_prs = [serialize(pr, False) for pr in repo.get_pulls(state="open", sort="created", direction="desc")]
        merged_prs = [
            serialize(pr, True)
            for pr in repo.get_pulls(state="closed", sort="updated", direction="desc")[:40]
            if pr.merged_at is not None
        ]
        return open_prs + merged_prs

    except Exception as e:
        # Degrade gracefully: GitHub may be unconfigured/unreachable, or
        # GITHUB_REPO_OWNER/NAME may not point at a real fork. Return an empty list
        # so the dashboard still renders instead of crashing on `pullRequests.map`.
        logger.error("Failed to fetch pull requests", error=str(e))
        return []

