from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, date
from bson import ObjectId

from db.mongo import get_db
from core.security import hash_password, verify_password, create_access_token, get_current_user
from models.schemas import SignupRequest, LoginRequest, TokenResponse, UserResponse

router = APIRouter()


def serialize_user(user: dict) -> UserResponse:
    return UserResponse(
        id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        plan=user.get("plan", "free"),
        messages_used=user.get("messages_used", 0),
        messages_limit=user.get("messages_limit", 50),
    )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest):
    db = get_db()

    existing = await db.users.find_one({"email": body.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_doc = {
        "name": body.name,
        "email": body.email,
        "password": hash_password(body.password),
        "plan": "free",
        "messages_used": 0,
        "messages_limit": 50,       # free plan daily limit
        "usage_reset_date": str(date.today()),
        "created_at": datetime.utcnow(),
    }

    result = await db.users.insert_one(user_doc)
    token = create_access_token({"sub": str(result.inserted_id)})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    db = get_db()

    user = await db.users.find_one({"email": body.email})
    if not user or not verify_password(body.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(user["_id"])})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    return serialize_user(current_user)
