import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pyotp
from fastapi import APIRouter
from dotenv import load_dotenv

from ..main import rds
from ..infra.sessions import Redis

load_dotenv()
env = os.getenv

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={401: {"description": "Unauthorized"}},
)

@router.post("/request-otp")
async def request_otp(email: str):
    pass

@router.post("/verify-otp")
async def verify_otp(email: str, otp: str):
    pass
    
@router.post("/signup")
async def signup(first_name: str, username: str, password: str, email: str):
    user_id = rds.create_user(first_name, username, password, email)

    if not user_id:
        return { "success": False, "message": "Failed to create account" }

    session_key = Redis.add_new_session(user_id)

    if not session_key:
        return { "success": False, "message": "Failed to create session" }

    return { "success": True, "session_key": session_key }

# add oauth below
