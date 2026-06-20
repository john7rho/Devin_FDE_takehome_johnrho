"""Spin up a live, shareable Superset preview via a real Devin session.

Creates a Devin session that boots Apache Superset + example data in its sandbox
and exposes port 8088 publicly (Devin's `expose_port` tool -> a *.devinapps.com
URL). We then poll the session for that public URL so the dashboard can hand a
reviewer a plain browser link — no Devin account needed.

Caveats (by design, per Devin's capabilities):
  * Each preview creates a REAL Devin session and consumes ACUs.
  * The public URL is ephemeral — it lives only while the session/keep-alive is up.
  * Builds from scratch (~10-15 min). A pre-built blueprint/snapshot would make
    cold starts near-instant; left as a follow-up optimization.
"""
import json
import os
import re
from typing import Any, Dict

import httpx

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger()

# Devin's expose_port returns a https://<id>.devinapps.com URL.
_DEVINAPPS_RE = re.compile(r"https://[a-z0-9.-]+\.devinapps\.com[^\s\"'<>)]*", re.IGNORECASE)

PROMPT = """Boot Apache Superset with example data and expose it publicly so a reviewer can use it.

Steps:
1. Start Superset in a container: `docker run -d -p 8088:8088 --name superset apache/superset:4.1.1`
2. Initialize it (exec into the container): `superset db upgrade`; \
`superset fab create-admin --username admin --password admin --firstname a --lastname b --email a@b.com`; \
`superset load_examples`; `superset init`. Ensure the server serves on 0.0.0.0:8088.
3. Wait until Superset responds on port 8088 AND the example dashboards have loaded.
4. Expose port 8088 publicly, then reply with the public URL on its own line, exactly:
   `PREVIEW_URL: <the https://...devinapps.com url>`

Login is admin / admin. Keep the session alive; do not stop until the public URL is serving Superset."""

_PLACEHOLDERS = {"", "demo", "test", "test-devin-key", "x", "changeme"}


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.devin_api_url,
        headers={"Authorization": f"Bearer {settings.devin_api_key}"},
        timeout=60.0,
    )


def is_configured() -> bool:
    return settings.devin_api_key not in _PLACEHOLDERS


def create_preview_session() -> Dict[str, Any]:
    """Create the Devin session and return its id + session UI url."""
    payload: Dict[str, Any] = {"prompt": PROMPT, "idempotent": True, "title": "Superset preview"}
    # Pin a pre-built Superset blueprint snapshot for near-instant boots (per-project).
    snapshot_id = os.getenv("DEVIN_SUPERSET_SNAPSHOT_ID")
    if snapshot_id:
        payload["snapshot_id"] = snapshot_id
    with _client() as c:
        r = c.post("/v1/sessions", json=payload)
        r.raise_for_status()
        data = r.json()
    logger.info("Superset preview session created", session_id=data.get("session_id"))
    return {"session_id": data.get("session_id"), "session_url": data.get("url")}


def get_preview_url(session_id: str) -> Dict[str, Any]:
    """Poll the session and extract the public devinapps.com URL once Devin posts it."""
    with _client() as c:
        r = c.get(f"/v1/sessions/{session_id}")
        r.raise_for_status()
        data = r.json()
    match = _DEVINAPPS_RE.search(json.dumps(data))
    return {
        "session_id": session_id,
        "status": data.get("status_enum") or data.get("status"),
        "preview_url": match.group(0) if match else None,
    }
