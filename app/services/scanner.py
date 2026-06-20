import subprocess
import json
from typing import List
from pathlib import Path

from app.models.schemas import ScanResult
from app.utils.logger import get_logger


class DependencyScanner:
    """Scanner for detecting dependency vulnerabilities using pip-audit and pnpm audit."""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.logger = get_logger()
    
    def run_pip_audit(self) -> List[ScanResult]:
        """Run pip-audit and return scan results."""
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
            
            if result.returncode != 0:
                self.logger.error("pip-audit failed", error=result.stderr)
                return []
            
            data = json.loads(result.stdout)
            findings = []
            
            for vuln in data.get("dependencies", []):
                for detail in vuln.get("vulnerabilities", []):
                    finding = ScanResult(
                        dependency_name=vuln.get("name"),
                        vulnerability_id=detail.get("id"),
                        severity=detail.get("severity", "UNKNOWN"),
                        description=detail.get("description", ""),
                        affected_versions=vuln.get("version", []),
                        fixed_version=detail.get("fix_versions", [None])[0],
                        references=detail.get("references", [])
                    )
                    findings.append(finding)
            
            self.logger.info("pip-audit completed", findings_count=len(findings))
            return findings
            
        except FileNotFoundError:
            self.logger.warning("pip-audit not found, skipping")
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
        
        if self.repo_path.joinpath("requirements.txt").exists() or \
           self.repo_path.joinpath("setup.py").exists() or \
           self.repo_path.joinpath("pyproject.toml").exists():
            all_findings.extend(self.run_pip_audit())
        
        if self.repo_path.joinpath("package.json").exists():
            all_findings.extend(self.run_pnpm_audit())
        
        return self.deduplicate_findings(all_findings)
