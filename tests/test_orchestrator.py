"""Tests for orchestrator issue dedupe (the fixed behavior)."""
from types import SimpleNamespace
from unittest.mock import patch

from app.models.schemas import ScanResult
from app.services.orchestrator import Orchestrator


def _finding(dep, vid):
    return ScanResult(dependency_name=dep, vulnerability_id=vid, description="x", affected_versions=["1.0"])


async def test_dedupe_across_all_issues_and_by_vuln_id(temp_db):
    # Pre-existing COMPLETED issue for flask/CVE-1 must NOT be recreated, even though
    # it's not "pending". Distinct CVEs for the same dependency MUST each be created.
    # Insert via temp_db (the fixture patches the orchestrator's db singleton to this).
    temp_db.insert_issue(issue_url="https://x/issues/1", title="flask CVE-1",
                         finding_type="dependency", dependency_name="flask", vulnerability_id="CVE-1")
    temp_db.update_issue("https://x/issues/1", status="completed")

    findings = [
        _finding("flask", "CVE-1"),   # duplicate of existing -> skip
        _finding("flask", "CVE-2"),   # same dep, new CVE -> create
        _finding("lodash", "CVE-3"),  # new dep -> create
    ]

    created = []

    def fake_create_issue(title, body, labels=None):
        url = f"https://x/issues/{100 + len(created)}"
        created.append(title)
        return SimpleNamespace(html_url=url)

    orch = Orchestrator()
    with patch.object(orch, "github_client") as gh, \
         patch("app.services.orchestrator.DependencyScanner") as scanner_cls:
        gh.create_issue.side_effect = fake_create_issue
        scanner_cls.return_value.scan_all.return_value = findings
        urls = await orch.scan_and_create_issues("/tmp/repo")

    # flask/CVE-1 skipped; flask/CVE-2 and lodash/CVE-3 created
    assert len(urls) == 2
    assert any("CVE-2" in t for t in created)
    assert any("lodash" in t for t in created)
    assert not any("CVE-1" in t for t in created)
