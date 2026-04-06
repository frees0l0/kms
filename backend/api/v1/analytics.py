# pylint: disable=not-callable
"""
Analytics endpoints - Query logs, statistics, export.
"""

import csv
import io
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from core.database import get_db
from models import QueryLog, Document, IntentSpace
from schemas import (
    QueryLogListResponse, QueryLogResponse, AnalyticsStats,
    IntentDistributionResponse, IntentDistribution, TopDocumentsResponse,
    TopDocument, DashboardSummary, IntegrationResponse, QueryLogFeedbackRequest
)
from api.v1.auth import get_current_user

logger = logging.getLogger("kms.analytics")

router = APIRouter()


@router.get("/queries", response_model=QueryLogListResponse)
def list_queries(
    search: Optional[str] = Query(None, description="Search by user_id or query_text"),
    intent_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """List query history with pagination and filtering."""
    query = select(QueryLog).options(selectinload(QueryLog.intent_space))

    # Apply filters
    if search:
        query = query.where(
            (QueryLog.user_id.contains(search)) | (QueryLog.query_text.contains(search))
        )
    if intent_id:
        query = query.where(QueryLog.intent_id == intent_id)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate and order
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
            user_feedback=log.user_feedback,
            corrected_intent_id=log.corrected_intent_id
        )
        for log in logs
    ]

    return QueryLogListResponse(total=total, page=page, page_size=page_size, items=items)


@router.patch("/queries/{query_id}/feedback")
def update_query_feedback(
    query_id: int,
    feedback: QueryLogFeedbackRequest,
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Update feedback for a query log entry."""
    result = db.execute(select(QueryLog).where(QueryLog.id == query_id))
    query_log = result.scalar_one_or_none()

    if not query_log:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Query log not found")

    query_log.user_feedback = feedback.feedback
    if feedback.corrected_intent_id is not None:
        query_log.corrected_intent_id = feedback.corrected_intent_id

    db.commit()
    return {"status": "ok"}


@router.get("/stats", response_model=AnalyticsStats)
def get_stats(
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Get aggregate statistics."""
    # Total queries
    total_result = db.execute(select(func.count()).select_from(QueryLog))
    total_queries = total_result.scalar() or 0

    # Average response time
    avg_time_result = db.execute(
        select(func.avg(QueryLog.response_time_ms)).where(QueryLog.response_time_ms.isnot(None))
    )
    avg_response_time = avg_time_result.scalar() or 0.0

    # Classification accuracy = correct / (correct + wrong)
    correct_count_result = db.execute(
        select(func.count()).select_from(QueryLog)
        .where(QueryLog.user_feedback == "correct")
    )
    correct_count = correct_count_result.scalar() or 0

    wrong_count_result = db.execute(
        select(func.count()).select_from(QueryLog)
        .where(QueryLog.user_feedback == "wrong")
    )
    wrong_count = wrong_count_result.scalar() or 0

    total_with_feedback = correct_count + wrong_count
    avg_accuracy = (correct_count / total_with_feedback) if total_with_feedback > 0 else None

    return AnalyticsStats(
        total_queries=total_queries,
        avg_response_time_ms=float(avg_response_time),
        avg_accuracy=avg_accuracy
    )


@router.get("/intent-distribution", response_model=IntentDistributionResponse)
def get_intent_distribution(
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Get query distribution across intent spaces."""
    query = (
        select(IntentSpace.name, func.count(QueryLog.id).label("count"))
        .outerjoin(QueryLog, IntentSpace.id == QueryLog.intent_id)
        .group_by(IntentSpace.id, IntentSpace.name)
    )

    result = db.execute(query)
    rows = result.all()

    distribution = [
        IntentDistribution(intent=row.name, count=row.count) # type: ignore
        for row in rows
    ]

    return IntentDistributionResponse(distribution=distribution)


@router.get("/top-documents", response_model=TopDocumentsResponse)
def get_top_documents(
    limit: int = Query(10, ge=1, le=50),
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Get top documents by retrieval frequency."""
    query = (
        select(Document, func.count(QueryLog.id).label("hit_count"))
        .outerjoin(QueryLog, Document.id == QueryLog.document_id)
        .group_by(Document.id)
        .order_by(func.count(QueryLog.id).desc())
        .limit(limit)
    )

    result = db.execute(query)
    rows = result.all()

    documents = []
    for doc, hit_count in rows:
        intent_space_name = doc.intent_space.name if doc.intent_space else None
        documents.append(TopDocument(
            id=doc.id,
            name=doc.name,
            hit_count=hit_count,
            intent_space=intent_space_name
        ))

    return TopDocumentsResponse(documents=documents)


@router.get("/export")
def export_queries(
    search: Optional[str] = Query(None),
    intent_id: Optional[int] = Query(None),
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Export query logs as CSV."""
    query = select(QueryLog).options(selectinload(QueryLog.intent_space))

    # Apply filters
    if search:
        query = query.where(
            (QueryLog.user_id.contains(search)) | (QueryLog.query_text.contains(search))
        )
    if intent_id:
        query = query.where(QueryLog.intent_id == intent_id)

    query = query.order_by(QueryLog.timestamp.desc())

    result = db.execute(query)
    logs = result.scalars().all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "timestamp", "source", "user_id", "query_text", "intent",
        "confidence", "response_time_ms", "user_feedback"
    ])

    # Data rows
    for log in logs:
        writer.writerow([
            log.timestamp.isoformat() if log.timestamp else "",
            log.source,
            log.user_id,
            log.query_text,
            log.intent_space.name if log.intent_space else "",
            f"{log.confidence:.2f}" if log.confidence else "",
            log.response_time_ms or "",
            log.user_feedback or ""
        ])

    output.seek(0)
    logger.info(f"CSV export requested: search={search}, intent_id={intent_id}, rows={len(logs)}")

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=query_logs_{datetime.now().strftime('%Y%m%d')}.csv"
        }
    )


@router.get("/dashboard-summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    db=Depends(get_db),
    _current_user: dict = Depends(get_current_user)
):
    """Get aggregated data for dashboard cards."""
    # Frontend integrations
    from services.integrations import get_all_integrations

    integrations = await get_all_integrations()
    frontend_integrations = [
        IntegrationResponse(
            channel=i.channel,
            is_active=i.is_active,
            config_hint=i.config.get("hint", "unknown") if i.config else "unknown"
        )
        for i in integrations
    ]

    # KB stats
    total_docs_result = db.execute(select(func.count()).select_from(Document))
    total_documents = total_docs_result.scalar() or 0

    processed_result = db.execute(
        select(func.count()).where(Document.status == "processed")
    )
    processed = processed_result.scalar() or 0

    pending_result = db.execute(
        select(func.count()).where(Document.status == "pending")
    )
    pending = pending_result.scalar() or 0

    error_result = db.execute(
        select(func.count()).where(Document.status == "error")
    )
    error = error_result.scalar() or 0

    kb_stats = {
        "total_documents": total_documents,
        "processed": processed,
        "pending": pending,
        "error": error
    }

    # Intent spaces
    intents_result = db.execute(select(IntentSpace))
    intents = intents_result.scalars().all()

    intent_spaces = []
    for intent in intents:
        doc_count_result = db.execute(
            select(func.count()).where(Document.intent_space_id == intent.id)
        )
        doc_count = doc_count_result.scalar() or 0
        intent_spaces.append({
            "id": intent.id,
            "name": intent.name,
            "document_count": doc_count
        })

    # Analytics summary
    total_queries_result = db.execute(select(func.count()).select_from(QueryLog))
    total_queries = total_queries_result.scalar() or 0

    analytics = {"total_queries": total_queries}

    return DashboardSummary(
        frontend_integrations=frontend_integrations,
        kb_stats=kb_stats,
        intent_spaces=intent_spaces,
        analytics=analytics
    )
