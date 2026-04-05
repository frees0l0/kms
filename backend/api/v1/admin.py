# pylint: disable=not-callable
"""
Admin endpoints - KB management, Intent spaces, Integrations.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload

from core.database import get_db, SessionLocal
from core.document_store import DocumentStore
from core.document_parser import DocumentParser
from models import Document, IntentSpace, Integration, QueryLog
from schemas import (
    DocumentResponse, DocumentListResponse, IntentSpaceResponse, IntentSpaceListResponse,
    IntentSpaceCreate, IntentSpaceUpdate, IntegrationResponse, IntegrationListResponse,
    TelegramConfig, TeamsConfig, MessageResponse, QueryLogListResponse, QueryLogResponse,
    TestResponse)
from api.v1.auth import get_current_user
from services.telegram import get_telegram_service
from services.teams import get_teams_service

logger = logging.getLogger("kms.admin")

router = APIRouter()

# Upload directory
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ============ Knowledge Base Endpoints ============

@router.post("/kb/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    intent_space_id: Optional[int] = Query(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Upload a document (PDF or DOCX) for processing."""
    # Validate file format
    allowed_formats = ["pdf", "docx"]
    file_format = file.filename.split(".")[-1].lower() if "." in file.filename else "" # type: ignore

    if file_format not in allowed_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Allowed: {', '.join(allowed_formats)}"
        )

    # Read file content
    content = await file.read()
    size_bytes = len(content)

    # Save file
    file_path = UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    with open(file_path, "wb") as f:
        f.write(content)

    # Get intent space name if provided
    intent_space_name = None
    if intent_space_id:
        result = db.execute(select(IntentSpace).where(IntentSpace.id == intent_space_id))
        intent_space = result.scalar_one_or_none()
        if intent_space:
            intent_space_name = intent_space.name

    # Create document record
    document = Document(
        name=file.filename,
        format=file_format,
        size_bytes=size_bytes,
        status="pending",
        intent_space_id=intent_space_id
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Schedule background processing
    background_tasks.add_task(process_document_background, document.id, str(file_path))
    logger.info(f"Document uploaded: name={document.name}, size={size_bytes}, intent_space_id={intent_space_id}")

    return DocumentResponse(
        id=document.id,
        name=document.name,
        format=document.format,
        size_bytes=document.size_bytes,
        upload_time=document.upload_time,
        status=document.status,
        intent_space_id=document.intent_space_id,
        intent_space_name=intent_space_name
    )


def process_document_background(document_id: int, file_path: str):
    """Background task to process uploaded document."""
    with SessionLocal() as db:
        try:
            # Parse document (sync - runs in threadpool via FastAPI background_tasks)
            parser = DocumentParser()
            chunks_data = parser.parse(file_path)

            # Delete existing chunks and store new ones
            doc_store = DocumentStore()
            doc_store.delete_document(document_id)
            asyncio.run(doc_store.store_document(document_id, chunks_data))

            # Update document status
            db.execute(
                update(Document).where(Document.id == document_id).values(status="processed")
            )
            db.commit()

        except Exception as e:
            logger.error(f"Document processing failed: document_id={document_id}, error={e}")
            db.execute(
                update(Document).where(Document.id == document_id).values(
                    status="error",
                    error_message=str(e)
                )
            )
            db.commit()

        else:
            logger.info(f"Document processed successfully: document_id={document_id}")

        finally:
            # Note: We intentionally don't delete the original file here
            # because reparse needs it. The file is kept in UPLOAD_DIR.
            pass


@router.get("/kb/documents", response_model=DocumentListResponse)
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    intent_space_id: Optional[int] = Query(None),
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """List all documents with pagination and filtering."""
    query = select(Document).options(selectinload(Document.intent_space))

    # Apply filters
    if search:
        query = query.where(Document.name.contains(search))
    if status_filter:
        query = query.where(Document.status == status_filter)
    if intent_space_id:
        query = query.where(Document.intent_space_id == intent_space_id)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Document.upload_time.desc())

    result = db.execute(query)
    documents = result.scalars().all()

    items = [
        DocumentResponse(
            id=doc.id,
            name=doc.name,
            format=doc.format,
            size_bytes=doc.size_bytes,
            upload_time=doc.upload_time,
            status=doc.status,
            intent_space_id=doc.intent_space_id,
            intent_space_name=doc.intent_space.name if doc.intent_space else None,
            error_message=doc.error_message
        )
        for doc in documents
    ]

    return DocumentListResponse(total=total, page=page, page_size=page_size, items=items)


@router.delete("/kb/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Delete a document and its associated vectors."""
    # Get document
    result = db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Delete chunks and vectors
    doc_store = DocumentStore()
    doc_store.delete_document(document_id)

    # Delete document record
    db.delete(document)
    db.commit()
    logger.info(f"Document deleted: document_id={document_id}")


@router.post("/kb/documents/{document_id}/reparse", response_model=MessageResponse)
def reparse_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Re-parse a document."""
    result = db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Find the original file in uploads (if still exists)
    file_path = None
    for f in UPLOAD_DIR.glob(f"*_{document.name}"):
        file_path = str(f)
        break

    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Original file not found. Please re-upload the document."
        )

    # Update status and schedule reprocessing
    db.execute(
        update(Document).where(Document.id == document_id).values(status="pending")
    )
    db.commit()

    background_tasks.add_task(process_document_background, document_id, file_path)
    logger.info(f"Document reparse started: document_id={document_id}")

    return MessageResponse(status="reparse started")


@router.put("/kb/documents/{document_id}/intent", response_model=DocumentResponse)
def update_document_intent(
    document_id: int,
    intent_space_id: Optional[int] = None,
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Update document's intent space association."""
    result = db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Validate intent space exists
    intent_space_name = None
    if intent_space_id:
        result = db.execute(select(IntentSpace).where(IntentSpace.id == intent_space_id))
        intent_space = result.scalar_one_or_none()
        if not intent_space:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Intent space not found")
        intent_space_name = intent_space.name

    # Update
    db.execute(
        update(Document).where(Document.id == document_id).values(intent_space_id=intent_space_id)
    )
    db.commit()

    document.intent_space_id = intent_space_id
    logger.info(f"Document intent updated: document_id={document_id}, intent_space_id={intent_space_id}, intent_space_name={intent_space_name}")
    return DocumentResponse(
        id=document.id,
        name=document.name,
        format=document.format,
        size_bytes=document.size_bytes,
        upload_time=document.upload_time,
        status=document.status,
        intent_space_id=document.intent_space_id,
        intent_space_name=intent_space_name
    )


# ============ Intent Space Endpoints ============

@router.get("/intents", response_model=IntentSpaceListResponse)
def list_intents(
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """List all intent spaces."""
    result = db.execute(select(IntentSpace))
    intents = result.scalars().all()

    items = []
    for intent in intents:
        # Get document count
        doc_count_result = db.execute(
            select(func.count()).where(Document.intent_space_id == intent.id)
        )
        doc_count = doc_count_result.scalar() or 0

        # Calculate accuracy from query logs
        accuracy_result = db.execute(
            select(func.avg(QueryLog.confidence))
            .where(QueryLog.intent_id == intent.id)
            .where(QueryLog.user_feedback == "correct")
        )
        accuracy = accuracy_result.scalar()

        items.append(IntentSpaceResponse(
            id=intent.id,
            name=intent.name,
            description=intent.description,
            keywords=intent.keywords,
            document_count=doc_count,
            accuracy=accuracy
        ))

    return IntentSpaceListResponse(data=items)


@router.post("/intents", response_model=IntentSpaceResponse, status_code=status.HTTP_201_CREATED)
def create_intent(
    intent: IntentSpaceCreate,
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Create a new intent space."""
    # Check if name already exists
    result = db.execute(select(IntentSpace).where(IntentSpace.name == intent.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Intent space already exists")

    new_intent = IntentSpace(
        name=intent.name,
        description=intent.description,
        keywords=intent.keywords
    )
    db.add(new_intent)
    db.commit()
    db.refresh(new_intent)
    logger.info(f"Intent space created: name={new_intent.name}, id={new_intent.id}")

    return IntentSpaceResponse(
        id=new_intent.id,
        name=new_intent.name,
        description=new_intent.description,
        keywords=new_intent.keywords,
        document_count=0
    )


@router.put("/intents/{intent_id}", response_model=IntentSpaceResponse)
def update_intent(
    intent_id: int,
    intent_update: IntentSpaceUpdate,
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Update an intent space."""
    result = db.execute(select(IntentSpace).where(IntentSpace.id == intent_id))
    intent = result.scalar_one_or_none()

    if not intent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intent space not found")

    # Update fields
    if intent_update.name is not None:
        intent.name = intent_update.name
    if intent_update.description is not None:
        intent.description = intent_update.description
    if intent_update.keywords is not None:
        intent.keywords = intent_update.keywords

    db.commit()

    # Get updated counts
    doc_count_result = db.execute(
        select(func.count()).where(Document.intent_space_id == intent.id)
    )
    doc_count = doc_count_result.scalar() or 0
    logger.info(f"Intent space updated: name={intent.name}, id={intent.id}")

    return IntentSpaceResponse(
        id=intent.id,
        name=intent.name,
        description=intent.description,
        keywords=intent.keywords,
        document_count=doc_count
    )


@router.delete("/intents/{intent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_intent(
    intent_id: int,
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Delete an intent space."""
    result = db.execute(select(IntentSpace).where(IntentSpace.id == intent_id))
    intent = result.scalar_one_or_none()

    if not intent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intent space not found")

    # Remove intent association from documents
    db.execute(
        update(Document).where(Document.intent_space_id == intent_id).values(intent_space_id=None)
    )

    db.delete(intent)
    db.commit()
    logger.info(f"Intent space deleted: id={intent_id}")


@router.get("/intents/{intent_id}/queries")
def get_intent_queries(
    intent_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Get query logs for a specific intent space."""
    # Verify intent exists
    result = db.execute(select(IntentSpace).where(IntentSpace.id == intent_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intent space not found")

    query = select(QueryLog).where(QueryLog.intent_id == intent_id)

    # Count total
    count_result = db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(QueryLog.timestamp.desc())

    result = db.execute(query)
    logs = result.scalars().all()

    items = [
        QueryLogResponse(
            id=log.id,
            timestamp=log.timestamp,
            source=log.source,
            user_id=log.user_id,
            query_text=log.query_text,
            intent=log.intent_space.name if log.intent_space else None,
            intent_id=log.intent_id,
            confidence=log.confidence,
            response_time_ms=log.response_time_ms,
            user_feedback=log.user_feedback
        )
        for log in logs
    ]

    return QueryLogListResponse(total=total, page=page, page_size=page_size, items=items)


# ============ Integration Endpoints ============

@router.get("/integrations", response_model=IntegrationListResponse)
def list_integrations(
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Get all integration configurations."""
    result = db.execute(select(Integration))
    integrations = result.scalars().all()

    items = []
    for integration in integrations:
        # Create config hint
        config = integration.config or {}
        if integration.channel == "telegram":
            token = config.get("token", "")
            hint = f"token ends with ...{token[-4:]}" if token else "not configured"
        elif integration.channel == "teams":
            app_id = config.get("app_id", "")
            hint = f"app_id: {app_id[:8]}..." if app_id else "not configured"
        else:
            hint = "unknown"

        items.append(IntegrationResponse(
            channel=integration.channel,
            is_active=integration.is_active,
            last_test_at=integration.last_test_at,
            config_hint=hint
        ))

    return IntegrationListResponse(data=items)


@router.post("/integrations/telegram", response_model=IntegrationResponse)
async def configure_telegram(
    config: TelegramConfig,
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Configure Telegram bot token."""
    result = db.execute(select(Integration).where(Integration.channel == "telegram"))
    integration = result.scalar_one_or_none()

    if integration:
        integration.config = {"token": config.token}
        integration.is_active = False  # Reset until test passes
    else:
        integration = Integration(
            channel="telegram",
            config={"token": config.token},
            is_active=False  # Will be set to True after successful test
        )
        db.add(integration)

    db.commit()
    logger.info(f"Telegram integration configured: token_hint=...{config.token[-4:]}")

    return IntegrationResponse(
        channel="telegram",
        is_active=False,
        config_hint=f"token ends with ...{config.token[-4:]}"
    )


@router.post("/integrations/teams", response_model=IntegrationResponse)
async def configure_teams(
    config: TeamsConfig,
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Configure Teams app credentials."""
    result = db.execute(select(Integration).where(Integration.channel == "teams"))
    integration = result.scalar_one_or_none()

    config_data = {
        "app_id": config.app_id,
        "app_secret": config.app_secret,
        "tenant_id": config.tenant_id
    }

    if integration:
        integration.config = config_data
        integration.is_active = False  # Reset until test passes
    else:
        integration = Integration(
            channel="teams",
            config=config_data,
            is_active=False  # Will be set to True after successful test
        )
        db.add(integration)

    db.commit()
    logger.info(f"Teams integration configured: app_id={config.app_id[:8]}...")

    return IntegrationResponse(
        channel="teams",
        is_active=False,
        config_hint=f"app_id: {config.app_id[:8]}..."
    )


@router.post("/integrations/{channel}/test", response_model=TestResponse)
async def test_integration(
    channel: str,
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Test an integration by verifying credentials and connectivity."""
    if channel not in ("telegram", "teams"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid channel")

    result = db.execute(select(Integration).where(Integration.channel == channel))
    integration = result.scalar_one_or_none()

    if not integration or not integration.config:
        return TestResponse(status="error", message="Integration not configured")

    try:
        if channel == "telegram":
            # Test Telegram bot - verify token by getting bot info
            telegram = get_telegram_service()
            await telegram.get_me()
            integration.is_active = True
        elif channel == "teams":
            # Test Teams - verify credentials by obtaining access token
            teams = get_teams_service()
            is_valid = await teams.verify_credentials()
            if not is_valid:
                return TestResponse(status="error", message="Failed to authenticate with Teams")
            integration.is_active = True

        # Update last_test_at on success
        integration.last_test_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Integration test passed: channel={channel}")

        return TestResponse(status="success", message="Integration test passed successfully")

    except Exception as e:
        # Mark as inactive on failure
        integration.is_active = False
        db.commit()
        logger.error(f"Integration test failed: channel={channel}, error={e}")
        return TestResponse(status="error", message=f"Test failed: {str(e)}")
