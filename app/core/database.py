import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional
import json

from app.core.config import settings


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.database_path
        self._ensure_database_exists()
    
    def _ensure_database_exists(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Sessions table - tracks Devin sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                issue_url TEXT NOT NULL,
                repo_url TEXT NOT NULL,
                branch TEXT,
                status TEXT NOT NULL,
                status_detail TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acu_used REAL DEFAULT 0,
                human_msgs INTEGER DEFAULT 0,
                pr_url TEXT,
                structured_output TEXT,
                error_message TEXT,
                devin_session_id TEXT
            )
        """)
        
        # Issues table - tracks GitHub issues created
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                finding_type TEXT NOT NULL,
                dependency_name TEXT,
                vulnerability_id TEXT,
                severity TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        
        # Metrics table - for aggregated metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)

        # Migration for pre-existing DBs: add devin_session_id if it's absent.
        try:
            cursor.execute("ALTER TABLE sessions ADD COLUMN devin_session_id TEXT")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()
    
    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def insert_session(self, session_id: str, issue_url: str, repo_url: str, 
                      branch: Optional[str] = None, status: str = "created") -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sessions 
                (session_id, issue_url, repo_url, branch, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (session_id, issue_url, repo_url, branch, status))
            conn.commit()
    
    def update_session(self, session_id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [session_id]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE sessions 
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, values)
            conn.commit()
    
    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_all_sessions(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM sessions WHERE status = ?", (status,))
            else:
                cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    def insert_issue(self, issue_url: str, title: str, finding_type: str,
                    dependency_name: Optional[str] = None, vulnerability_id: Optional[str] = None,
                    severity: Optional[str] = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO issues 
                (issue_url, title, finding_type, dependency_name, vulnerability_id, severity)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (issue_url, title, finding_type, dependency_name, vulnerability_id, severity))
            conn.commit()
            return int(cursor.lastrowid or 0)
    
    def update_issue(self, issue_url: str, session_id: Optional[str] = None, status: Optional[str] = None) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            
            if session_id:
                updates.append("session_id = ?")
                params.append(session_id)
            if status:
                updates.append("status = ?")
                params.append(status)
            
            if updates:
                params.append(issue_url)
                cursor.execute(f"""
                    UPDATE issues 
                    SET {', '.join(updates)}
                    WHERE issue_url = ?
                """, params)
                conn.commit()
    
    def get_pending_issues(self) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM issues
                WHERE status = 'pending'
                ORDER BY created_at ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_all_issues(self) -> list[dict[str, Any]]:
        """All issues regardless of status, newest first (for the dashboard panel)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM issues ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    def record_metric(self, metric_name: str, metric_value: float, metadata: Optional[dict[str, Any]] = None) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO metrics (metric_name, metric_value, metadata)
                VALUES (?, ?, ?)
            """, (metric_name, metric_value, json.dumps(metadata) if metadata else None))
            conn.commit()
    
    def get_metrics(self, metric_name: Optional[str] = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if metric_name:
                cursor.execute("""
                    SELECT * FROM metrics 
                    WHERE metric_name = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (metric_name, limit))
            else:
                cursor.execute("""
                    SELECT * FROM metrics 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
            return [dict(row) for row in cursor.fetchall()]


# Global database instance
db = Database()
