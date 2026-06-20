import asyncio
from typing import List, Optional
import uuid

import structlog

from app.core.config import settings
from app.core.database import db
from app.models.schemas import SessionStatus, IssueStatus, DevinStructuredOutput
from app.services.devin_client import DevinClient
from app.services.github_client import GitHubClient
from app.services.scanner import DependencyScanner
from app.utils.logger import get_logger, SessionLogger


class Orchestrator:
    """Orchestrates Devin sessions for issue remediation with concurrency control."""
    
    def __init__(self):
        self.max_concurrent = settings.max_concurrent_sessions
        self.active_sessions: set[str] = set()
        self.github_client = GitHubClient()
        self.logger = get_logger()
    
    async def process_issue(self, issue_url: str, repo_url: str) -> str:
        """Process a single issue by creating a Devin session."""
        session_id = str(uuid.uuid4())
        session_logger = SessionLogger(session_id)
        devin_client: Optional[DevinClient] = None

        # Tag EVERY log line emitted within this session's async context with
        # session_id — including the Devin client, which uses a generic logger.
        # Task-local contextvars keep concurrent sessions from cross-tagging.
        structlog.contextvars.bind_contextvars(session_id=session_id)

        try:
            # Generate branch name
            branch_name = f"{settings.branch_prefix}/{session_id[:8]}"
            self.active_sessions.add(session_id)
            
            # Insert session into database
            db.insert_session(
                session_id=session_id,
                issue_url=issue_url,
                repo_url=repo_url,
                branch=branch_name,
                status="created"
            )
            
            session_logger.info("Processing issue", issue_url=issue_url, branch=branch_name)
            
            # Create Devin session
            devin_client = DevinClient()
            prompt = self._build_instructions(issue_url, repo_url, branch_name)

            devin_session_id, devin_url = await devin_client.create_session(
                prompt=prompt,
                max_acu_limit=settings.max_acu_limit,
                idempotent=True,
            )

            # Update session status (persist the Devin session id so the UI can deep-link to it)
            db.update_session(session_id, status="running", status_detail="session_created", devin_session_id=devin_session_id)
            session_logger.info("Devin session created", devin_session_id=devin_session_id, devin_url=devin_url)

            # Wait for completion (terminal or blocked-on-human)
            result = await devin_client.wait_for_completion(devin_session_id)

            # Parse status from the v1 status_enum. ACUs are not on the v1 session
            # response; human-message count is derived from the messages list.
            status = self._map_status(str(result.get("status_enum") or result.get("status") or ""))
            db.update_session(
                session_id,
                status=status.value,
                status_detail=str(result.get("status") or ""),
                human_msgs=DevinClient.count_human_messages(result),
                acu_used=DevinClient.extract_acu(result),
            )

            session_logger.info("Session completed", status=status.value)

            # Structured output is a field on the session (we passed a schema at creation).
            structured_output: Optional[DevinStructuredOutput] = DevinClient.parse_structured_output(result)
            
            if structured_output:
                db.update_session(
                    session_id,
                    structured_output=structured_output.model_dump_json(),
                    pr_url=structured_output.pr_url
                )
                
                # Only "completed" if a PR was actually opened and no human action is
                # still required; otherwise the issue is blocked on a human (push access,
                # review, etc.). The session status carries the finer-grained signal.
                if structured_output.pr_url and not structured_output.needs_human:
                    issue_status = IssueStatus.COMPLETED
                else:
                    issue_status = IssueStatus.IN_PROGRESS
                db.update_issue(issue_url, session_id=session_id, status=issue_status.value)
                
                session_logger.info(
                    "Structured output received",
                    pr_url=structured_output.pr_url,
                    files_changed=len(structured_output.files_changed)
                )
            else:
                db.update_issue(issue_url, session_id=session_id, status=IssueStatus.FAILED.value)
                session_logger.warning("No structured output received")
            
            return session_id
            
        except Exception as e:
            session_logger.error("Error processing issue", error=str(e))
            db.update_session(session_id, status="error", error_message=str(e))
            db.update_issue(issue_url, session_id=session_id, status=IssueStatus.FAILED.value)
            raise
        finally:
            if devin_client:
                await devin_client.close()
            self.active_sessions.discard(session_id)
            structlog.contextvars.unbind_contextvars("session_id")
    
    async def process_pending_issues(self, repo_path: Optional[str] = None) -> List[str]:
        """Process all pending issues with concurrency control."""
        self.logger.info("Starting to process pending issues")
        
        # Get pending issues from database
        pending_issues = db.get_pending_issues()
        
        if not pending_issues:
            self.logger.info("No pending issues to process")
            return []
        
        self.logger.info(f"Found {len(pending_issues)} pending issues")
        
        repo_url = settings.github_fork_url or repo_path
        if not repo_url:
            raise ValueError("A GitHub fork URL is required to process issues")

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_with_limit(issue: dict) -> str:
            async with semaphore:
                return await self.process_issue(issue["issue_url"], repo_url)

        tasks = [asyncio.create_task(process_with_limit(issue)) for issue in pending_issues]
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        session_ids: List[str] = []
        for result in results:
            if isinstance(result, BaseException):
                self.logger.error("Task failed", error=str(result))
            else:
                session_ids.append(result)
        
        self.logger.info(f"Completed processing {len(session_ids)} issues")
        return session_ids
    
    async def scan_and_create_issues(self, repo_path: str) -> List[str]:
        """Scan dependencies and create GitHub issues for findings."""
        self.logger.info("Starting dependency scan", repo_path=repo_path)
        
        scanner = DependencyScanner(repo_path)
        findings = scanner.scan_all()
        
        if not findings:
            self.logger.info("No vulnerabilities found")
            return []
        
        self.logger.info(f"Found {len(findings)} vulnerabilities")
        
        issue_urls = []
        for finding in findings:
            # Check if issue already exists
            existing = db.get_pending_issues()
            title = f"Dependency vulnerability: {finding.dependency_name}"
            
            # Simple deduplication by title
            if any(issue["title"] == title for issue in existing):
                self.logger.info("Issue already exists", title=title)
                continue
            
            # Create GitHub issue
            issue_body = self._build_issue_body(finding)
            issue = self.github_client.create_issue(
                title=title,
                body=issue_body,
                labels=["dependency", "security", "automated"]
            )
            
            # Store in database
            db.insert_issue(
                issue_url=issue.html_url,
                title=title,
                finding_type="dependency",
                dependency_name=finding.dependency_name,
                vulnerability_id=finding.vulnerability_id,
                severity=finding.severity
            )
            
            issue_urls.append(issue.html_url)
            self.logger.info("Issue created", issue_url=issue.html_url)
        
        return issue_urls
    
    def _build_instructions(
        self,
        issue_url: str,
        repo_url: str,
        branch_name: str
    ) -> str:
        """Build instructions for Devin session."""
        return f"""
You are tasked with fixing the issue described at: {issue_url}

Repository: {repo_url}
Branch: {branch_name}

Please:
1. Research the issue thoroughly
2. Implement the fix on the specified branch
3. Add appropriate tests to verify the fix
4. Run the tests and ensure they pass
5. Create a pull request with a clear description

After completion, return a JSON response with the following structure:
{{
  "issue_url": "{issue_url}",
  "summary": "Brief summary of work performed",
  "branch": "{branch_name}",
  "pr_url": "URL of created PR",
  "files_changed": ["list of modified files"],
  "tests_run": ["list of tests executed"],
  "test_result": "pass/fail/skip",
  "evidence": "Evidence of the fix (logs, diffs)",
  "needs_human": false
}}
"""
    
    def _build_issue_body(self, finding) -> str:
        """Build GitHub issue body from scan result."""
        body = f"""## Dependency Vulnerability

**Dependency:** {finding.dependency_name}
**Vulnerability ID:** {finding.vulnerability_id or 'N/A'}
**Severity:** {finding.severity or 'UNKNOWN'}

### Description
{finding.description}

### Affected Versions
{', '.join(finding.affected_versions)}

### Fixed Version
{finding.fixed_version or 'Not available'}

### References
{chr(10).join(f'- {ref}' for ref in finding.references)}

### Automated Fix
This issue will be automatically processed by the Devin automation system.
"""
        return body
    
    def _map_status(self, devin_status: str) -> SessionStatus:
        """Map a Devin v1 status_enum value to our SessionStatus enum."""
        status_map = {
            "finished": SessionStatus.FINISHED,
            "blocked": SessionStatus.WAITING_FOR_USER,
            "working": SessionStatus.RUNNING,
            "expired": SessionStatus.ERROR,
        }
        return status_map.get(devin_status, SessionStatus.ERROR)
