import threading
import random

from fastapi import FastAPI, Request, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, snap, user
from infra.db import RDS
from infra.sessions import Redis
from infra.messaging import run_consumer
from logging_config import terminate_logging

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://fivesnaps.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(snap.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")

rds = RDS()

@app.on_event("startup")
def startup_processes():
    event = threading.Event()
    
    thread = threading.Thread(target=run_consumer, args=(event,), daemon=True)
    thread.start()
    
    app.state.kafka_thread = thread
    app.state.kafka_stop_event = event

@app.on_event("shutdown")
def shutdown_processes():
    app.state.kafka_stop_event.set()
    app.state.kafka_thread.join()
    
    terminate_logging()

@app.post("/")
async def root(request: Request):
    session_key = request.cookies.get("session_key")
    
    if not session_key:
        return RedirectResponse(url="http://localhost:3000/login")
    
    session = Redis.get_session(session_key)
    
    if not session:
        return RedirectResponse(url="http://localhost:3000/login")
    
    first_name = rds.read_user(session["user_id"])["first_name"].title()
    thumbnail_img_url = session["thumbnail_img_url"]
        
    greeting_messages = ["Howdy", "Greetings", "How's it going",
                         "Hello", "Hi", "Hey", "How are ya?", "What's up?", 
                         "What's going on?", "What's new?", "What're you up to?", 
                         "What're you doing?", "Hola", "Bonjour", "Ciao", "Konnichiwa", 
                         "Nǐ hǎo", "Xin chào", "Merhaba", "Namaste", "Konnichiwa", 
                         "Annyeonghaseyo", "Privet", "Hallo", "Geiá sou", 
                         "Olá", "S̄wạs̄dī", "As-salamu alaykum"]

    if thumbnail_img_url == "not found" or thumbnail_img_url == "error":
        return {
            "no_thumbnail": True,
            "greeting_display": f"{random.choice(greeting_messages)}, {first_name}!",
            "message": (
                "Take a snap to get started!" 
                if thumbnail_img_url == "not found" 
                else "Cannot load thumbnail"
            ),
        }
        
    return {
        "no_thumbnail": False,
        "greeting_display": f"{random.choice(greeting_messages)}, {first_name}!",
        "thumbnail_img_url": thumbnail_img_url,
    }

@app.get("/health")
async def health_check():
    return { "status": "alive" }
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
