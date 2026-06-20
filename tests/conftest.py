"""Pytest fixtures and test-environment setup.

Required API-key settings have no defaults in ``app.core.config.Settings``, so we
must populate the environment BEFORE any ``app.*`` import triggers ``Settings()``.
We also point the module-level DB singleton at a throwaway temp file so importing
the app never touches the real ``data/state.db``.
"""
import os
import tempfile

os.environ.setdefault("DEVIN_API_KEY", "test-devin-key")
os.environ.setdefault("GITHUB_TOKEN", "test-gh-token")
os.environ.setdefault("GITHUB_REPO_OWNER", "test-owner")
os.environ.setdefault("GITHUB_REPO_NAME", "superset")
os.environ.setdefault("GITHUB_FORK_URL", "https://github.com/test-owner/superset")
os.environ.setdefault(
    "DATABASE_PATH", os.path.join(tempfile.gettempdir(), "devin_test_singleton.db")
)

import pytest  # noqa: E402
from app.core.database import Database  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """A fresh, isolated SQLite DB per test, patched into every module that
    imported the global ``db`` singleton (``from app.core.database import db``)."""
    test_db = Database(db_path=str(tmp_path / "state.db"))
    for target in (
        "app.core.database.db",
        "app.services.metrics.db",
        "app.services.orchestrator.db",
        "app.api.routes.db",
    ):
        monkeypatch.setattr(target, test_db)
    return test_db
