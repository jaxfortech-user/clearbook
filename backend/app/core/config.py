from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "Clearbook"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    SECRET_KEY: str

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"

    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "ap-south-1"
    S3_BUCKET_NAME: str
    SQS_QUEUE_URL: str

    OPENAI_API_KEY: str = ""
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "https://clearbook-inky.vercel.app",
    ]

    class Config:
        env_file = ".env"


settings = Settings()