import threading
import random

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, snap, settings
from infra.db import RDS
from infra.messaging import run_consumer

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
app.include_router(settings.router, prefix="/api/v1")

rds = RDS()

@app.on_event("startup")
def start_kafka_consumer():
    event = threading.Event()
    
    thread = threading.Thread(target=run_consumer, args=(event,), daemon=True)
    thread.start()
    
    app.state.kafka_thread = thread
    app.state.kafka_stop_event = event

@app.on_event("shutdown")
def stop_kafka_consumer():
    app.state.kafka_stop_event.set()
    app.state.kafka_thread.join()

@app.get("/")
async def root():
    greeting_messages = ["Howdy", "Greetings", "How's it going",
                         "Hello", "Hi", "Hey", "How are ya?", "What's up?", 
                         "What's going on?", "What's new?", "What're you up to?", 
                         "What're you doing?", "Hola", "Bonjour", "Ciao", "Konnichiwa", 
                         "Nǐ hǎo", "Xin chào", "Merhaba", "Namaste", "Konnichiwa", 
                         "Annyeonghaseyo", "Privet", "Hallo", "Geiá sou"]

    return {
        "message": f"{random.choice(greeting_messages)}, Earthling",
        "version": "0.1.0",
    }

@app.get("/health")
async def health_check():
    return { "status": "alive" }
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
