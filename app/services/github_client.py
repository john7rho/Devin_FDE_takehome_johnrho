from typing import List, Optional

from github import Github
from github.Repository import Repository
from github.Issue import Issue

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
            self.logger.info("Issue created", issue_url=issue.html_url, title=title)
            return issue
        except Exception as e:
            self.logger.error("Failed to create issue", error=str(e))
            raise
