import secrets
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Response
from datetime import datetime
from bson import ObjectId

from db.mongo import get_db
from core.security import get_current_user
from core.document_text import (
    MAX_UPLOAD_BYTES,
    MAX_FILES_PER_AGENT,
    MAX_TOTAL_STORED_CHARS,
    extract_document_text,
    safe_document_filename,
    unique_filename,
)
from models.schemas import CreateAgentRequest, UpdateAgentRequest, AgentResponse, KnowledgeDocumentSummary

router = APIRouter()

PLAN_BOT_LIMITS = {
    "free": 1,
    "starter": 3,
    "pro": 999,
    "enterprise": 999,
}


def generate_api_key() -> str:
    return "bf_live_" + secrets.token_hex(16)


def _knowledge_sources(agent: dict | None) -> list:
    if not agent:
        return []
    return list(agent.get("document_sources") or agent.get("pdf_sources") or [])


def _bot_knowledge(agent: dict) -> str:
    k = agent.get("bot_knowledge")
    if k is not None and str(k).strip():
        return str(k).strip()
    parts: list[str] = []
    if agent.get("business_name"):
        parts.append(str(agent["business_name"]).strip())
    if agent.get("business_description"):
        parts.append(str(agent["business_description"]).strip())
    return "\n\n".join(p for p in parts if p)


def _existing_filenames(rows: list) -> set[str]:
    return {str(d.get("filename", "")) for d in (rows or []) if d.get("filename")}


def _total_kb_chars(rows: list) -> int:
    return sum(len((d.get("text") or "")) for d in (rows or []))


def _document_summaries(agent: dict) -> list[KnowledgeDocumentSummary]:
    out: list[KnowledgeDocumentSummary] = []
    for d in _knowledge_sources(agent):
        fn = str(d.get("filename") or "document")
        text = d.get("text") or ""
        out.append(KnowledgeDocumentSummary(filename=fn, chars=len(text)))
    return out


def serialize_agent(agent: dict) -> AgentResponse:
    return AgentResponse(
        id=str(agent["_id"]),
        name=agent["name"],
        bot_knowledge=_bot_knowledge(agent),
        tone=agent.get("tone", "friendly"),
        faqs=agent.get("faqs", []),
        api_key=agent["api_key"],
        is_active=agent.get("is_active", True),
        created_at=agent["created_at"],
        documents=_document_summaries(agent),
    )


async def _upload_knowledge_files(
    *,
    response: Response,
    bot_id: str,
    files: list[UploadFile],
    current_user: dict,
) -> AgentResponse:
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    db = get_db()
    agent = await db.agents.find_one({
        "_id": ObjectId(bot_id),
        "owner_id": current_user["_id"],
    })
    if not agent:
        raise HTTPException(status_code=404, detail="Bot not found")

    sources = _knowledge_sources(agent)
    if len(sources) + len(files) > MAX_FILES_PER_AGENT:
        raise HTTPException(
            status_code=400,
            detail=f"Too many knowledge files. Maximum {MAX_FILES_PER_AGENT} per bot.",
        )

    names_in_use = _existing_filenames(sources)
    new_entries: list[dict] = []
    errors: list[str] = []

    for uf in files:
        raw_name = safe_document_filename(uf.filename or "document.txt")
        data = await uf.read()
        if len(data) > MAX_UPLOAD_BYTES:
            errors.append(f"{raw_name}: file exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB")
            continue
        try:
            text = extract_document_text(raw_name, data)
        except ValueError as exc:
            errors.append(f"{raw_name}: {exc}")
            continue
        except Exception as exc:
            errors.append(f"{raw_name}: could not process ({exc})")
            continue

        final_name = unique_filename(names_in_use, raw_name)
        names_in_use.add(final_name)
        new_entries.append({"filename": final_name, "text": text})

    if not new_entries:
        msg = "No files could be processed."
        if errors:
            msg += " " + " ".join(errors)
        raise HTTPException(status_code=400, detail=msg)

    merged = sources + new_entries
    if _total_kb_chars(merged) > MAX_TOTAL_STORED_CHARS:
        raise HTTPException(
            status_code=400,
            detail="Total knowledge from uploaded files would exceed the storage limit. Remove a file and try again.",
        )

    result = await db.agents.find_one_and_update(
        {"_id": ObjectId(bot_id), "owner_id": current_user["_id"]},
        {"$set": {"document_sources": merged}, "$unset": {"pdf_sources": ""}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Bot not found")

    if errors:
        w = " | ".join(errors)[:2048]
        response.headers["X-BotForge-Knowledge-Warnings"] = w
        response.headers["X-BotForge-PDF-Warnings"] = w

    return serialize_agent(result)


@router.post("/create", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(body: CreateAgentRequest, current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = current_user["_id"]

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
        "bot_knowledge": body.bot_knowledge.strip(),
        "tone": body.tone,
        "faqs": [faq.model_dump() for faq in body.faqs],
        "document_sources": [],
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


@router.post("/{bot_id}/knowledge/documents", response_model=AgentResponse)
async def upload_knowledge_documents(
    response: Response,
    bot_id: str,
    files: list[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    return await _upload_knowledge_files(
        response=response,
        bot_id=bot_id,
        files=files,
        current_user=current_user,
    )


@router.post("/{bot_id}/knowledge/pdfs", response_model=AgentResponse)
async def upload_knowledge_pdfs_legacy(
    response: Response,
    bot_id: str,
    files: list[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Alias for older clients; accepts the same file types as /knowledge/documents."""
    return await _upload_knowledge_files(
        response=response,
        bot_id=bot_id,
        files=files,
        current_user=current_user,
    )


@router.delete("/{bot_id}/knowledge/documents/{doc_index}", response_model=AgentResponse)
async def delete_knowledge_document(
    bot_id: str,
    doc_index: int,
    current_user: dict = Depends(get_current_user),
):
    if doc_index < 0:
        raise HTTPException(status_code=400, detail="Invalid document index")

    db = get_db()
    agent = await db.agents.find_one({
        "_id": ObjectId(bot_id),
        "owner_id": current_user["_id"],
    })
    if not agent:
        raise HTTPException(status_code=404, detail="Bot not found")

    sources = _knowledge_sources(agent)
    if doc_index >= len(sources):
        raise HTTPException(status_code=404, detail="Document not found")

    sources.pop(doc_index)

    result = await db.agents.find_one_and_update(
        {"_id": ObjectId(bot_id), "owner_id": current_user["_id"]},
        {"$set": {"document_sources": sources}, "$unset": {"pdf_sources": ""}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Bot not found")
    return serialize_agent(result)


@router.delete("/{bot_id}/knowledge/pdfs/{doc_index}", response_model=AgentResponse)
async def delete_knowledge_pdf_legacy(
    bot_id: str,
    doc_index: int,
    current_user: dict = Depends(get_current_user),
):
    return await delete_knowledge_document(bot_id, doc_index, current_user)


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

    if "bot_knowledge" in update_data:
        update_data["bot_knowledge"] = str(update_data["bot_knowledge"]).strip()

    if not update_data:
        raise HTTPException(status_code=400, detail="Nothing to update")

    mongo_update: dict = {"$set": update_data}
    if "bot_knowledge" in update_data:
        mongo_update["$unset"] = {"business_name": "", "business_description": ""}

    result = await db.agents.find_one_and_update(
        {"_id": ObjectId(bot_id), "owner_id": current_user["_id"]},
        mongo_update,
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
