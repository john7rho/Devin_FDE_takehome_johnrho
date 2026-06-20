from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Devin API Configuration
    devin_api_key: str
    devin_api_url: str = "https://api.devin.ai"
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
    
    # Branch Naming Convention
    branch_prefix: str = "fix/dependency"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
