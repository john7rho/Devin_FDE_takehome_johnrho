from typing import List, Optional
from github import Github
from github.Repository import Repository
from github.Issue import Issue
from github.PullRequest import PullRequest

from app.core.config import settings
from app.utils.logger import get_logger


class GitHubClient:
    """Client for interacting with GitHub API."""
    
    def __init__(self):
        self.token = settings.github_token
        self.repo_owner = settings.github_repo_owner
        self.repo_name = settings.github_repo_name
        self.github = Github(self.token)
        self.logger = get_logger()
    
    def get_repo(self) -> Repository:
        """Get the repository object."""
        try:
            repo = self.github.get_repo(f"{self.repo_owner}/{self.repo_name}")
            self.logger.info("Repository accessed", repo=f"{self.repo_owner}/{self.repo_name}")
            return repo
        except Exception as e:
            self.logger.error("Failed to access repository", error=str(e))
            raise
    
    def create_issue(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None
    ) -> Issue:
        """Create a GitHub issue on the fork."""
        try:
            repo = self.get_repo()
            issue = repo.create_issue(
                title=title,
                body=body,
                labels=labels or []
            )
            
            self.logger.info(
                "Issue created",
                issue_url=issue.html_url,
                title=title
            )
            return issue
            
        except Exception as e:
            self.logger.error("Failed to create issue", error=str(e))
            raise
    
    def get_issue(self, issue_number: int) -> Issue:
        """Get an issue by number."""
        try:
            repo = self.get_repo()
            issue = repo.get_issue(issue_number)
            return issue
        except Exception as e:
            self.logger.error("Failed to get issue", issue_number=issue_number, error=str(e))
            raise
    
    def create_branch(
        self,
        branch_name: str,
        base_branch: str = "main"
    ) -> str:
        """Create a new branch from the base branch."""
        try:
            repo = self.get_repo()
            
            # Get the base branch
            base = repo.get_branch(base_branch)
            
            # Create the new branch
            repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=base.commit.sha
            )
            
            self.logger.info(
                "Branch created",
                branch=branch_name,
                base_branch=base_branch
            )
            return branch_name
            
        except Exception as e:
            self.logger.error("Failed to create branch", branch=branch_name, error=str(e))
            raise
    
    def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        labels: Optional[List[str]] = None
    ) -> PullRequest:
        """Create a pull request."""
        try:
            repo = self.get_repo()
            pr = repo.create_pull(
                title=title,
                body=body,
                head=head,
                base=base
            )
            
            if labels:
                pr.add_to_labels(*labels)
            
            self.logger.info(
                "Pull request created",
                pr_url=pr.html_url,
                head=head,
                base=base
            )
            return pr
            
        except Exception as e:
            self.logger.error("Failed to create pull request", error=str(e))
            raise
    
    def add_comment_to_issue(self, issue_number: int, comment: str) -> None:
        """Add a comment to an issue."""
        try:
            issue = self.get_issue(issue_number)
            issue.create_comment(comment)
            self.logger.info("Comment added to issue", issue_number=issue_number)
        except Exception as e:
            self.logger.error("Failed to add comment", issue_number=issue_number, error=str(e))
            raise
    
    def close_issue(self, issue_number: int) -> None:
        """Close an issue."""
        try:
            issue = self.get_issue(issue_number)
            issue.edit(state="closed")
            self.logger.info("Issue closed", issue_number=issue_number)
        except Exception as e:
            self.logger.error("Failed to close issue", issue_number=issue_number, error=str(e))
            raise
    
    def get_open_issues(self, label: Optional[str] = None) -> List[Issue]:
        """Get all open issues, optionally filtered by label."""
        try:
            repo = self.get_repo()
            if label:
                issues = repo.get_issues(labels=[label], state="open")
            else:
                issues = repo.get_issues(state="open")
            
            return list(issues)
        except Exception as e:
            self.logger.error("Failed to get open issues", error=str(e))
            raise

    def add_reviewer_to_pr(self, pr_number: int, reviewer: str) -> None:
        """Add a reviewer to a pull request."""
        try:
            repo = self.get_repo()
            pr = repo.get_pull(pr_number)
            pr.create_review_request(reviewers=[reviewer])
            self.logger.info(f"Added reviewer {reviewer} to PR #{pr_number}")
        except Exception as e:
            self.logger.error("Failed to add reviewer", pr_number=pr_number, reviewer=reviewer, error=str(e))
            raise

    def remove_reviewer_from_pr(self, pr_number: int, reviewer: str) -> None:
        """Remove a reviewer from a pull request."""
        try:
            repo = self.get_repo()
            pr = repo.get_pull(pr_number)
            pr.delete_review_request(reviewers=[reviewer])
            self.logger.info(f"Removed reviewer {reviewer} from PR #{pr_number}")
        except Exception as e:
            self.logger.error("Failed to remove reviewer", pr_number=pr_number, reviewer=reviewer, error=str(e))
            raise

    def get_pr_reviewers(self, pr_number: int) -> List[str]:
        """Get all reviewers for a pull request."""
        try:
            repo = self.get_repo()
            pr = repo.get_pull(pr_number)
            return [reviewer.login for reviewer in pr.requested_reviewers]
        except Exception as e:
            self.logger.error("Failed to fetch reviewers", pr_number=pr_number, error=str(e))
            raise

    def add_comment_to_pr(self, pr_number: int, comment: str) -> None:
        """Add a comment to a pull request."""
        try:
            repo = self.get_repo()
            pr = repo.get_pull(pr_number)
            pr.create_issue_comment(comment)
            self.logger.info("Comment added to PR", pr_number=pr_number)
        except Exception as e:
            self.logger.error("Failed to add comment to PR", pr_number=pr_number, error=str(e))
            raise
