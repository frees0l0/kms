#pylint: disable=global-statement,invalid-name
"""
Bot message endpoints - Telegram/Teams message handling with RAG.
"""

import asyncio
import logging
from fastapi import APIRouter, status

from core.orchestrator import process_query
from schemas import BotMessageRequest, BotMessageResponse

logger = logging.getLogger("kms.bot")

router = APIRouter()


@router.post("/message", response_model=BotMessageResponse)
async def handle_bot_message(
    request: BotMessageRequest
):
    """
    Receive message from Telegram/Teams, classify intent,
    retrieve relevant documents, and generate response.
    """
    logger.info(f"Received message from {request.source}, chat_id={request.chat_id}")
    try:
        result = await process_query(
            query_text=request.text,
            source=request.source,
            chat_id=request.chat_id
        )
        logger.info(f"Message processed successfully for chat_id={request.chat_id}")
        return BotMessageResponse(status="success", response=result["response"])
    except Exception as e:
        logger.error(f"Failed to process message for chat_id={request.chat_id}: {e}")
        raise


@router.post("/teams/webhook", status_code=status.HTTP_202_ACCEPTED)
async def teams_webhook(request: dict):
    """
    Teams-specific webhook endpoint.
    Teams expects immediate acknowledgment (202 Accepted) within 3 seconds.
    The actual response is sent proactively via Teams API.
    """
    from services.teams import get_teams_service

    activity_type = request.get("type", "")
    if activity_type != "message":
        return {"status": "accepted"}

    conversation_id = request.get("conversation", {}).get("id")
    message_text = request.get("text", "")
    service_url = request.get("serviceUrl")
    user_name = request.get("from", {}).get("name", "User")

    if not conversation_id or not message_text:
        return {"status": "accepted"}

    logger.info(f"Teams webhook: conversation_id={conversation_id}, user={user_name}, text='{message_text[:50]}...'")

    async def process_and_reply():
        try:
            teams = get_teams_service()

            result = await process_query(
                query_text=message_text,
                source="teams",
                chat_id=conversation_id
            )
            response_text = result.get("response", "")
            if response_text and service_url:
                await teams.send_message(conversation_id, response_text, service_url=service_url)
                logger.info(f"Teams webhook: response sent to conversation_id={conversation_id}")
        except Exception as e:
            logger.error(f"Teams webhook: failed to process conversation_id={conversation_id}: {e}")

    asyncio.create_task(process_and_reply())

    return {"status": "accepted"}
