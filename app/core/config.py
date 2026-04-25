from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "QueryBridge AI API"
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1200
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BACKEND_URL: str = "http://localhost:8000/"

    class Config:
        env_file = ".env"

settings = Settings()