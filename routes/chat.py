from fastapi import APIRouter, HTTPException, Depends, Header, status
from datetime import date
from bson import ObjectId
from typing import Optional

from db.mongo import get_db
from core.security import get_current_user
from core.groq import chat_with_groq
from models.schemas import InternalChatRequest, WidgetChatRequest, ChatResponse

router = APIRouter()

PLAN_DAILY_LIMITS = {
    "free": 50,
    "starter": 1000,
    "pro": 10000,
    "enterprise": 999999,
}


async def check_and_increment_usage(db, user: dict) -> dict:
    """
    Resets daily counter if it's a new day.
    Raises 429 if daily limit exceeded.
    Returns updated user doc.
    """
    today = str(date.today())
    user_id = user["_id"]

    # Reset daily usage if it's a new day
    if user.get("usage_reset_date") != today:
        await db.users.update_one(
            {"_id": user_id},
            {"$set": {"messages_used": 0, "usage_reset_date": today}},
        )
        user["messages_used"] = 0
        user["usage_reset_date"] = today

    plan = user.get("plan", "free")
    daily_limit = PLAN_DAILY_LIMITS.get(plan, 50)
    messages_used = user.get("messages_used", 0)

    if messages_used >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Daily limit reached",
                "messages_used": messages_used,
                "messages_limit": daily_limit,
                "upgrade_url": "/pricing",
            },
        )

    # Increment counter
    await db.users.update_one(
        {"_id": user_id},
        {"$inc": {"messages_used": 1}},
    )

    return {
        "messages_used": messages_used + 1,
        "messages_limit": daily_limit,
    }


# ── Internal: user tests their own bot inside BotForge app ───────────────────

@router.post("/test/{bot_id}", response_model=ChatResponse)
async def test_bot(
    bot_id: str,
    body: InternalChatRequest,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()

    agent = await db.agents.find_one({
        "_id": ObjectId(bot_id),
        "owner_id": current_user["_id"],
    })
    if not agent:
        raise HTTPException(status_code=404, detail="Bot not found")

    if not agent.get("is_active"):
        raise HTTPException(status_code=403, detail="This bot is inactive")

    usage = await check_and_increment_usage(db, current_user)

    session_history = [m.model_dump() for m in body.session_history]
    reply = await chat_with_groq(agent, session_history, body.message)

    # Log to chat_logs
    await db.chat_logs.insert_one({
        "bot_id": agent["_id"],
        "owner_id": current_user["_id"],
        "source": "internal",
        "user_message": body.message,
        "bot_response": reply,
    })

    return ChatResponse(reply=reply, **usage)


# ── External: client's website hits this endpoint using API key ───────────────

@router.post("/widget", response_model=ChatResponse)
async def widget_chat(
    body: WidgetChatRequest,
    x_api_key: Optional[str] = Header(None),
):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required. Pass X-Api-Key header.")

    db = get_db()

    # Find agent by API key
    agent = await db.agents.find_one({"api_key": x_api_key})
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not agent.get("is_active"):
        raise HTTPException(status_code=403, detail="This bot is inactive")

    # Find the owner to check usage limits
    owner = await db.users.find_one({"_id": agent["owner_id"]})
    if not owner:
        raise HTTPException(status_code=404, detail="Bot owner not found")

    usage = await check_and_increment_usage(db, owner)

    session_history = [m.model_dump() for m in body.session_history]
    reply = await chat_with_groq(agent, session_history, body.message)

    # Log to chat_logs
    await db.chat_logs.insert_one({
        "bot_id": agent["_id"],
        "owner_id": owner["_id"],
        "source": "widget",
        "user_message": body.message,
        "bot_response": reply,
    })

    return ChatResponse(reply=reply, **usage)
