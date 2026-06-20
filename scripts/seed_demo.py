"""Seed data/state.db with a realistic demo run for local manual testing.

Delegates to app.core.seed (the single source of truth, also used by the
optional SEED_ON_STARTUP hook). GitHub owner/repo + API keys come from .env.

Run:  DATABASE_PATH=data/state.db uv run python scripts/seed_demo.py
"""
import os
import sys

# Make `app` importable when this script is run directly from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_PATH", "data/state.db")

from app.core.seed import seed_demo_data  # noqa: E402

if __name__ == "__main__":
    # force=True so a fresh run always (re)populates; pair with `rm -f data/state.db`
    # for a clean reseed.
    print(seed_demo_data(force=True))
