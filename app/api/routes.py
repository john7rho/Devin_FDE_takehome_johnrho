from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.core.database import db
from app.models.schemas import SessionResponse, IssueResponse, MetricsSummary
from app.services.orchestrator import Orchestrator
from app.services.metrics import MetricsCollector
from app.utils.logger import get_logger
from app.core.config import settings

router = APIRouter()
logger = get_logger()


class RunCreate(BaseModel):
    repo_path: Optional[str] = None
    scan_only: bool = False


class RunResponse(BaseModel):
    run_id: str
    status: str
    message: str


@router.post("/runs", response_model=RunResponse)
async def create_run(run: RunCreate, background_tasks: BackgroundTasks):
    """Start a new run: scan dependencies and process issues."""
    import uuid
    
    run_id = str(uuid.uuid4())
    logger.info("Creating run", run_id=run_id, scan_only=run.scan_only)
    
    orchestrator = Orchestrator()
    
    async def execute_run():
        try:
            if run.repo_path:
                # Scan and create issues
                issue_urls = await orchestrator.scan_and_create_issues(run.repo_path)
                logger.info("Scan completed", run_id=run_id, issues_created=len(issue_urls))
                
                if not run.scan_only:
                    # Process pending issues
                    session_ids = await orchestrator.process_pending_issues(run.repo_path)
                    logger.info("Processing completed", run_id=run_id, sessions=len(session_ids))
            else:
                # Just process pending issues
                session_ids = await orchestrator.process_pending_issues()
                logger.info("Processing completed", run_id=run_id, sessions=len(session_ids))
        except Exception as e:
            logger.error("Run failed", run_id=run_id, error=str(e))
    
    background_tasks.add_task(execute_run)
    
    return RunResponse(
        run_id=run_id,
        status="started",
        message="Run started in background"
    )


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: str):
    """Get the status of a run."""
    # For now, return a simple response
    # In a real implementation, we'd track runs in the database
    return RunResponse(
        run_id=run_id,
        status="unknown",
        message="Run tracking not fully implemented"
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
    """Get all issues."""
    issues = db.get_pending_issues()
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
