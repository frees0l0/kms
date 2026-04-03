"""
Telegram service for bot integration.
"""

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger("kms.telegram")


class TelegramService:
    """Service for interacting with Telegram Bot API."""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.api_base = f"https://api.telegram.org/bot{bot_token}"

    def reload_token(self):
        """Reload bot token from database Integration table."""
        from core.database import SessionLocal
        from models import Integration
        from sqlalchemy import select
        with SessionLocal() as db:
            result = db.execute(
                select(Integration.config).where(Integration.channel == "telegram")
            )
            row = result.scalar_one_or_none()
            self.bot_token = row.get("token", "") if row else ""
            self.api_base = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(self, chat_id: str, text: str) -> dict:
        """Send a message to a Telegram chat."""
        self.reload_token()
        url = f"{self.api_base}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            logger.info(f"Telegram message sent: chat_id={chat_id}, text_len={len(text)}")
            return response.json()

    async def send_test_message(self, chat_id: Optional[str] = None) -> dict:
        """Send a test message to verify the bot is working."""
        self.reload_token()
        test_message = "✅ *KMS Bot Connected*\n\nYour Telegram integration is working correctly!"
        logger.info(f"Telegram test message sent: chat_id={chat_id}")
        return await self.send_message(chat_id or "test", test_message)

    async def set_webhook(self, webhook_url: str) -> dict:
        """Set the webhook URL for incoming updates."""
        self.reload_token()
        url = f"{self.api_base}/setWebhook"
        payload = {"url": webhook_url}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            logger.info(f"Telegram webhook set: url={webhook_url}")
            return response.json()

    async def delete_webhook(self) -> dict:
        """Delete the current webhook."""
        self.reload_token()
        url = f"{self.api_base}/deleteWebhook"

        async with httpx.AsyncClient() as client:
            response = await client.post(url)
            logger.info("Telegram webhook deleted")
            return response.json()

    async def get_me(self) -> dict:
        """Get bot information."""
        self.reload_token()
        url = f"{self.api_base}/getMe"

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            return response.json()

    async def start_polling(self):
        """Start long polling for updates."""
        self._polling_offset = 0
        self._polling_active = True
        logger.info("Telegram polling started")
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            while self._polling_active:
                try:
                    self.reload_token()
                    if not self.bot_token:
                        await asyncio.sleep(60)
                        continue
                    response = await client.get(
                        f"{self.api_base}/getUpdates",
                        params={"offset": self._polling_offset, "timeout": 30}
                    )
                    response.raise_for_status()
                    data = response.json()
                    if data.get("ok"):
                        updates = data.get("result", [])
                        for update in updates:
                            await self._process_update(update)
                except httpx.HTTPError as e:
                    logger.error(f"Telegram polling HTTP error: {e}")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Telegram polling error: {e}")
                    await asyncio.sleep(1)

    async def _process_update(self, update: dict):
        """Process a single update."""
        self._polling_offset = update["update_id"] + 1
        message = update.get("message", {})
        if not message or not message.get("text"):
            return

        chat_id = str(message["chat"]["id"])
        text = message["text"]
        logger.info(f"Telegram polling: chat_id={chat_id}, text='{text[:50]}...'")

        try:
            from core.orchestrator import process_query
            result = await process_query(
                query_text=text,
                source="telegram",
                chat_id=chat_id
            )
            response_text = result.get("response", "")
            if response_text:
                await self.send_message(chat_id, response_text)
            logger.info(f"Telegram polling: processed chat_id={chat_id}")
        except Exception as e:
            logger.error(f"Telegram polling: failed to process chat_id={chat_id}: {e}")

    def stop_polling(self):
        """Stop the polling loop."""
        self._polling_active = False
        logger.info("Telegram polling stopped")


# Global shared instance
_telegram_service: Optional["TelegramService"] = None


def get_telegram_service() -> "TelegramService":
    """Get the global TelegramService instance."""
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramService(bot_token="")
    return _telegram_service