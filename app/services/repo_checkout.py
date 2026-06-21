"""Resolve what local path the dependency scanner should audit.

The browser can't hand the server a filesystem path, so the "Scan" buttons rely on
the server deciding for itself. By default that's a local checkout of the fork at the
tip of its default branch -- cloned on first use and refreshed every run -- so a scan
always reflects the fork's current version without any manual configuration.
"""
import subprocess
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger()


def resolve_scan_repo_path() -> Optional[str]:
    """Decide the path to scan.

    Priority:
      1. ``settings.scan_repo_path`` when explicitly configured (an operator override).
      2. Otherwise a managed checkout of ``settings.github_fork_url`` at the tip of its
         default branch.
    Returns ``None`` only when neither a path nor a fork URL is available.
    """
    if settings.scan_repo_path:
        return settings.scan_repo_path
    if not settings.github_fork_url:
        return None

    dest = Path(settings.fork_checkout_path)
    try:
        _clone_or_update(settings.github_fork_url, dest, settings.fork_default_branch)
        return str(dest)
    except Exception as e:
        logger.error("Could not refresh fork checkout", error=str(e), dest=str(dest))
        # A stale checkout still beats scanning nothing; only give up if none exists.
        return str(dest) if (dest / ".git").exists() else None


def _git(*args: str) -> None:
    # safe.directory=* because the checkout is bind-mounted from the host (owned by a
    # different uid than the container user); without it git refuses with "dubious
    # ownership". Shallow throughout to keep the big Superset tree cheap.
    subprocess.run(
        ["git", "-c", "safe.directory=*", *args],
        check=True, capture_output=True, text=True,
    )


def _clone_or_update(url: str, dest: Path, branch: str) -> None:
    if (dest / ".git").exists():
        logger.info("Refreshing fork checkout", dest=str(dest), branch=branch)
        _git("-C", str(dest), "fetch", "--depth", "1", "origin", branch)
        _git("-C", str(dest), "reset", "--hard", f"origin/{branch}")
        _git("-C", str(dest), "clean", "-fd")
    else:
        logger.info("Cloning fork checkout", url=url, dest=str(dest), branch=branch)
        dest.parent.mkdir(parents=True, exist_ok=True)
        _git("clone", "--depth", "1", "--branch", branch, url, str(dest))
