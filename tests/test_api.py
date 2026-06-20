"""Smoke tests for the FastAPI surface using TestClient."""
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


def test_metrics_empty(temp_db):
    r = client.get("/api/v1/metrics")
    assert r.status_code == 200
    assert r.json()["total_sessions"] == 0


def test_sessions_empty(temp_db):
    r = client.get("/api/v1/sessions")
    assert r.status_code == 200
    assert r.json() == []


def test_unknown_session_404(temp_db):
    r = client.get("/api/v1/sessions/does-not-exist")
    assert r.status_code == 404


def test_seed_endpoint_removed(temp_db):
    r = client.post("/api/v1/seed")
    assert r.status_code == 404


def test_scan_only_does_not_dispatch_sessions(temp_db):
    # Regression: scan_only must never process pending issues (it used to fall
    # through to process_pending_issues() when no repo_path was given).
    with patch("app.api.routes.Orchestrator.process_pending_issues",
               new=AsyncMock(return_value=[])) as proc:
        r = client.post("/api/v1/runs", json={"scan_only": True})
        assert r.status_code == 200
    proc.assert_not_called()


def test_scan_and_process_dispatches(temp_db):
    with patch("app.api.routes.Orchestrator.process_pending_issues",
               new=AsyncMock(return_value=[])) as proc:
        r = client.post("/api/v1/runs", json={"scan_only": False})
        assert r.status_code == 200
    proc.assert_called_once()


def test_run_is_tracked_and_retrievable(temp_db):
    # POST /runs must record the run; GET /runs/{id} must return the real record,
    # not the old "unknown" stub.
    with patch("app.api.routes.Orchestrator.process_pending_issues",
               new=AsyncMock(return_value=[])):
        run_id = client.post("/api/v1/runs", json={"scan_only": True}).json()["run_id"]
    r = client.get(f"/api/v1/runs/{run_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == run_id
    assert body["status"] != "unknown"
    assert body["scan_only"] is True


def test_unknown_run_404(temp_db):
    assert client.get("/api/v1/runs/does-not-exist").status_code == 404


def test_metrics_outcome_breakdown_present(temp_db):
    body = client.get("/api/v1/metrics").json()
    assert set(body["outcome_breakdown"]) == {"success", "blocked", "failed"}
    assert "blocked_sessions" in body


def test_logs_endpoint_reads_log_store(temp_db, tmp_path, monkeypatch):
    # /logs reads the append-only JSONL store and filters by session_id.
    import app.services.metrics as m
    monkeypatch.setattr(m.settings, "log_path", str(tmp_path))
    logfile = tmp_path / "sessions.jsonl"
    logfile.write_text(
        '{"session_id": "abc", "event": "step one", "level": "info"}\n'
        '{"session_id": "other", "event": "noise", "level": "info"}\n'
        '{"session_id": "abc", "event": "step two", "level": "info"}\n'
    )
    r = client.get("/api/v1/logs/abc")
    assert r.status_code == 200
    logs = r.json()
    assert len(logs) == 2
    assert [line["event"] for line in logs] == ["step one", "step two"]
