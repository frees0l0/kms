"""
Discord service for bot integration using discord.py.
"""

import logging
import re
from typing import Optional

import discord

from core.config import settings

logger = logging.getLogger("kms.discord")


class DiscordService(discord.Client):
    """Discord bot client."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

    async def _start(self):
        if not settings.discord_bot_token:
            logger.warning("Discord bot token not configured")
            return
        try:
            await super().start(settings.discord_bot_token)
            logger.info("Discord bot started")
        except Exception as e:
            logger.error(f"Discord bot start failed: {e}")

    async def on_message(self, message: discord.Message):
        """Handle text messages."""
        logger.info(f"Discord message from {message.author}: '{message.content[:50]}...'")

        if message.author == self.user:
            logger.info("Discord message ignored (from ourselves)")
            return

        # Only respond if the bot is mentioned and it's the only mention
        if len(message.mentions) > 1:
            logger.info("Discord message ignored (multiple mentions)")
            return
        if self.user not in message.mentions:
            logger.info("Discord message ignored (bot not mentioned)")
            return

        # Strip bot mention prefix (e.g. "<@1490596279623880744> ")
        content = message.content
        if self.user:
            content = re.sub(rf"^<@{self.user.id}>\s*", "", content)

        try:
            if content.startswith('/hello'):
                await message.channel.send('Hello!')
                return

            from core.orchestrator import process_query
            result = await process_query(
                query_text=content,
                source="discord",
                chat_id=str(message.author.id)
            )
            response_text = result.get("response", "")
            if response_text:
                await message.channel.send(response_text)
        except Exception as e:
            logger.error(f"Discord message error: {e}")

    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Discord bot logged in as {self.user}")

    async def on_error(self, event: str, *args, **kwargs):
        """Called when an exception is raised in an event handler."""
        logger.error(f"Discord {event} error: {args}, {kwargs}")


# Global instance
_discord_service: Optional[DiscordService] = None


def get_discord_service() -> DiscordService:
    """Get the global DiscordService instance."""
    global _discord_service
    if _discord_service is None:
        _discord_service = DiscordService()
    return _discord_service
