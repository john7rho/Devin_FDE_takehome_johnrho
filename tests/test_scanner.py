"""Unit tests for the dependency scanner (OSV HTTP + filesystem mocked)."""
from unittest.mock import patch, MagicMock

from app.services.scanner import DependencyScanner
from app.models.schemas import ScanResult


def _client_mock(batch_results, vuln_detail=None):
    """Fake httpx.Client context manager.

    batch_results -> the 'results' list the OSV querybatch endpoint returns.
    vuln_detail   -> dict each per-vuln detail GET returns.
    """
    client = MagicMock()
    post_resp = MagicMock()
    post_resp.json.return_value = {"results": batch_results}
    post_resp.raise_for_status.return_value = None
    client.post.return_value = post_resp
    get_resp = MagicMock()
    get_resp.json.return_value = vuln_detail or {}
    client.get.return_value = get_resp
    cm = MagicMock()
    cm.__enter__.return_value = client
    cm.__exit__.return_value = False
    return cm


def _scanner_with_reqs(tmp_path, text):
    (tmp_path / "requirements.txt").write_text(text)
    return DependencyScanner(str(tmp_path))


def test_osv_audit_parses_and_enriches_findings(tmp_path):
    scanner = _scanner_with_reqs(tmp_path, "flask==1.0\nurllib3==1.25.0\n")
    # flask has a vuln (first query); urllib3 is clean (second query).
    batch = [{"vulns": [{"id": "GHSA-1"}]}, {}]
    detail = {
        "summary": "bad thing",
        "database_specific": {"severity": "HIGH"},
        "aliases": ["CVE-2024-1"],
        "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "2.0"}]}]}],
    }
    with patch("app.services.scanner.httpx.Client", return_value=_client_mock(batch, detail)):
        findings = scanner.run_python_audit()
    assert len(findings) == 1
    f = findings[0]
    assert f.dependency_name == "flask"
    assert f.vulnerability_id == "GHSA-1"
    assert f.severity == "HIGH"
    assert f.fixed_version == "2.0"
    assert f.affected_versions == ["1.0"]
    assert "CVE-2024-1" in f.references


def test_osv_audit_no_pins_skips_network(tmp_path):
    # Only comments / editable / unpinned lines -> nothing to query, no HTTP call.
    scanner = _scanner_with_reqs(tmp_path, "# comment\n-e ./superset-core\nflask>=1.0\n")
    with patch("app.services.scanner.httpx.Client") as Client:
        findings = scanner.run_python_audit()
    assert findings == []
    Client.assert_not_called()


def test_osv_audit_handles_http_failure(tmp_path):
    scanner = _scanner_with_reqs(tmp_path, "flask==1.0\n")
    with patch("app.services.scanner.httpx.Client", side_effect=Exception("network down")):
        findings = scanner.run_python_audit()
    assert findings == []


def test_osv_detail_enrichment_is_best_effort(tmp_path):
    # A failing detail fetch must not drop the finding -- the id + link still stand.
    scanner = _scanner_with_reqs(tmp_path, "flask==1.0\n")
    cm = _client_mock([{"vulns": [{"id": "GHSA-1"}]}])
    cm.__enter__.return_value.get.side_effect = Exception("detail fetch failed")
    with patch("app.services.scanner.httpx.Client", return_value=cm):
        findings = scanner.run_python_audit()
    assert len(findings) == 1
    assert findings[0].vulnerability_id == "GHSA-1"
    assert findings[0].severity == "UNKNOWN"  # fell back to the default


def test_parse_pinned_requirements_skips_noise(tmp_path):
    scanner = _scanner_with_reqs(
        tmp_path,
        "# comment\n-e ./superset-core\nFlask==2.3.3\n"
        "requests==2.0.0 ; python_version>'3'\n--hash=sha256:x\nfoo>=1.0\n",
    )
    pins = scanner._parse_pinned_requirements(tmp_path / "requirements.txt")
    assert ("flask", "2.3.3") in pins          # lowercased
    assert ("requests", "2.0.0") in pins        # marker stripped
    assert all(name != "foo" for name, _ in pins)  # unpinned (>=) skipped


def test_deduplicate_findings_by_name_and_id():
    def f(name, vid):
        return ScanResult(dependency_name=name, vulnerability_id=vid, description="", affected_versions=[])

    scanner = DependencyScanner("/tmp/repo")
    out = scanner.deduplicate_findings([f("a", "1"), f("a", "1"), f("b", "2")])
    assert len(out) == 2
