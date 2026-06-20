"""Client for the real Devin v1 API (https://docs.devin.ai/api-reference).

Notable v1 facts this client respects:
  * Create takes `prompt` (not instructions/repo_url) and returns {session_id, url};
    the `url` (https://app.devin.ai/sessions/<id>) is only returned at creation.
  * Structured output comes back as the `structured_output` field on the session
    GET — only if you pass `structured_output_schema` at creation. There is no
    `/output` endpoint.
  * Status lives in `status_enum` (working|blocked|finished|expired|...).
  * Terminate is `DELETE /v1/sessions/{id}`; resume is `POST /v1/sessions/{id}/message`.
"""
import json
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.config import settings
from app.models.schemas import DevinStructuredOutput
from app.utils.logger import get_logger

# Devin v1 session `status_enum` values.
TERMINAL_STATUSES = {"finished", "expired"}
WAITING_STATUSES = {"blocked"}  # blocked = waiting on a human

# JSON schema Devin is asked to fill in as `structured_output`.
STRUCTURED_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "issue_url": {"type": "string"},
        "summary": {"type": "string"},
        "branch": {"type": "string"},
        "pr_url": {"type": "string"},
        "files_changed": {"type": "array", "items": {"type": "string"}},
        "tests_run": {"type": "array", "items": {"type": "string"}},
        "test_result": {"type": "string"},
        "evidence": {"type": "string"},
        "needs_human": {"type": "boolean"},
    },
    "required": ["issue_url", "summary", "branch", "test_result", "evidence"],
}


class DevinClient:
    """Async client for the Devin v1 sessions API."""

    def __init__(self) -> None:
        self.api_key = settings.devin_api_key
        self.base_url = settings.devin_api_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=300.0,
        )
        self.logger = get_logger()

    async def create_session(
        self,
        prompt: str,
        *,
        max_acu_limit: Optional[int] = None,
        snapshot_id: Optional[str] = None,
        idempotent: bool = False,
    ) -> Tuple[str, Optional[str]]:
        """Create a session. Returns (session_id, session_url)."""
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "structured_output_schema": STRUCTURED_OUTPUT_SCHEMA,
        }
        if max_acu_limit:
            payload["max_acu_limit"] = max_acu_limit
        if snapshot_id:
            payload["snapshot_id"] = snapshot_id
        if idempotent:
            payload["idempotent"] = True
        try:
            response = await self.client.post("/v1/sessions", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as e:
            self.logger.error("Failed to create Devin session", error=str(e))
            raise
        data = response.json()
        session_id = data.get("session_id")
        if not isinstance(session_id, str):
            raise ValueError("Devin API response did not include a session_id")
        self.logger.info("Devin session created", session_id=session_id, url=data.get("url"))
        return session_id, data.get("url")

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """GET a session (status, status_enum, messages, structured_output, ...)."""
        response = await self.client.get(f"/v1/sessions/{session_id}")
        response.raise_for_status()
        return response.json()

    async def wait_for_completion(
        self, session_id: str, poll_interval: int = 30, timeout: int = 3600
    ) -> Dict[str, Any]:
        """Poll until the session is terminal or blocked (waiting on a human)."""
        import asyncio

        elapsed = 0
        while elapsed < timeout:
            session = await self.get_session(session_id)
            status = str(session.get("status_enum") or session.get("status") or "")
            if status in TERMINAL_STATUSES or status in WAITING_STATUSES:
                self.logger.info("Session reached terminal/blocked state", session_id=session_id, status=status)
                return session
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f"Session {session_id} did not complete within {timeout} seconds")

    @staticmethod
    def parse_structured_output(session: Dict[str, Any]) -> Optional[DevinStructuredOutput]:
        """Parse the `structured_output` field off a session response."""
        raw: Any = session.get("structured_output")
        if not raw:
            return None
        try:
            if isinstance(raw, str):
                raw = json.loads(raw)
            return DevinStructuredOutput(**raw)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger_warn = get_logger()
            logger_warn.warning("Failed to parse structured_output", error=str(e))
            return None

    @staticmethod
    def extract_acu(session: Dict[str, Any]) -> float:
        """Pull ACUs consumed off a v1 session response. The field has moved
        around across API versions, so check the known names (top-level and
        under a `usage` object) and fall back to 0.0."""
        candidates = ("acu_used", "acus_used", "acu", "acus", "compute_units_used", "acu_consumed")
        for key in candidates:
            v = session.get(key)
            if isinstance(v, (int, float)):
                return float(v)
        usage = session.get("usage")
        if isinstance(usage, dict):
            for key in candidates:
                v = usage.get(key)
                if isinstance(v, (int, float)):
                    return float(v)
        return 0.0

    @staticmethod
    def count_human_messages(session: Dict[str, Any]) -> int:
        """Count human-authored messages (for the autonomy metric)."""
        messages = session.get("messages") or []
        if not isinstance(messages, list):
            return 0
        return sum(
            1
            for m in messages
            if isinstance(m, dict) and (m.get("origin") == "user" or m.get("type") == "user_message")
        )

    async def send_message(self, session_id: str, message: str) -> bool:
        """Send a follow-up message to a session (resume / steer)."""
        try:
            response = await self.client.post(f"/v1/sessions/{session_id}/message", json={"message": message})
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            self.logger.error("Failed to send message", session_id=session_id, error=str(e))
            return False

    async def terminate_session(self, session_id: str) -> bool:
        """Terminate a session (DELETE /v1/sessions/{id})."""
        try:
            response = await self.client.delete(f"/v1/sessions/{session_id}")
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            self.logger.error("Failed to terminate session", session_id=session_id, error=str(e))
            return False

    async def close(self) -> None:
        await self.client.aclose()
