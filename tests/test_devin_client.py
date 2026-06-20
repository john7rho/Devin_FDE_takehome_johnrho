"""Unit tests for the Devin API client, with HTTP mocked via httpx.MockTransport.

These cover the polling logic that now keys off the SessionStatus enum helpers
(terminal_values / waiting_values).
"""
import httpx

from app.services.devin_client import DevinClient
from app.models.schemas import SessionStatus


def _client_with(handler):
    dc = DevinClient()
    dc.client = httpx.AsyncClient(base_url=dc.base_url, transport=httpx.MockTransport(handler))
    return dc


async def test_create_session_returns_session_id():
    def handler(request):
        return httpx.Response(200, json={"session_id": "devin-123"})

    dc = _client_with(handler)
    sid = await dc.create_session(instructions="fix the bug", repo_url="http://repo")
    assert sid == "devin-123"
    await dc.close()


async def test_wait_for_completion_returns_on_terminal_status():
    def handler(request):
        return httpx.Response(200, json={"status": SessionStatus.FINISHED.value})

    dc = _client_with(handler)
    result = await dc.wait_for_completion("s", poll_interval=0)
    assert result["status"] == "finished"
    await dc.close()


async def test_wait_for_completion_returns_on_waiting_status():
    def handler(request):
        return httpx.Response(200, json={"status": SessionStatus.WAITING_FOR_USER.value})

    dc = _client_with(handler)
    result = await dc.wait_for_completion("s", poll_interval=0)
    assert result["status"] == "waiting_for_user"
    await dc.close()
