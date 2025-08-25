import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse, ORJSONResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi_csrf_protect import CsrfProtect

from routers import auth, snap, user
from config.app_settings_config import Settings
from config.logging_config import Logging
from infra.db import RDS
from infra.sessions import Redis
from infra.messaging import run_consumer

settings = Settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_slowapi_limiter],
)

# Pydantic models
class RootWithThumbnail(BaseModel):
    greeting_message: str
    thumbnail_img_url: str
    session_created_at: str

class RootNoThumbnail(BaseModel):
    greeting_message: str
    message: str
    
RootResponse = RootWithThumbnail | RootNoThumbnail

class CsrfSettings(BaseModel):
    secret_key: str = settings.csrf_secret_key
    cookie_samesite: str = settings.csrf_cookie_samesite
    cookie_secure: bool = settings.csrf_cookie_secure
    token_location: str = settings.csrf_token_location
    
    
@CsrfProtect.load_config
def get_csrf_config() -> CsrfSettings:
    return CsrfSettings()
class CsrfTokenOut(BaseModel):
    csrf_token = Field(..., description="Send this in a 'X-CSRF-Token' header")
    
# Error handling
class RootError(Exception):
    "Exception for root operations"
    pass

# Server configs and root logic
@asynccontextmanager
async def lifespan(app: FastAPI):
    rds = RDS()
    logging = Logging()
    
    app.state.rds = rds
    app.state.logging = logging
    
    stop_event = threading.Event()
    thread = threading.Thread(target=run_consumer, args=(stop_event,), daemon=True)
    thread.start()
    
    app.state.kafka_thread = thread
    app.state.kafka_stop_event = stop_event
    
    yield
    
    app.state.kafka_stop_event.set()
    app.state.kafka_thread.join(timeout=5)

app = FastAPI(
    title=settings.app_name,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(GZipMiddleware, minimum_size=1024)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    res = await call_next(request)
    res.headers["X-Content-Type-Options"] = "nosniff"
    res.headers["X-Frame-Options"] = "DENY"
    res.headers["Referrer-Policy"] = "no-referrer"

    if settings.env == "prod":
        res.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
    return res

app.include_router(auth.router, prefix="/api/v1")
app.include_router(snap.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/", response_model=RootResponse)
@limiter.limit("40/minute")
async def root(request: Request, csrf_protect: CsrfProtect = Depends()):
    await csrf_protect.validate_csrf(request)
    
    try:
        session_key = request.cookies.get("session_key")
        
        if not session_key:
            return RedirectResponse(url="http://localhost:3000/login", status_code=302)
        
        session = Redis.get_session(session_key)
        
        if not session:
            return RedirectResponse(url="http://localhost:3000/login", status_code=302)
        
        first_name = app.state.rds.read_user(session["user_id"])["first_name"].title()
        thumbnail_img_url = session["thumbnail_img_url"]
        created_at = session["created_at"]

        if not thumbnail_img_url:
            return RootNoThumbnail(
                greeting_message=f"{random_greeting()}, {first_name}!",
                message="Take a snap to get started!",
            )
            
        return RootWithThumbnail(
            greeting_message=f"{random_greeting()}, {first_name}!",
            thumbnail_img_url=thumbnail_img_url,
            session_created_at=created_at,
        )
    
    except Exception as e:
        error_message = f"Failed to perform root operation: {e}"
    
        app.state.logger.log_error(error_message)
        raise RootError(error_message) from e
    
@app.get("/csrf", response_model=CsrfTokenOut)
@limiter.limit("20/minute")
async def issue_csrf(csrf_protect: CsrfProtect = Depends()):
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    
    res = JSONResponse(content={ "csrf_token": csrf_token })
    csrf_protect.set_csrf_cookie(signed_token, res)
    
    return res

@app.get("/health")
@limiter.limit("60/minute")
async def health_check():
    return { "status": "alive" }

# Make mypy happy
import random
def random_greeting() -> str:
    greeting_messages = ["Howdy", "Greetings", "How's it going",
                            "Hello", "Hi", "Hey", "How are ya?", "What's up?", 
                            "What's going on?", "What's new?", "What're you up to?", 
                            "What're you doing?", "Hola", "Bonjour", "Ciao", "Konnichiwa", 
                            "Nǐ hǎo", "Xin chào", "Merhaba", "Namaste", "Konnichiwa", 
                            "Annyeonghaseyo", "Privet", "Hallo", "Geiá sou", 
                            "Olá", "S̄wạs̄dī", "As-salamu alaykum"]
    
    return random.choice(greeting_messages)
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
