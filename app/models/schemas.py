import json

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    FINISHED = "finished"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    ERROR = "error"
    OUT_OF_CREDITS = "out_of_credits"
    USAGE_LIMIT_EXCEEDED = "usage_limit_exceeded"

    @classmethod
    def failure_values(cls) -> set[str]:
        """Status values that mean the session failed."""
        return {cls.ERROR.value, cls.OUT_OF_CREDITS.value, cls.USAGE_LIMIT_EXCEEDED.value}

    @classmethod
    def terminal_values(cls) -> set[str]:
        """Status values that mean the session is done (success or failure)."""
        return cls.failure_values() | {cls.FINISHED.value}

    @classmethod
    def waiting_values(cls) -> set[str]:
        """Status values that mean the session is blocked waiting on a human."""
        return {cls.WAITING_FOR_USER.value, cls.WAITING_FOR_APPROVAL.value}


class IssueStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class DevinStructuredOutput(BaseModel):
    """Structured output schema required from Devin sessions."""
    issue_url: str = Field(..., description="URL of the GitHub issue being addressed")
    summary: str = Field(..., description="Summary of the work performed")
    branch: str = Field(..., description="Branch name where changes were made")
    pr_url: Optional[str] = Field(None, description="URL of the created PR")
    files_changed: List[str] = Field(default_factory=list, description="List of files modified")
    tests_run: List[str] = Field(default_factory=list, description="List of tests executed")
    test_result: str = Field(..., description="Result of test execution (pass/fail/skip)")
    evidence: str = Field(..., description="Evidence of the fix (logs, diffs, screenshots)")
    needs_human: bool = Field(default=False, description="Whether human intervention is needed")


class SessionCreate(BaseModel):
    issue_url: str
    repo_url: str
    branch: str
    requested_fix: str
    requested_tests: str
    expected_pr_output: str


class SessionResponse(BaseModel):
    session_id: str
    issue_url: str
    repo_url: str
    branch: Optional[str]
    status: SessionStatus
    status_detail: Optional[str]
    created_at: datetime
    updated_at: datetime
    acu_used: float
    human_msgs: int
    pr_url: Optional[str]
    structured_output: Optional[Dict[str, Any]]
    error_message: Optional[str]
    devin_session_id: Optional[str] = None

    @field_validator("structured_output", mode="before")
    @classmethod
    def _parse_structured_output(cls, v: Any) -> Any:
        """DB stores structured_output as a JSON string; coerce it to a dict."""
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
        return v


class IssueCreate(BaseModel):
    title: str
    body: str
    finding_type: str
    dependency_name: Optional[str] = None
    vulnerability_id: Optional[str] = None
    severity: Optional[str] = None


class IssueResponse(BaseModel):
    issue_id: int
    issue_url: str
    title: str
    finding_type: str
    dependency_name: Optional[str]
    vulnerability_id: Optional[str]
    severity: Optional[str]
    created_at: datetime
    session_id: Optional[str]
    status: IssueStatus


class ScanResult(BaseModel):
    """Result from dependency scanning."""
    dependency_name: str
    vulnerability_id: Optional[str] = None
    severity: Optional[str] = None
    description: str
    affected_versions: List[str]
    fixed_version: Optional[str] = None
    references: List[str] = Field(default_factory=list)


class MetricResponse(BaseModel):
    metric_name: str
    metric_value: float
    timestamp: datetime
    metadata: Optional[Dict[str, Any]]


class MetricsSummary(BaseModel):
    """Aggregated metrics summary."""
    autonomy_rate: float  # % finished with human_msgs=0
    outcome_rate: float   # success / total
    avg_cycle_time: float  # updated_at - created_at in seconds
    total_acu_used: float
    failure_breakdown: Dict[str, int]
    total_sessions: int
    active_sessions: int
    completed_sessions: int
    failed_sessions: int
    blocked_sessions: int = 0
    # SPEC outcome classification: finished->success, waiting->blocked,
    # error/out_of_credits/usage_limit_exceeded->failed
    outcome_breakdown: Dict[str, int] = Field(default_factory=dict)
