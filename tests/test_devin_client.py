"""Unit tests for the Devin v1 API client (HTTP mocked via httpx.MockTransport)."""
import json

import httpx

from app.services.devin_client import DevinClient, TERMINAL_STATUSES, WAITING_STATUSES


def _client_with(handler):
    dc = DevinClient()
    dc.client = httpx.AsyncClient(base_url=dc.base_url, transport=httpx.MockTransport(handler))
    return dc


async def test_create_session_returns_id_and_url():
    def handler(request):
        return httpx.Response(200, json={"session_id": "devin-123", "url": "https://app.devin.ai/sessions/devin-123"})

    dc = _client_with(handler)
    session_id, url = await dc.create_session(prompt="fix the bug")
    assert session_id == "devin-123"
    assert url == "https://app.devin.ai/sessions/devin-123"
    await dc.close()


async def test_create_session_sends_prompt_and_schema():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"session_id": "s1", "url": "u"})

    dc = _client_with(handler)
    await dc.create_session(prompt="do it", max_acu_limit=5)
    assert seen["prompt"] == "do it"
    assert "structured_output_schema" in seen
    assert seen["max_acu_limit"] == 5
    await dc.close()


async def test_wait_for_completion_returns_on_terminal():
    def handler(request):
        return httpx.Response(200, json={"status_enum": "finished"})

    dc = _client_with(handler)
    result = await dc.wait_for_completion("s", poll_interval=0)
    assert result["status_enum"] in TERMINAL_STATUSES
    await dc.close()


async def test_wait_for_completion_returns_on_blocked():
    def handler(request):
        return httpx.Response(200, json={"status_enum": "blocked"})

    dc = _client_with(handler)
    result = await dc.wait_for_completion("s", poll_interval=0)
    assert result["status_enum"] in WAITING_STATUSES
    await dc.close()


def test_parse_structured_output():
    session = {
        "structured_output": {
            "issue_url": "u", "summary": "s", "branch": "b", "test_result": "pass", "evidence": "e",
        }
    }
    out = DevinClient.parse_structured_output(session)
    assert out is not None
    assert out.pr_url is None
    assert out.needs_human is False


def test_parse_structured_output_missing():
    assert DevinClient.parse_structured_output({}) is None


def test_count_human_messages():
    session = {"messages": [{"origin": "user"}, {"origin": "devin"}, {"type": "user_message"}]}
    assert DevinClient.count_human_messages(session) == 2
