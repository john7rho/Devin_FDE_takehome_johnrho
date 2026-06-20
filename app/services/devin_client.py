import json
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.models.schemas import SessionStatus, DevinStructuredOutput
from app.utils.logger import get_logger


class DevinClient:
    """Client for interacting with Devin API."""
    
    def __init__(self):
        self.api_key = settings.devin_api_key
        self.base_url = settings.devin_api_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=300.0
        )
        self.logger = get_logger()
    
    async def create_session(
        self,
        instructions: str,
        repo_url: str,
        branch: Optional[str] = None,
        max_acu_limit: Optional[int] = None
    ) -> str:
        """Create a new Devin session and return session_id."""
        try:
            payload: Dict[str, Any] = {
                "instructions": instructions,
                "repo_url": repo_url,
                "max_acu_limit": max_acu_limit or settings.max_acu_limit
            }
            if branch:
                payload["branch"] = branch
            
            self.logger.info("Creating Devin session", repo_url=repo_url, branch=branch)
            
            response = await self.client.post("/v1/sessions", json=payload)
            response.raise_for_status()
            
            data = response.json()
            session_id = data.get("session_id")
            if not isinstance(session_id, str):
                raise ValueError("Devin API response did not include a session_id")
            
            self.logger.info("Devin session created", session_id=session_id)
            return session_id
            
        except httpx.HTTPError as e:
            self.logger.error("Failed to create Devin session", error=str(e))
            raise
    
    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get the status of a Devin session."""
        try:
            response = await self.client.get(f"/v1/sessions/{session_id}")
            response.raise_for_status()
            
            data = response.json()
            self.logger.debug("Session status retrieved", session_id=session_id, status=data.get("status"))
            return data
            
        except httpx.HTTPError as e:
            self.logger.error("Failed to get session status", session_id=session_id, error=str(e))
            raise
    
    async def wait_for_completion(
        self,
        session_id: str,
        poll_interval: int = 30,
        timeout: int = 3600
    ) -> Dict[str, Any]:
        """Wait for a session to complete, polling for status."""
        import asyncio
        
        self.logger.info("Waiting for session completion", session_id=session_id)
        
        elapsed = 0
        while elapsed < timeout:
            status_data = await self.get_session_status(session_id)
            status = str(status_data.get("status", ""))
            
            if status in SessionStatus.terminal_values():
                self.logger.info("Session completed", session_id=session_id, status=status)
                return status_data
            
            if status in SessionStatus.waiting_values():
                self.logger.warning("Session waiting for human", session_id=session_id, status=status)
                return status_data
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        self.logger.error("Session timeout", session_id=session_id)
        raise TimeoutError(f"Session {session_id} did not complete within {timeout} seconds")
    
    async def get_session_output(self, session_id: str) -> Optional[DevinStructuredOutput]:
        """Retrieve and parse structured output from a completed session."""
        try:
            response = await self.client.get(f"/v1/sessions/{session_id}/output")
            response.raise_for_status()
            
            data = response.json()
            output_text = data.get("output", "")
            
            # Try to parse JSON from output
            try:
                output_json = json.loads(output_text)
                return DevinStructuredOutput(**output_json)
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(
                    "Failed to parse structured output as JSON",
                    session_id=session_id,
                    error=str(e)
                )
                return None
            
        except httpx.HTTPError as e:
            self.logger.error("Failed to get session output", session_id=session_id, error=str(e))
            return None
    
    async def cancel_session(self, session_id: str) -> bool:
        """Cancel a running Devin session."""
        try:
            response = await self.client.post(f"/v1/sessions/{session_id}/cancel")
            response.raise_for_status()
            
            self.logger.info("Session cancelled", session_id=session_id)
            return True
            
        except httpx.HTTPError as e:
            self.logger.error("Failed to cancel session", session_id=session_id, error=str(e))
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
