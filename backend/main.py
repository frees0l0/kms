"""
IntelliKnow KMS - FastAPI Backend
AI-powered knowledge management system
"""

import asyncio
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from core.database import engine, Base, SessionLocal
from core.document_store import DocumentStore
from utils.logging import setup_logging, log_error
from api.v1 import auth, bot, admin, analytics
from services.telegram import get_telegram_service

# Setup logging
logger = setup_logging()


def _create_default_intent_spaces():
    """Create default intent spaces if they don't exist."""
    from models import IntentSpace
    from sqlalchemy import select
    default_intents = [
        {"name": "General", "description": "General knowledge and common questions", "keywords": "general,help,info"},
        {"name": "HR", "description": "Human resources, policies, benefits, and employee matters", "keywords": "hr,human resources,employee,benefits,policy,leave,vacation"},
        {"name": "Legal", "description": "Legal matters, contracts, compliance, and regulations", "keywords": "legal,law,contract,compliance,regulation,agreement"},
        {"name": "Finance", "description": "Financial matters, budgets, expenses, and accounting", "keywords": "finance,budget,expense,cost,accounting,payment,invoice"},
    ]
    with SessionLocal() as db:
        for intent_data in default_intents:
            result = db.execute(select(IntentSpace).where(IntentSpace.name == intent_data["name"]))
            if not result.scalar_one_or_none():
                db.add(IntentSpace(**intent_data))
                logger.info(f"Created default intent space: {intent_data['name']}")
        db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize database on startup."""
    # Create database tables
    with engine.begin() as conn:
        Base.metadata.create_all(conn)

    # Initialize document store (create FTS tables if needed)
    try:
        doc_store = DocumentStore()
        doc_store.initialize()
    except Exception as e:
        log_error(f"Failed to initialize document store: {e}")

    # Create default intent spaces if they don't exist
    _create_default_intent_spaces()

    # Start Telegram polling
    telegram = get_telegram_service()
    polling_task = asyncio.create_task(telegram.start_polling())
    logger.info("Telegram polling started")

    yield

    # Shutdown Telegram polling
    telegram.stop_polling()
    await polling_task
    logger.info("Telegram polling stopped")


app = FastAPI(
    title="IntelliKnow KMS",
    description="AI-powered knowledge management system",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(bot.router, prefix="/api/v1/bot", tags=["bot"])
app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])


# Global exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    error_id = id(exc)
    stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    logger.error(
        f"Unhandled exception: {exc}\n"
        f"Request: {request.method} {request.url.path}\n"
        f"Error ID: {error_id}\n"
        f"Traceback:\n{stack_trace}"
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "error_id": error_id
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with logging."""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail} - {request.method} {request.url.path}")

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.get("/")
async def root():
    return {"message": "IntelliKnow KMS API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
