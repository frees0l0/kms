"""
Microsoft Teams service for bot integration.
"""

import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger("kms.teams")


class TeamsService:
    """Service for interacting with Microsoft Teams Bot Framework."""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        tenant_id: str = "common"
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.tenant_id = tenant_id
        self.token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self.api_base = "https://smba.trafficmanager.net/teams/v1.0"

    async def get_access_token(self) -> str:
        """Obtain an access token for the Teams API."""
        scope = "https://api.botframework.com/.default"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "scope": scope
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.token_url, data=payload)
            response.raise_for_status()
            data = response.json()
            return data["access_token"]

    async def send_message(
        self,
        conversation_id: str,
        message: str,
        service_url: Optional[str] = None
    ) -> Dict[Any, Any]:
        """Send a message to a Teams conversation."""
        self.reload_token()
        access_token = await self.get_access_token()
        base_url = service_url or self.api_base

        url = f"{base_url}/conversations/{conversation_id}/activities"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        activity = {
            "type": "message",
            "text": message,
            "from": {"id": self.app_id},
            "channelId": "msteams"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=activity, headers=headers)
            logger.info(f"Teams message sent: conversation_id={conversation_id}, text_len={len(message)}")
            return response.json()

    async def send_test_message(self, conversation_id: Optional[str] = None) -> Dict[Any, Any]:
        """Send a test message to verify the Teams integration."""
        test_message = "✅ **KMS Bot Connected**\n\nYour Microsoft Teams integration is working correctly!"
        logger.info(f"Teams test message sent: conversation_id={conversation_id}")
        return await self.send_message(conversation_id or "test", test_message)

    async def verify_credentials(self) -> bool:
        """Verify that the Teams credentials are valid by obtaining an access token."""
        try:
            await self.get_access_token()
            logger.info("Teams credentials verified successfully")
            return True
        except Exception as e:
            logger.error(f"Teams credential verification failed: {e}")
            return False

    def reload_token(self):
        """Reload Teams credentials from database Integration table."""
        from core.database import SessionLocal
        from models import Integration
        from sqlalchemy import select
        with SessionLocal() as db:
            result = db.execute(
                select(Integration.config).where(Integration.channel == "teams")
            )
            row = result.scalar_one_or_none()
            if row:
                self.app_id = row.get("app_id", "")
                self.app_secret = row.get("app_secret", "")
                self.tenant_id = row.get("tenant_id", "common")
            else:
                self.app_id = ""
                self.app_secret = ""
                self.tenant_id = "common"
            self.token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"


# Global shared instance
_teams_service: Optional["TeamsService"] = None


def get_teams_service() -> "TeamsService":
    """Get the global TeamsService instance."""
    global _teams_service
    if _teams_service is None:
        _teams_service = TeamsService(app_id="", app_secret="", tenant_id="common")
    return _teams_service
