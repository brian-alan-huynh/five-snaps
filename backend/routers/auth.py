import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pyotp
from fastapi import APIRouter
from dotenv import load_dotenv

from ..main import rds
from ..infra.sessions import Redis
from ..infra.storage import S3

load_dotenv()
env = os.getenv

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={401: {"description": "Unauthorized"}},
)

@router.post("/request-otp")
async def request_otp(first_name: str, email: str):
    try:
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        otp = totp.now()
        
        msg = MIMEMultipart()
        
        msg["Subject"] = "Five Snaps Verification Code"
        msg["From"] = env("EMAIL")
        msg["To"] = email
        
        text = f"""\
            <html>
                <body>
                    <p>Xin chào, {first_name}!!!</p>
                    
                    <p>Here is your Five Snaps Verification Code:</p>
                    
                    <h1>{otp}</h1>
                    
                    <p>Remember:</p>
                    <p><strong>Never share this code with anyone</strong></p>
                    <p><strong>This one-time password will expire in 15 minutes</strong></p>
                    <p><strong>Five Snaps will never ask for this code</strong></p>
                    <p><strong>If you did not request this, change your account password immediately</strong></p>
                    
                    <p>Best regards,</p>
                    <p>Brian A. Huynh, creator of Five Snaps</p>
                </body>
            </html>
        """
        
        msg.attach(MIMEText(text, "html"))
        
        with smtplib.SMTP(env("SMTP_SERVER"), env("SMTP_SERVER_PORT")) as server:
            server.starttls()
            server.login(env("EMAIL"), env("SMTP_EMAIL_APP_PASS"))
            server.sendmail(env("EMAIL"), email, msg.as_string())
            
        res = Redis.add_otp(int(otp), email)
        
        if not res:
            return { "success": False, "message": "Failed to send OTP" }
            
        return { "success": True }
    
    except Exception:
        return { "success": False, "message": "Failed to send OTP" }

@router.post("/verify-otp")
async def verify_otp(email: str, user_otp: str):
    try:
        res = Redis.verify_otp(int(user_otp), email)
    
        if not res:
            return { "success": False, "message": "Invalid OTP" }
    
        return { "success": True }
    
    except Exception:
        return { "success": False, "message": "Failed to verify OTP" }
    
@router.post("/signup")
async def signup(first_name: str, username: str, password: str, email: str):
    try:
        user_id = rds.create_user(first_name, username, password, email)

        if not user_id:
            return { "success": False, "message": "Failed to create account" }

        session_key = Redis.add_new_session(user_id)

        if not session_key:
            return { "success": False, "message": "Failed to create session" }

        return { "success": True, "session_key": session_key }
    
    except Exception:
        return { "success": False, "message": "Failed to create account" }

# add login and oauth below
# when the user signs in, create a new session and fetch the most recent s3 snap image (read_snaps(user_id, most_recent=True)) and put that as the thumbnail_img_url in redis