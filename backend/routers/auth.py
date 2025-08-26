import os
import smtplib
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pyotp
from dotenv import load_dotenv
from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field, validator
from fastapi_csrf_protect import CsrfProtect

from backend.main import app, limiter
from backend.infra.sessions import Redis
from backend.infra.oauth import oauth
from backend.utils.login import update_thumbnail, signup_or_login_oauth, redirect_and_set_cookie

load_dotenv()
env = os.getenv

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={
        401: { "description": "Unauthorized" },
        429: { "description": "Too many requests" },
        500: { "description": "Internal server error" },
    },
)

# Pydantic models
class RequestOtpAndSignupCreds(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=50, strip_whitespace=True)
    username: str = Field(..., min_length=4, max_length=50, strip_whitespace=True)
    password: str = Field(..., min_length=8, max_length=50)
    email: EmailStr
    
    @validator("first_name")
    def validate_first_name(cls, v):
        if not v.replace(" ", "").isalpha():
            raise ValueError("First name must contain only letters and spaces")

        return v.strip().title()
    
    @validator("username")
    def validate_username(cls, v):
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must contain only letters, hyphens, and underscores")

        return v.strip().lower()
    
    @validator("password")
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        
        if not any(c in string.punctuation for c in v):
            raise ValueError("Password must contain at least one special character")
        
        return v

class VerifyOtpCreds(BaseModel):
    email: EmailStr
    user_otp: int = Field(..., ge=100000, le=999999)

class ValidateAndLoginCreds(BaseModel):
    username_or_email: str = Field(..., min_length=4, max_length=50, strip_whitespace=True) | EmailStr
    password: str = Field(..., min_length=8, max_length=50)
    
class ValidateResponse(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=2, max_length=50, strip_whitespace=True)
    
# Error handling
class AuthError(Exception):
    "Exception for auth operations"
    pass

class LoginError(AuthError):
    "Exception for login operations"
    pass

def _raise_auth_operation_error(func_name: str, error: Exception) -> None:
    error_message = f"Failed to perform auth operation in {func_name}: {error}"
    
    app.state.logger.log_error(error_message)
    raise AuthError(error_message) from error

@router.get("/login/google")
async def login_google(request: Request):
    try:
        redirect_uri = request.url_for("google_auth")
        return await oauth.google.authorize_redirect(request, redirect_uri)
    
    except Exception as e:
        _raise_auth_operation_error("login_google", e)
    
@router.get("/auth/google")
async def google_auth(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user = await oauth.google.parse_id_token(token)
        
        oauth_user_id = user.get("sub")
        first_name = user.get("given_name")

        session_key = signup_or_login_oauth(first_name, "google", oauth_user_id)
        
        return redirect_and_set_cookie(session_key)
    
    except Exception as e:
        _raise_auth_operation_error("google_auth", e)

@router.get("/login/facebook")
async def login_facebook(request: Request):
    try:
        redirect_uri = request.url_for("facebook_auth")
        return await oauth.facebook.authorize_redirect(request, redirect_uri)
    
    except Exception as e:
        _raise_auth_operation_error("login_facebook", e)
    
@router.get("/auth/facebook")
async def facebook_auth(request: Request):
    try:
        token = await oauth.facebook.authorize_access_token(request)
        resp = await oauth.facebook.get("me?fields=id,first_name,email", token=token)
        user = await resp.json()
        
        oauth_user_id = user.get("id")
        first_name = user.get("first_name")
        
        session_key = signup_or_login_oauth(first_name, "facebook", oauth_user_id)
        
        return redirect_and_set_cookie(session_key)
    
    except Exception as e:
        _raise_auth_operation_error("facebook_auth", e)
    
@router.get("/login/apple")
async def login_apple(request: Request):
    try:
        redirect_uri = request.url_for("apple_auth")
        return await oauth.apple.authorize_redirect(request, redirect_uri)
    
    except Exception as e:
        _raise_auth_operation_error("login_apple", e)
    
@router.post("/auth/apple")
async def apple_auth(request: Request):
    try:
        token = await oauth.apple.authorize_access_token(request)
        id_token = token.get("id_token")
        form_data = await request.form()
        user_data = await form_data.get("user")
        
        oauth_user_id = id_token.get("sub") if id_token else None
        first_name = json.loads(user_data).get("name", {}).get("firstName") if user_data else None
        
        session_key = signup_or_login_oauth(first_name, "apple", oauth_user_id)
        
        return redirect_and_set_cookie(session_key)
    
    except Exception as e:
        _raise_auth_operation_error("apple_auth", e)
    
@router.post("/request-otp")
@limiter.limit("5/minute")
async def request_otp(
    creds: RequestOtpAndSignupCreds, 
    request: Request, 
    csrf_protect: CsrfProtect = Depends()
):
    await csrf_protect.validate_csrf(request)
    
    try:
        first_name = creds.first_name
        email = creds.email
        
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
            
        Redis.add_otp(int(otp), email)
            
        return Response(status_code=200)

    except Exception as e:
        _raise_auth_operation_error("request_otp", e)

@router.post("/verify-otp")
@limiter.limit("10/minute")
async def verify_otp(
    creds: VerifyOtpCreds,
    request: Request, 
    csrf_protect: CsrfProtect = Depends()
):
    await csrf_protect.validate_csrf(request)
    
    try:
        email = creds.email
        user_otp = creds.user_otp
        
        res = Redis.verify_otp(int(user_otp), email)
    
        if not res:
            return Response(status_code=401, content="Your code is incorrect! Please try again!")
    
        return "Verification successful"
    
    except Exception as e:
        _raise_auth_operation_error("verify_otp", e)
    
@router.post("/signup")
@limiter.limit("5/minute")
async def signup(
    creds: RequestOtpAndSignupCreds,
    request: Request, 
    csrf_protect: CsrfProtect = Depends()
):
    await csrf_protect.validate_csrf(request)
    
    try:
        first_name = creds.first_name
        username = creds.username
        password = creds.password
        email = creds.email
        
        user_id = app.state.rds.create_user(first_name, username, password, email)
        app.state.rds.create_user_preference(user_id, "light")
        session_key = Redis.add_new_session(user_id)

        return redirect_and_set_cookie(session_key)
    
    except Exception as e:
        _raise_auth_operation_error("signup", e)

@router.post("/validate", response_model=ValidateResponse)
@limiter.limit("10/minute")
async def validate(
    creds: ValidateAndLoginCreds,
    request: Request, 
    csrf_protect: CsrfProtect = Depends()
):
    await csrf_protect.validate_csrf(request)
    
    try:
        username_or_email = creds.username_or_email
        password = creds.password
        
        res = app.state.rds.check_or_fetch_normal_login_creds(username_or_email, password)
            
        if not res:
            return Response(status_code=401, content="Incorrect username or password")

        return res
        
    except Exception as e:
        _raise_auth_operation_error("validate", e)
    
@router.post("/login")
@limiter.limit("5/minute")
async def login(
    creds: ValidateAndLoginCreds,
    request: Request, 
    csrf_protect: CsrfProtect = Depends()
):
    await csrf_protect.validate_csrf(request)
    
    try:
        username_or_email = creds.username_or_email
        password = creds.password
        
        user_id = app.state.rds.check_or_fetch_normal_login_creds(username_or_email, password, is_fetch=True)
        
        if not user_id:
            error_message = "Failed to perform login despite correct credentials"
            
            app.state.logger.log_error(error_message)
            raise LoginError(error_message)

        session_key = Redis.add_new_session(user_id)
        update_thumbnail(user_id, session_key)
            
        return redirect_and_set_cookie(session_key)
    
    except LoginError:
        raise

    except Exception as e:
        _raise_auth_operation_error("login", e)
    
@router.post("/logout")
@limiter.limit("1/minute")
async def logout(
    request: Request, 
    response: Response, 
    csrf_protect: CsrfProtect = Depends()
):
    await csrf_protect.validate_csrf(request)
    
    try:
        session_key = request.cookies.get("session_key")
        
        Redis.delete_session(session_key)
        response.delete_cookie("session_key")
        res = JSONResponse(content={ "detail": "success" })
        csrf_protect.unset_csrf_cookie(res)
        
        return RedirectResponse(url="http://localhost:3000/login", status_code=302)
    
    except Exception as e:
        _raise_auth_operation_error("logout", e)
