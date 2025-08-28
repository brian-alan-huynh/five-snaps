import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()
env = os.getenv

class Settings(BaseSettings):
    env = "dev" # "prod" in production
    app_name = "Firesnaps"
    cors_origins = ["http://localhost:3000", "https://firesnaps.co"]
    trusted_hosts = ["localhost", "127.0.0.1", "firesnaps.co", "*.firesnaps.co"]
    
    csrf_secret_key = env("APP_CSRF_SECRET_KEY")
    csrf_cookie_samesite = "lax"
    csrf_cookie_secure = False # True in production
    csrf_token_location = "header"
    
    rate_slowapi_limiter = "50/minute"
    
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
