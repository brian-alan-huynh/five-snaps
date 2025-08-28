import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()
env = os.getenv

class Settings(BaseSettings):
    env = "dev" # "prod" in production
    app_name = "Firesnaps"
    cors_origins = ["https://firesnaps.co"] if env == "prod" else ["http://localhost:3000", "https://firesnaps.co"]
    trusted_hosts = ["api.firesnaps.co"] if env == "prod" else ["localhost", "127.0.0.1", "api.firesnaps.co"]
    
    csrf_secret_key = env("APP_CSRF_SECRET_KEY")
    csrf_cookie_samesite = "lax"
    csrf_cookie_secure = True if env == "prod" else False
    csrf_token_location = "header"
    
    rate_slowapi_limiter = "50/minute"
