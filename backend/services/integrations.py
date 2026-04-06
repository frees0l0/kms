"""
Integration aggregation service.
Returns integration status from settings (config hints) and real-time active states.
"""

import logging
from typing import List

from core.config import settings
from models import Integration

logger = logging.getLogger("kms.integrations")


def _check_telegram_active() -> bool:
    """Check real-time Telegram active state."""
    if not settings.telegram_bot_token:
        return False
    try:
        from services.telegram import get_telegram_service
        telegram = get_telegram_service()
        return telegram.is_active()
    except Exception as e:
        logger.warning(f"Telegram active state check failed: {e}")
        return False


def _check_discord_active() -> bool:
    """Check real-time Discord active state."""
    if not settings.discord_bot_token:
        return False
    try:
        from services.discord import get_discord_service
        discord_bot = get_discord_service()
        return discord_bot.is_ready()
    except Exception as e:
        logger.warning(f"Discord active state check failed: {e}")
        return False


async def _check_teams_active() -> bool:
    """Check real-time Teams active state."""
    if not settings.teams_app_id or not settings.teams_app_secret:
        return False
    try:
        from services.teams import get_teams_service
        teams = get_teams_service()
        # Need better way to check Teams integration status
        return await teams.verify_credentials()
    except Exception as e:
        logger.warning(f"Teams active state check failed: {e}")
        return False


async def get_all_integrations() -> List[Integration]:
    """
    Get all integrations with config hints from settings and real-time active states.
    Returns list of Integration model instances (not persisted).
    """
    integrations = []

    # Telegram
    telegram_config = {"hint": "not configured"}
    if settings.telegram_bot_token:
        telegram_config = {"hint": f"token ends with ...{settings.telegram_bot_token[-4:]}"}
    integrations.append(Integration(
        channel="telegram",
        config=telegram_config,
        is_active=_check_telegram_active()
    ))

    # Discord
    discord_config = {"hint": "not configured"}
    if settings.discord_bot_token:
        discord_config = {"hint": f"token ends with ...{settings.discord_bot_token[-4:]}"}
    integrations.append(Integration(
        channel="discord",
        config=discord_config,
        is_active=_check_discord_active()
    ))

    # Teams
    # teams_config = {"hint": "not configured"}
    # if settings.teams_app_id:
    #     teams_config = {"hint": f"app_id: {settings.teams_app_id[:8]}..."}
    # integrations.append(Integration(
    #     channel="teams",
    #     config=teams_config,
    #     is_active=await _check_teams_active()
    # ))

    return integrations