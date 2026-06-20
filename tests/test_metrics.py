"""Unit tests for metric aggregation.

These exercise the metrics LOGIC against known DB rows. Note: in the live
pipeline ``human_msgs`` is currently always 0 (the orchestrator reads a Devin
field that does not exist), so real autonomy is inflated — that is an upstream
data bug, separate from the aggregation logic verified here.
"""
from app.services.metrics import MetricsCollector


def _seed(temp_db, sid, status, human_msgs=0, acu=0.0):
    temp_db.insert_session(sid, f"http://issue/{sid}", "http://repo", status=status)
    temp_db.update_session(sid, human_msgs=human_msgs, acu_used=acu)


def test_empty_db_returns_zeros(temp_db):
    m = MetricsCollector().calculate_metrics()
    assert m.total_sessions == 0
    assert m.autonomy_rate == 0.0
    assert m.failure_breakdown == {}


def test_session_counts_and_acu(temp_db):
    _seed(temp_db, "a", "finished", human_msgs=0, acu=2.0)
    _seed(temp_db, "b", "finished", human_msgs=3, acu=1.0)
    _seed(temp_db, "c", "running")
    _seed(temp_db, "d", "error")
    m = MetricsCollector().calculate_metrics()
    assert m.total_sessions == 4
    assert m.active_sessions == 1
    assert m.completed_sessions == 2
    assert m.failed_sessions == 1
    assert m.total_acu_used == 3.0
    assert m.failure_breakdown == {"error": 1}


def test_autonomy_rate_counts_only_zero_human_finished(temp_db):
    _seed(temp_db, "a", "finished", human_msgs=0)
    _seed(temp_db, "b", "finished", human_msgs=2)
    m = MetricsCollector().calculate_metrics()
    # 1 of 2 finished sessions ran with zero human messages
    assert m.autonomy_rate == 50.0


def test_outcome_rate(temp_db):
    _seed(temp_db, "a", "finished")
    _seed(temp_db, "b", "error")
    m = MetricsCollector().calculate_metrics()
    assert m.outcome_rate == 50.0


def test_cycle_time_is_non_negative(temp_db):
    _seed(temp_db, "a", "finished")
    m = MetricsCollector().calculate_metrics()
    assert m.avg_cycle_time >= 0.0
