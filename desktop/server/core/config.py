"""
Configuration settings for the backend server.
"""

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite:///./chat.db"
    MAX_MESSAGE_LENGTH: int = 10000
    MAX_SESSIONS_PER_USER: int = 100

settings = Settings()