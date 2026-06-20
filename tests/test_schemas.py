"""Unit tests for the schema enums — especially the SessionStatus helpers that
are now the single source of truth for status classification."""
import pytest
from pydantic import ValidationError

from app.models.schemas import SessionStatus, DevinStructuredOutput


def test_failure_values():
    assert SessionStatus.failure_values() == {"error", "out_of_credits", "usage_limit_exceeded"}


def test_terminal_values_is_failures_plus_finished():
    assert SessionStatus.terminal_values() == {
        "finished",
        "error",
        "out_of_credits",
        "usage_limit_exceeded",
    }
    assert SessionStatus.FINISHED.value in SessionStatus.terminal_values()


def test_waiting_values():
    assert SessionStatus.waiting_values() == {"waiting_for_user", "waiting_for_approval"}


def test_terminal_and_waiting_are_disjoint():
    assert SessionStatus.terminal_values().isdisjoint(SessionStatus.waiting_values())


def test_str_enum_value_lookup():
    # Because SessionStatus subclasses str, value-lookup returns the member.
    # This is the property that lets the enum be the single source of truth.
    assert SessionStatus("finished") is SessionStatus.FINISHED


def test_structured_output_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        DevinStructuredOutput(summary="only a summary")


def test_structured_output_valid_defaults():
    out = DevinStructuredOutput(
        issue_url="http://issue/1",
        summary="fixed it",
        branch="fix/1",
        test_result="pass",
        evidence="tests green",
    )
    assert out.needs_human is False
    assert out.files_changed == []
    assert out.pr_url is None
