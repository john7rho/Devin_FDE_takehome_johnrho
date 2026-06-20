"""Unit tests for the dependency scanner (subprocess mocked)."""
import json
from unittest.mock import patch, MagicMock

from app.services.scanner import DependencyScanner
from app.models.schemas import ScanResult


def test_pip_audit_parses_findings():
    # Real pip-audit JSON: dependencies[].vulns[], version is a string, no severity.
    fake = {
        "dependencies": [
            {
                "name": "flask",
                "version": "1.0",
                "vulns": [
                    {
                        "id": "CVE-2024-1",
                        "description": "bad thing",
                        "fix_versions": ["2.0"],
                        "aliases": ["GHSA-xxxx"],
                    }
                ],
            }
        ]
    }
    # pip-audit exits 1 WHEN it finds vulnerabilities -- must still parse.
    proc = MagicMock(returncode=1, stdout=json.dumps(fake), stderr="")
    with patch("subprocess.run", return_value=proc):
        findings = DependencyScanner("/tmp/repo").run_pip_audit()
    assert len(findings) == 1
    assert findings[0].dependency_name == "flask"
    assert findings[0].vulnerability_id == "CVE-2024-1"
    assert findings[0].fixed_version == "2.0"
    assert findings[0].affected_versions == ["1.0"]


def test_pip_audit_nonzero_exit_with_findings_not_dropped():
    fake = {"dependencies": [{"name": "urllib3", "version": "1.0",
                              "vulns": [{"id": "CVE-X", "fix_versions": ["2.0"]}]}]}
    proc = MagicMock(returncode=1, stdout=json.dumps(fake), stderr="")
    with patch("subprocess.run", return_value=proc):
        findings = DependencyScanner("/tmp/repo").run_pip_audit()
    assert [f.vulnerability_id for f in findings] == ["CVE-X"]


def test_pip_audit_empty_output_returns_empty():
    proc = MagicMock(returncode=2, stdout="", stderr="boom")
    with patch("subprocess.run", return_value=proc):
        findings = DependencyScanner("/tmp/repo").run_pip_audit()
    assert findings == []


def test_pip_audit_missing_tool_returns_empty():
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        findings = DependencyScanner("/tmp/repo").run_pip_audit()
    assert findings == []


def test_deduplicate_findings_by_name_and_id():
    def f(name, vid):
        return ScanResult(dependency_name=name, vulnerability_id=vid, description="", affected_versions=[])

    scanner = DependencyScanner("/tmp/repo")
    out = scanner.deduplicate_findings([f("a", "1"), f("a", "1"), f("b", "2")])
    assert len(out) == 2
