"""Unit tests for the SQLite persistence layer (isolated temp DB per test)."""


def test_insert_and_get_session(temp_db):
    temp_db.insert_session("s1", "http://issue/1", "http://repo", branch="fix/1", status="created")
    s = temp_db.get_session("s1")
    assert s["session_id"] == "s1"
    assert s["status"] == "created"
    assert s["branch"] == "fix/1"


def test_get_missing_session_returns_none(temp_db):
    assert temp_db.get_session("nope") is None


def test_update_session_sets_columns(temp_db):
    temp_db.insert_session("s1", "i", "r")
    temp_db.update_session("s1", status="finished", acu_used=3.5, human_msgs=2)
    s = temp_db.get_session("s1")
    assert s["status"] == "finished"
    assert s["acu_used"] == 3.5
    assert s["human_msgs"] == 2


def test_get_all_sessions_and_status_filter(temp_db):
    temp_db.insert_session("s1", "i", "r", status="finished")
    temp_db.insert_session("s2", "i2", "r", status="running")
    assert len(temp_db.get_all_sessions()) == 2
    assert len(temp_db.get_all_sessions(status="finished")) == 1


def test_insert_issue_is_pending_by_default(temp_db):
    temp_db.insert_issue("http://issue/1", "Vuln in lodash", "dependency", dependency_name="lodash")
    pending = temp_db.get_pending_issues()
    assert len(pending) == 1
    assert pending[0]["status"] == "pending"


def test_update_issue_status_removes_from_pending(temp_db):
    temp_db.insert_issue("http://issue/1", "t", "dependency")
    temp_db.update_issue("http://issue/1", status="completed")
    assert temp_db.get_pending_issues() == []


def test_insert_issue_dedups_on_unique_url(temp_db):
    # issues.issue_url is UNIQUE + INSERT OR IGNORE -> second insert is a no-op
    temp_db.insert_issue("http://issue/1", "first", "dependency")
    temp_db.insert_issue("http://issue/1", "second", "dependency")
    assert len(temp_db.get_pending_issues()) == 1
