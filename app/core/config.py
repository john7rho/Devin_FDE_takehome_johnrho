from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Devin API Configuration
    devin_api_key: str
    devin_api_url: str = "https://api.devin.ai"
    # Cognition/Devin enterprise key for the consumption (ACU) API; falls back to
    # devin_api_key. NOTE: the consumption API also requires Devin to enable it for
    # the account, so ACU stays unavailable (403) until the org is entitled.
    cog_api_key: Optional[str] = None
    max_acu_limit: int = 10
    max_concurrent_sessions: int = 3
    
    # GitHub Configuration
    github_token: str
    github_repo_owner: str  # Fork owner
    github_repo_name: str = "superset"
    github_fork_url: Optional[str] = None
    
    # Database Configuration
    database_path: str = "data/state.db"
    
    # Logging Configuration
    log_level: str = "INFO"
    log_path: str = "logs"
    
    # Scanner Configuration
    scan_interval_hours: int = 24
    enable_pip_audit: bool = True
    enable_pnpm_audit: bool = True
    # Local checkout the dashboard "Scan" buttons audit (server-side path; the
    # browser can't supply a filesystem path). Empty -> nothing to scan.
    scan_repo_path: Optional[str] = None
    
    # Branch Naming Convention
    branch_prefix: str = "fix/dependency"
    
settings = Settings()  # type: ignore[call-arg]
