from typing import List, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.core.database import db
from app.models.schemas import SessionResponse, IssueResponse, MetricsSummary
from app.services.orchestrator import Orchestrator
from app.services.metrics import MetricsCollector
from app.utils.logger import get_logger
from app.core.config import settings
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
            if run.repo_path:
                # Scan a local checkout and create issues for findings.
                issue_urls = await orchestrator.scan_and_create_issues(run.repo_path)
                issues_found = len(issue_urls)
                logger.info("Scan completed", run_id=run_id, issues_created=issues_found)

            # scan_only must be honored regardless of repo_path. The old code only
            # checked it inside the repo_path branch, so "Scan only" with no checkout
            # fell through to dispatching a Devin session for EVERY pending issue.
            if not run.scan_only:
                session_ids = await orchestrator.process_pending_issues(run.repo_path)
                sessions_started = len(session_ids)
                logger.info("Processing completed", run_id=run_id, sessions=sessions_started)
            elif not run.repo_path:
                logger.info("Scan-only run with no repo_path: nothing to scan or process", run_id=run_id)
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
        prs = repo.get_pulls(state="open", sort="created", direction="desc")
        
        pr_list = []
        for pr in prs:
            pr_list.append({
                "number": pr.number,
                "title": pr.title,
                "html_url": pr.html_url,
                "state": pr.state,
                "user": pr.user.login,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
                "mergeable": pr.mergeable,
                "mergeable_state": pr.mergeable_state,
                "head_ref": pr.head.ref,
                "base_ref": pr.base.ref,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "commits": pr.commits,
                "reviewers": [reviewer.login for reviewer in pr.requested_reviewers],
            })
        
        return pr_list
        
    except Exception as e:
        # Degrade gracefully: GitHub may be unconfigured/unreachable, or
        # GITHUB_REPO_OWNER/NAME may not point at a real fork. Return an empty list
        # so the dashboard still renders instead of crashing on `pullRequests.map`.
        logger.error("Failed to fetch pull requests", error=str(e))
        return []


@router.post("/pull-requests/{pr_number}/reviewers")
async def add_reviewer(pr_number: int, request: dict):
    """Add a reviewer to a pull request."""
    from app.services.github_client import GitHubClient
    
    try:
        reviewer = request.get("reviewer")
        if not reviewer:
            raise HTTPException(status_code=400, detail="Reviewer is required")
        
        github_client = GitHubClient()
        github_client.add_reviewer_to_pr(pr_number, reviewer)
        return {"message": f"Added reviewer {reviewer} to PR #{pr_number}"}
    except Exception as e:
        logger.error("Failed to add reviewer", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to add reviewer")


@router.delete("/pull-requests/{pr_number}/reviewers/{reviewer}")
async def remove_reviewer(pr_number: int, reviewer: str):
    """Remove a reviewer from a pull request."""
    from app.services.github_client import GitHubClient
    
    try:
        github_client = GitHubClient()
        github_client.remove_reviewer_from_pr(pr_number, reviewer)
        return {"message": f"Removed reviewer {reviewer} from PR #{pr_number}"}
    except Exception as e:
        logger.error("Failed to remove reviewer", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to remove reviewer")


@router.get("/pull-requests/{pr_number}/reviewers")
async def get_reviewers(pr_number: int):
    """Get all reviewers for a pull request."""
    from app.services.github_client import GitHubClient
    
    try:
        github_client = GitHubClient()
        reviewers = github_client.get_pr_reviewers(pr_number)
        return {"reviewers": reviewers}
    except Exception as e:
        logger.error("Failed to fetch reviewers", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch reviewers")


@router.post("/pull-requests/{pr_number}/review")
async def request_devin_review(pr_number: int):
    """Request a Devin review for a pull request."""
    from app.services.github_client import GitHubClient
    from app.services.devin_client import DevinClient
    
    try:
        github_client = GitHubClient()
        repo = github_client.get_repo()
        pr = repo.get_pull(pr_number)
        
        # Create a Devin session for reviewing the PR
        devin_client = DevinClient()
        repo_url = pr.head.repo.clone_url or settings.github_fork_url
        if not repo_url:
            raise ValueError("Unable to determine PR repository URL")
        
        # Build review instruction
        instruction = f"""
Review this pull request for the Superset repository:

PR Title: {pr.title}
PR Number: {pr.number}
Author: {pr.user.login}
Branch: {pr.head.ref} → {pr.base.ref}
URL: {pr.html_url}

Please:
1. Review the code changes for quality, security, and best practices
2. Check for any potential bugs or issues
3. Verify the changes align with Superset's coding standards
4. Provide specific feedback on any concerns
5. Suggest improvements if needed

Focus on the actual code changes in this PR, not general repository issues.
"""
        
        # Create Devin session
        try:
            devin_session_id = await devin_client.create_session(
                instructions=instruction,
                repo_url=repo_url,
                branch=pr.head.ref,
                max_acu_limit=settings.max_acu_limit,
            )
        finally:
            await devin_client.close()
        
        # Store session in database
        db.insert_session(
            session_id=devin_session_id,
            issue_url=pr.html_url,
            repo_url=repo_url,
            branch=pr.head.ref,
            status="running",
        )
        
        # Add comment to PR indicating review started
        github_client.add_comment_to_pr(
            pr_number,
            f"Devin review started. Session ID: {devin_session_id}\n\nReview is in progress..."
        )
        
        logger.info(f"Started Devin review for PR #{pr_number}", session_id=devin_session_id)
        
        return {
            "message": f"Devin review started for PR #{pr_number}",
            "session_id": devin_session_id,
        }
        
    except Exception as e:
        logger.error("Failed to request Devin review", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to request Devin review")
