from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "BotForge"
    APP_ENV: str = "development"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    MONGO_URI: str

    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    DODO_API_KEY: str = ""
    DODO_WEBHOOK_SECRET: str = ""

    FRONTEND_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
