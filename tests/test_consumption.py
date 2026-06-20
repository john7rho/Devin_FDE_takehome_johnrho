"""Tests for the Devin consumption API client (HTTP mocked)."""
import httpx
import pytest

import app.services.consumption as consumption


@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch):
    # fresh cache + a real-looking key for each test
    consumption._cache.update(ts=0.0, fetched=False, value=None)
    monkeypatch.setattr(consumption.settings, "devin_api_key", "apk_user_test")
    yield
    consumption._cache.update(ts=0.0, fetched=False, value=None)


def _mock_get(monkeypatch, *, status, json_body=None):
    def fake_get(url, headers=None, params=None, timeout=None):
        return httpx.Response(status, json=json_body or {}, request=httpx.Request("GET", url))
    monkeypatch.setattr(consumption.httpx, "get", fake_get)


def test_returns_total_acus_on_200(monkeypatch):
    _mock_get(monkeypatch, status=200, json_body={"total_acus": 12.5})
    assert consumption.get_total_acus(force=True) == 12.5


def test_returns_none_when_gated_403(monkeypatch):
    _mock_get(monkeypatch, status=403, json_body={"detail": "Contact support to enable"})
    assert consumption.get_total_acus(force=True) is None


def test_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(consumption.settings, "devin_api_key", "your-api-key-here")
    assert consumption.get_total_acus(force=True) is None


def test_caches_result(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, headers=None, params=None, timeout=None):
        calls["n"] += 1
        return httpx.Response(200, json={"total_acus": 3.0}, request=httpx.Request("GET", url))

    monkeypatch.setattr(consumption.httpx, "get", fake_get)
    consumption.get_total_acus(force=True)
    consumption.get_total_acus()  # cached, no second HTTP call
    assert calls["n"] == 1


def test_status_reports_gated(monkeypatch):
    _mock_get(monkeypatch, status=403)
    status = consumption.get_status()
    assert status["enabled"] is False
    assert status["total_acus"] is None
