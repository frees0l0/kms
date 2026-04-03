"""
Pydantic schemas for request/response validation.
"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


# ============ Auth Schemas ============

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ============ Document Schemas ============

class DocumentBase(BaseModel):
    name: str
    format: str
    size_bytes: int


class DocumentCreate(DocumentBase):
    intent_space_id: Optional[int] = None


class DocumentResponse(DocumentBase):
    id: int
    upload_time: datetime
    status: str
    intent_space_id: Optional[int] = None
    intent_space_name: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[DocumentResponse]


# ============ Intent Space Schemas ============

class IntentSpaceBase(BaseModel):
    name: str
    description: Optional[str] = None
    keywords: Optional[str] = None


class IntentSpaceCreate(IntentSpaceBase):
    pass


class IntentSpaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None


class IntentSpaceResponse(IntentSpaceBase):
    id: int
    document_count: int = 0
    accuracy: Optional[float] = None

    class Config:
        from_attributes = True


class IntentSpaceListResponse(BaseModel):
    data: List[IntentSpaceResponse]


# ============ Integration Schemas ============

class TelegramConfig(BaseModel):
    token: str


class TeamsConfig(BaseModel):
    app_id: str
    app_secret: str
    tenant_id: str = "common"


class IntegrationResponse(BaseModel):
    channel: str
    is_active: bool
    last_test_at: Optional[datetime] = None
    config_hint: str


class IntegrationListResponse(BaseModel):
    data: List[IntegrationResponse]


class TestRequest(BaseModel):
    test_message: str = "Hello from KMS"


class TestResponse(BaseModel):
    status: str
    message: str


# ============ Bot Schemas ============

class BotMessageRequest(BaseModel):
    source: str = Field(..., description="telegram or teams")
    chat_id: str
    text: str = Field(..., max_length=2000)


class BotMessageResponse(BaseModel):
    status: str
    response: str


# ============ Analytics Schemas ============

class QueryLogResponse(BaseModel):
    id: int
    timestamp: datetime
    source: str
    user_id: str
    query_text: str
    intent: Optional[str] = None
    intent_id: Optional[int] = None
    confidence: Optional[float] = None
    response_time_ms: Optional[int] = None
    user_feedback: Optional[str] = None
    corrected_intent_id: Optional[int] = None

    class Config:
        from_attributes = True


class QueryLogListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[QueryLogResponse]


class QueryLogFeedbackRequest(BaseModel):
    feedback: str = Field(..., description="correct or wrong")
    corrected_intent_id: Optional[int] = Field(None, description="correct intent id if feedback is wrong")


class AnalyticsStats(BaseModel):
    total_queries: int
    avg_response_time_ms: Optional[float]
    avg_accuracy: Optional[float]


class IntentDistribution(BaseModel):
    intent: str
    count: int


class IntentDistributionResponse(BaseModel):
    distribution: List[IntentDistribution]


class TopDocument(BaseModel):
    id: int
    name: str
    hit_count: int
    intent_space: Optional[str] = None


class TopDocumentsResponse(BaseModel):
    documents: List[TopDocument]


class DashboardSummary(BaseModel):
    frontend_integrations: List[IntegrationResponse]
    kb_stats: dict
    intent_spaces: List[dict]
    analytics: dict


# ============ Generic Responses ============

class MessageResponse(BaseModel):
    status: str
    message: Optional[str] = None
