import subprocess
import json
from typing import List
from pathlib import Path

from app.core.config import settings
from app.models.schemas import ScanResult
from app.utils.logger import get_logger


class DependencyScanner:
    """Scanner for detecting dependency vulnerabilities using pip-audit and pnpm audit."""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.logger = get_logger()
    
    def run_pip_audit(self) -> List[ScanResult]:
        """Run pip-audit and return scan results.

        pip-audit exits non-zero (1) precisely WHEN it finds vulnerabilities, so we
        must parse stdout regardless of the exit code -- a genuine failure is signalled
        by empty/unparseable stdout, not by a nonzero code. The JSON shape is
        {"dependencies": [{"name", "version", "vulns": [{"id", "fix_versions",
        "aliases", "description"}]}]} (older pip-audit emitted a bare list).
        Ref: pip-audit README exit codes -- https://github.com/pypa/pip-audit#exit-codes
        """
        if not self.repo_path:
            self.logger.warning("No repo path provided for pip-audit")
            return []

        try:
            self.logger.info("Running pip-audit", repo_path=str(self.repo_path))

            result = subprocess.run(
                ["pip-audit", "--format", "json", "--output", "-"],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )

            if not (result.stdout or "").strip():
                # No JSON at all -> genuine tool failure (bad path, install error, ...)
                self.logger.error("pip-audit produced no output",
                                  error=result.stderr, returncode=result.returncode)
                return []

            data = json.loads(result.stdout)
            # Accept both the object form ({"dependencies": [...]}) and a bare list.
            deps = data.get("dependencies", []) if isinstance(data, dict) else data
            findings = []

            for dep in deps:
                version = dep.get("version")
                for v in (dep.get("vulns") or dep.get("vulnerabilities") or []):
                    fix_versions = v.get("fix_versions") or []
                    finding = ScanResult(
                        dependency_name=dep.get("name"),
                        vulnerability_id=v.get("id"),
                        severity=v.get("severity", "UNKNOWN"),  # pip-audit omits severity
                        description=v.get("description", ""),
                        affected_versions=[version] if version else [],
                        fixed_version=fix_versions[0] if fix_versions else None,
                        references=v.get("aliases") or v.get("references") or [],
                    )
                    findings.append(finding)

            self.logger.info("pip-audit completed", findings_count=len(findings))
            return findings

        except FileNotFoundError:
            self.logger.warning("pip-audit not found, skipping")
            return []
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error("pip-audit output not parseable", error=str(e))
            return []
        except Exception as e:
            self.logger.error("Error running pip-audit", error=str(e))
            return []
    
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
            or self.repo_path.joinpath("setup.py").exists()
            or self.repo_path.joinpath("pyproject.toml").exists()
        )
        if settings.enable_pip_audit and has_python:
            all_findings.extend(self.run_pip_audit())

        if settings.enable_pnpm_audit and self.repo_path.joinpath("package.json").exists():
            all_findings.extend(self.run_pnpm_audit())

        return self.deduplicate_findings(all_findings)
