import secrets
from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime
from bson import ObjectId

from db.mongo import get_db
from core.security import get_current_user
from models.schemas import CreateAgentRequest, UpdateAgentRequest, AgentResponse

router = APIRouter()

PLAN_BOT_LIMITS = {
    "free": 1,
    "starter": 3,
    "pro": 999,
    "enterprise": 999,
}


def generate_api_key() -> str:
    return "bf_live_" + secrets.token_hex(16)


def serialize_agent(agent: dict) -> AgentResponse:
    return AgentResponse(
        id=str(agent["_id"]),
        name=agent["name"],
        business_name=agent["business_name"],
        business_description=agent["business_description"],
        tone=agent.get("tone", "friendly"),
        faqs=agent.get("faqs", []),
        api_key=agent["api_key"],
        is_active=agent.get("is_active", True),
        created_at=agent["created_at"],
    )


@router.post("/create", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(body: CreateAgentRequest, current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = current_user["_id"]

    # Check plan bot limit
    plan = current_user.get("plan", "free")
    bot_limit = PLAN_BOT_LIMITS.get(plan, 1)
    existing_count = await db.agents.count_documents({"owner_id": user_id})

    if existing_count >= bot_limit:
        raise HTTPException(
            status_code=403,
            detail=f"Your {plan} plan allows {bot_limit} bot(s). Upgrade to create more.",
        )

    agent_doc = {
        "owner_id": user_id,
        "name": body.name,
        "business_name": body.business_name,
        "business_description": body.business_description,
        "tone": body.tone,
        "faqs": [faq.model_dump() for faq in body.faqs],
        "api_key": generate_api_key(),
        "is_active": True,
        "created_at": datetime.utcnow(),
    }

    result = await db.agents.insert_one(agent_doc)
    agent_doc["_id"] = result.inserted_id
    return serialize_agent(agent_doc)


@router.get("/list", response_model=list[AgentResponse])
async def list_agents(current_user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db.agents.find({"owner_id": current_user["_id"]})
    agents = await cursor.to_list(length=100)
    return [serialize_agent(a) for a in agents]


@router.get("/{bot_id}", response_model=AgentResponse)
async def get_agent(bot_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    agent = await db.agents.find_one({
        "_id": ObjectId(bot_id),
        "owner_id": current_user["_id"],
    })
    if not agent:
        raise HTTPException(status_code=404, detail="Bot not found")
    return serialize_agent(agent)


@router.put("/{bot_id}", response_model=AgentResponse)
async def update_agent(bot_id: str, body: UpdateAgentRequest, current_user: dict = Depends(get_current_user)):
    db = get_db()
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}

    if "faqs" in update_data:
        update_data["faqs"] = [faq if isinstance(faq, dict) else faq for faq in update_data["faqs"]]

    if not update_data:
        raise HTTPException(status_code=400, detail="Nothing to update")

    result = await db.agents.find_one_and_update(
        {"_id": ObjectId(bot_id), "owner_id": current_user["_id"]},
        {"$set": update_data},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Bot not found")
    return serialize_agent(result)


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(bot_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    result = await db.agents.delete_one({
        "_id": ObjectId(bot_id),
        "owner_id": current_user["_id"],
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Bot not found")


@router.post("/{bot_id}/regenerate-key", response_model=AgentResponse)
async def regenerate_api_key(bot_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    result = await db.agents.find_one_and_update(
        {"_id": ObjectId(bot_id), "owner_id": current_user["_id"]},
        {"$set": {"api_key": generate_api_key()}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Bot not found")
    return serialize_agent(result)
