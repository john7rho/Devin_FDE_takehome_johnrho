import json
from typing import Any, Dict, List
from datetime import datetime, timedelta
from pathlib import Path

from app.core.config import settings
from app.core.database import db
from app.models.schemas import MetricsSummary, SessionStatus
from app.services import consumption
from app.utils.logger import get_logger


class MetricsCollector:
    """Collects and aggregates metrics from session data."""
    
    def __init__(self):
        self.logger = get_logger()
    
    def calculate_metrics(self) -> MetricsSummary:
        """Calculate aggregated metrics from all sessions."""
        sessions = db.get_all_sessions()
        
        if not sessions:
            return MetricsSummary(
                autonomy_rate=0.0,
                outcome_rate=0.0,
                avg_cycle_time=0.0,
                total_acu_used=0.0,
                failure_breakdown={},
                total_sessions=0,
                active_sessions=0,
                completed_sessions=0,
                failed_sessions=0,
                blocked_sessions=0,
                outcome_breakdown={"success": 0, "blocked": 0, "failed": 0},
            )

        total_sessions = len(sessions)
        active_sessions = len([s for s in sessions if s["status"] == SessionStatus.RUNNING.value])
        completed_sessions = len([s for s in sessions if s["status"] == SessionStatus.FINISHED.value])
        failed_sessions = len([s for s in sessions if s["status"] in SessionStatus.failure_values()])
        blocked_sessions = len([s for s in sessions if s["status"] in SessionStatus.waiting_values()])

        # SPEC outcome classification: success=finished, blocked=waiting_for_user/approval,
        # failed=error/out_of_credits/usage_limit_exceeded
        outcome_breakdown = {
            "success": completed_sessions,
            "blocked": blocked_sessions,
            "failed": failed_sessions,
        }
        
        # Autonomy rate: % finished with human_msgs=0
        autonomous_sessions = [
            s for s in sessions 
            if s["status"] == SessionStatus.FINISHED.value and s.get("human_msgs", 0) == 0
        ]
        autonomy_rate = (
            len(autonomous_sessions) / completed_sessions * 100 
            if completed_sessions > 0 else 0.0
        )
        
        # Outcome rate: success / total
        outcome_rate = (
            completed_sessions / total_sessions * 100 
            if total_sessions > 0 else 0.0
        )
        
        # Average cycle time
        cycle_times = []
        for s in sessions:
            if s["created_at"] and s["updated_at"]:
                created = datetime.fromisoformat(s["created_at"])
                updated = datetime.fromisoformat(s["updated_at"])
                cycle_times.append((updated - created).total_seconds())
        
        avg_cycle_time = (
            sum(cycle_times) / len(cycle_times) 
            if cycle_times else 0.0
        )
        
        # Total ACU used. Per the Devin docs, ACU is not on the session object;
        # the consumption API is the only programmatic source (aggregate, gated).
        # Prefer the real aggregate when entitled; otherwise fall back to the
        # per-session sum (honest-zero until ACU is available).
        total_acu_used = sum(s.get("acu_used", 0) for s in sessions)
        real_acus = consumption.get_total_acus()
        if real_acus is not None:
            total_acu_used = real_acus
        
        # Failure breakdown
        failure_breakdown: Dict[str, int] = {}
        for s in sessions:
            if s["status"] in SessionStatus.failure_values():
                status = s["status"]
                failure_breakdown[status] = failure_breakdown.get(status, 0) + 1
        
        # Record metrics to database
        self._record_metrics_to_db(
            autonomy_rate,
            outcome_rate,
            avg_cycle_time,
            total_acu_used,
            failure_breakdown,
            total_sessions,
            active_sessions,
            completed_sessions,
            blocked_sessions,
        )

        return MetricsSummary(
            autonomy_rate=autonomy_rate,
            outcome_rate=outcome_rate,
            avg_cycle_time=avg_cycle_time,
            total_acu_used=total_acu_used,
            failure_breakdown=failure_breakdown,
            total_sessions=total_sessions,
            active_sessions=active_sessions,
            completed_sessions=completed_sessions,
            failed_sessions=failed_sessions,
            blocked_sessions=blocked_sessions,
            outcome_breakdown=outcome_breakdown,
        )

    def _record_metrics_to_db(
        self,
        autonomy_rate: float,
        outcome_rate: float,
        avg_cycle_time: float,
        total_acu_used: float,
        failure_breakdown: Dict[str, int],
        total_sessions: int = 0,
        active_sessions: int = 0,
        completed_sessions: int = 0,
        blocked_sessions: int = 0,
    ) -> None:
        """Record metrics to the metrics table (each call appends a history point)."""
        db.record_metric("autonomy_rate", autonomy_rate)
        db.record_metric("outcome_rate", outcome_rate)
        db.record_metric("avg_cycle_time", avg_cycle_time)
        db.record_metric("total_acu_used", total_acu_used)
        db.record_metric("total_sessions", total_sessions)
        db.record_metric("blocked_sessions", blocked_sessions)
        db.record_metric("active_sessions", active_sessions)
        db.record_metric("completed_sessions", completed_sessions)

        for status, count in failure_breakdown.items():
            db.record_metric(
                f"failure_{status}",
                count,
                metadata={"status": status}
            )
    
    def get_metrics_history(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get historical metrics for a specific metric name."""
        cutoff = datetime.now() - timedelta(hours=hours)
        metrics = db.get_metrics(metric_name, limit=1000)
        
        # Filter by time
        filtered = [
            m for m in metrics
            if datetime.fromisoformat(m["timestamp"]) >= cutoff
        ]
        
        return filtered
    
    def get_session_logs(self, session_id: str, limit: int = 500) -> List[Dict[str, Any]]:
        """Return the structured log lines tagged with this session_id, read from
        the append-only JSONL store. Newest `limit` lines, in chronological order."""
        log_file = Path(settings.log_path) / "sessions.jsonl"
        if not log_file.exists():
            return []
        out: List[Dict[str, Any]] = []
        try:
            with log_file.open() as f:
                for line in f:
                    line = line.strip()
                    # cheap pre-filter: skip lines that can't reference this session
                    if not line or session_id not in line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("session_id") == session_id:
                        out.append(entry)
        except OSError:
            return []
        return out[-limit:]
