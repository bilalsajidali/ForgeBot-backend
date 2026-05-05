from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# ── Auth ──────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    plan: str
    messages_used: int
    messages_limit: int


# ── Agent / Bot ───────────────────────────────────────────────────────────────

class FAQItem(BaseModel):
    question: str = Field(..., min_length=3)
    answer: str = Field(..., min_length=1)


class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    bot_knowledge: str = Field(..., min_length=10, max_length=50000)
    tone: str = Field(default="friendly")  # friendly | formal | sales
    faqs: Optional[List[FAQItem]] = []


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    bot_knowledge: Optional[str] = Field(default=None, min_length=10, max_length=50000)
    tone: Optional[str] = None
    faqs: Optional[List[FAQItem]] = None


class KnowledgeDocumentSummary(BaseModel):
    filename: str
    chars: int


class AgentResponse(BaseModel):
    id: str
    name: str
    bot_knowledge: str
    tone: str
    faqs: List[FAQItem]
    api_key: str
    is_active: bool
    created_at: datetime
    documents: List[KnowledgeDocumentSummary] = []


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class InternalChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_history: Optional[List[ChatMessage]] = []


class WidgetChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_history: Optional[List[ChatMessage]] = []


class ChatResponse(BaseModel):
    reply: str
    messages_used: int
    messages_limit: int
