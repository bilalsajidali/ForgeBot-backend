from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.config import settings
from db.mongo import connect_db, close_db
from routes import auth, agents, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="BotForge API",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(auth.router,   prefix="/auth",   tags=["Auth"])
app.include_router(agents.router, prefix="/agents", tags=["Agents"])
app.include_router(chat.router,   prefix="/chat",   tags=["Chat"])


@app.get("/")
async def root():
    return {"status": "BotForge API running 🚀"}
