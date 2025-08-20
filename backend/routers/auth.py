import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pyotp
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

from ..main import rds
from ..infra.sessions import Redis
from ..infra.oauth import oauth
from ..utils.login import update_thumbnail, signup_or_login_oauth, redirect_and_set_cookie

load_dotenv()
env = os.getenv

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={401: {"description": "Unauthorized"}},
)

@router.get("/login/google")
async def login_google(request: Request):
    try:
        redirect_uri = request.url_for("google_auth")
        return await oauth.google.authorize_redirect(request, redirect_uri)
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=google&reason={e}")
    
@router.get("/auth/google")
async def google_auth(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user = await oauth.google.parse_id_token(token)
        
        user_id = user.get("sub")
        first_name = user.get("given_name")
        
        session_key = signup_or_login_oauth(first_name, "google", user_id)
        
        if not session_key:
            return RedirectResponse(url="http://localhost:3000/error?where=google&reason=session")
        
        return redirect_and_set_cookie(session_key)
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=google&reason={e}")

@router.get("/login/facebook")
async def login_facebook(request: Request):
    try:
        redirect_uri = request.url_for("facebook_auth")
        return await oauth.facebook.authorize_redirect(request, redirect_uri)
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=facebook&reason={e}")
    
@router.get("/auth/facebook")
async def facebook_auth(request: Request):
    try:
        token = await oauth.facebook.authorize_access_token(request)
        resp = await oauth.facebook.get("me?fields=id,first_name,email", token=token)
        user = await resp.json()
        
        user_id = user.get("id")
        first_name = user.get("first_name")
        
        session_key = signup_or_login_oauth(first_name, "facebook", user_id)
        
        if not session_key:
            return RedirectResponse(url="http://localhost:3000/error?where=facebook&reason=session")
        
        return redirect_and_set_cookie(session_key)
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=facebook&reason={e}")
    
@router.get("/login/apple")
async def login_apple(request: Request):
    try:
        redirect_uri = request.url_for("apple_auth")
        return await oauth.apple.authorize_redirect(request, redirect_uri)
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=apple&reason={e}")
    
@router.post("/auth/apple")
async def apple_auth(request: Request):
    try:
        token = await oauth.apple.authorize_access_token(request)
        id_token = token.get("id_token")
        form_data = await request.form()
        user_data = await form_data.get("user")
        
        user_id = id_token.get("sub") if id_token else None
        first_name = json.loads(user_data).get("name", {}).get("firstName") if user_data else None
        
        session_key = signup_or_login_oauth(first_name, "apple", user_id)
        
        if not session_key:
            return RedirectResponse(url="http://localhost:3000/error?where=apple&reason=session")
        
        return redirect_and_set_cookie(session_key)
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=apple&reason={e}")
    
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
            return RedirectResponse(url="http://localhost:3000/error?where=otp&reason=storing+otp")
            
        return True
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=otp&reason={e}")

@router.post("/verify-otp")
async def verify_otp(email: str, user_otp: str):
    try:
        res = Redis.verify_otp(int(user_otp), email)
    
        if not res:
            return False
    
        return True
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=otp&reason={e}")
    
@router.post("/signup")
async def signup(first_name: str, username: str, password: str, email: str, request: Request):
    try:
        user_id = rds.create_user(first_name, username, password, email)

        if not user_id:
            return RedirectResponse(url="http://localhost:3000/error?where=signup&reason=account+create+failure")

        session_key = Redis.add_new_session(user_id)

        if not session_key:
            return RedirectResponse(url="http://localhost:3000/error?where=signup&reason=session+create+failure")

        return redirect_and_set_cookie(session_key)
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=signup&reason={e}")

@router.post("/validate")
async def validate(username_or_email: str, password: str):
    try:
        res = rds.check_login_creds(username_or_email, password)
            
        if not res:
            return { "correct_creds": False, "message": "Incorrect username/email or password" }

        email = res["email"]
        first_name = res["first_name"]
            
        return {
            "correct_creds": True, 
            "email": email, 
            "first_name": first_name,
        }
        
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=validate&reason={e}")
    
@router.post("/login")
async def login(username_or_email: str, password: str):
    try:
        user_id = rds.check_login_creds(username_or_email, password, after_successful_2fa_or_oauth=True)
            
        if not user_id:
            return RedirectResponse(url="http://localhost:3000/error?where=login&reason=login+failure")
            
        session_key = Redis.add_new_session(user_id)
            
        if not session_key:
            return RedirectResponse(url="http://localhost:3000/error?where=login&reason=session+create+failure")
        
        update_thumbnail(user_id, session_key)
            
        return redirect_and_set_cookie(session_key)
        
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=login&reason={e}")
    
@router.post("/logout")
async def logout(session_key: str, response: Response):
    try:
        Redis.delete_session(session_key)
        response.delete_cookie("session_key")
        
        return RedirectResponse(url="http://localhost:3000/login")
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=logout&reason={e}")
