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
    business_name: str = Field(..., min_length=2, max_length=100)
    business_description: str = Field(..., min_length=10, max_length=2000)
    tone: str = Field(default="friendly")  # friendly | formal | sales
    faqs: Optional[List[FAQItem]] = []


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    tone: Optional[str] = None
    faqs: Optional[List[FAQItem]] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    business_name: str
    business_description: str
    tone: str
    faqs: List[FAQItem]
    api_key: str
    is_active: bool
    created_at: datetime


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
