import subprocess
import json
import re
from typing import List
from pathlib import Path

import httpx

from app.core.config import settings
from app.models.schemas import ScanResult
from app.utils.logger import get_logger

# OSV (https://osv.dev) — open-source vulnerability DB with a free, unauthenticated
# batch API. We audit declared dependency versions against it instead of installing
# them, so the scan is interpreter-agnostic and never builds anything.
OSV_QUERYBATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_VULN_URL = "https://api.osv.dev/v1/vulns/"
# `name==version` pins; everything else (ranges, markers, options) is skipped.
_PIN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9._\-+!]*)")


class DependencyScanner:
    """Scanner for detecting dependency vulnerabilities using OSV (Python) and pnpm audit (Node)."""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.logger = get_logger()

    def _python_requirement_files(self) -> List[Path]:
        """Pinned requirement files to audit, in a stable order. Covers a root
        requirements.txt and a requirements/ directory of compiled *.txt files
        (the Superset layout). .in files are skipped -- they're unpinned."""
        files: List[Path] = []
        root_req = self.repo_path / "requirements.txt"
        if root_req.is_file():
            files.append(root_req)
        req_dir = self.repo_path / "requirements"
        if req_dir.is_dir():
            files.extend(sorted(req_dir.glob("*.txt")))
        return files

    def _parse_pinned_requirements(self, path: Path) -> List[tuple]:
        """Extract (name, version) from `name==version` lines, skipping comments,
        options/includes (-e, -r, --hash, ...), editable/local/VCS installs, and
        environment markers. Names are lowercased for stable dedupe/matching."""
        pins: List[tuple] = []
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            self.logger.warning("Could not read requirements file", path=str(path), error=str(e))
            return pins
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            line = line.split(";")[0].split("--hash")[0].strip()  # drop markers/hashes
            m = _PIN_RE.match(line)
            if m:
                pins.append((m.group(1).lower(), m.group(2)))
        return pins

    def run_python_audit(self) -> List[ScanResult]:
        """Audit the repo's pinned Python dependencies against the OSV database.

        We query OSV by (name, version) rather than running `pip-audit -r`: pip-audit
        resolves/installs each requirement in a throwaway venv, which fails for large
        real-world projects whose pins lack wheels for the running interpreter (e.g.
        Superset's deps under this image's Python). OSV checks declared versions
        directly -- no install, no build, interpreter-agnostic. Each hit is enriched
        best-effort (severity/fix/aliases) from the per-vulnerability OSV endpoint.
        """
        files = self._python_requirement_files()
        pins: "dict[tuple, None]" = {}
        for f in files:
            for name, version in self._parse_pinned_requirements(f):
                pins[(name, version)] = None
        if not pins:
            self.logger.info("No pinned Python requirements to audit", repo_path=str(self.repo_path))
            return []

        packages = list(pins.keys())
        queries = [{"package": {"name": n, "ecosystem": "PyPI"}, "version": v} for n, v in packages]
        try:
            self.logger.info("Querying OSV", package_count=len(packages),
                             requirement_files=[f.name for f in files])
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(OSV_QUERYBATCH_URL, json={"queries": queries})
                resp.raise_for_status()
                results = resp.json().get("results", [])

                findings: List[ScanResult] = []
                for (name, version), result in zip(packages, results):
                    for vuln in (result.get("vulns") or []):
                        vid = vuln.get("id")
                        if vid:
                            findings.append(self._osv_finding(client, name, version, vid))

            self.logger.info("OSV audit completed", findings_count=len(findings))
            return findings
        except Exception as e:
            self.logger.error("OSV audit failed", error=str(e))
            return []

    def _osv_finding(self, client: "httpx.Client", name: str, version: str, vuln_id: str) -> ScanResult:
        """Build a ScanResult for one OSV vuln id, enriching with detail best-effort.
        The id + OSV link always stand even if the detail fetch fails."""
        severity = "UNKNOWN"
        description = ""
        fixed_version = None
        references = [f"https://osv.dev/vulnerability/{vuln_id}"]
        try:
            detail = client.get(f"{OSV_VULN_URL}{vuln_id}").json()
            description = detail.get("summary") or (detail.get("details") or "")[:500]
            sev = (detail.get("database_specific") or {}).get("severity")
            if sev:
                severity = str(sev).upper()
            for aff in detail.get("affected") or []:
                for rng in aff.get("ranges") or []:
                    for ev in rng.get("events") or []:
                        if ev.get("fixed"):
                            fixed_version = ev["fixed"]
            references += [a for a in (detail.get("aliases") or [])]
        except Exception:
            pass  # enrichment is best-effort
        return ScanResult(
            dependency_name=name,
            vulnerability_id=vuln_id,
            severity=severity,
            description=description or f"{name} {version} is affected by {vuln_id}.",
            affected_versions=[version],
            fixed_version=fixed_version,
            references=references,
        )
    
    def run_pnpm_audit(self) -> List[ScanResult]:
        """Run pnpm audit and return scan results."""
        if not self.repo_path:
            self.logger.warning("No repo path provided for pnpm audit")
            return []
        
        try:
            self.logger.info("Running pnpm audit", repo_path=str(self.repo_path))
            
            result = subprocess.run(
                ["pnpm", "audit", "--json"],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                # pnpm audit returns non-zero even when vulnerabilities are found
                # So we still try to parse the output
                pass
            
            data = json.loads(result.stdout)
            findings = []
            
            for advisory in data.get("advisories", {}).values():
                finding = ScanResult(
                    dependency_name=advisory.get("module_name"),
                    vulnerability_id=advisory.get("github_advisory_id"),
                    severity=advisory.get("severity", "UNKNOWN"),
                    description=advisory.get("overview", ""),
                    affected_versions=[advisory.get("vulnerable_versions", "")],
                    fixed_version=advisory.get("patched_versions"),
                    references=[advisory.get("url", "")]
                )
                findings.append(finding)
            
            self.logger.info("pnpm audit completed", findings_count=len(findings))
            return findings
            
        except FileNotFoundError:
            self.logger.warning("pnpm not found, skipping")
            return []
        except Exception as e:
            self.logger.error("Error running pnpm audit", error=str(e))
            return []
    
    def deduplicate_findings(self, findings: List[ScanResult]) -> List[ScanResult]:
        """Deduplicate findings based on dependency_name and vulnerability_id."""
        seen = set()
        unique_findings = []
        
        for finding in findings:
            key = (finding.dependency_name, finding.vulnerability_id)
            if key not in seen:
                seen.add(key)
                unique_findings.append(finding)
        
        self.logger.info(
            "Findings deduplicated",
            original_count=len(findings),
            unique_count=len(unique_findings)
        )
        return unique_findings
    
    def scan_all(self) -> List[ScanResult]:
        """Run all enabled scanners and return combined, deduplicated results."""
        all_findings = []

        has_python = (
            self.repo_path.joinpath("requirements.txt").exists()
            or self.repo_path.joinpath("requirements").is_dir()
            or self.repo_path.joinpath("setup.py").exists()
            or self.repo_path.joinpath("pyproject.toml").exists()
        )
        if settings.enable_pip_audit and has_python:
            all_findings.extend(self.run_python_audit())

        if settings.enable_pnpm_audit and self.repo_path.joinpath("package.json").exists():
            all_findings.extend(self.run_pnpm_audit())

        return self.deduplicate_findings(all_findings)
