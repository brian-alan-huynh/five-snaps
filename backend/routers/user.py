from typing import Optional

from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from fastapi_csrf_protect import CsrfProtect

from ..main import app, limiter
from ..infra.storage import S3
from ..infra.sessions import Redis

router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={ 401: { "description": "Unauthorized" } },
)

# Pydantic models
class NormalDetailsResponse(BaseModel):
    is_oauth: bool
    account_type: str
    username: str
    email: EmailStr
    first_name: str
    user_id: int
    created_at: str
    last_login_at: str
    snap_count: int
    
class OAuthDetailsResponse(BaseModel):
    is_oauth: bool
    account_type: str
    first_name: str
    user_id: int
    created_at: str
    last_login_at: str
    snap_count: int
    
DetailsResponse = NormalDetailsResponse | OAuthDetailsResponse

# Error handling
class UserError(Exception):
    "Exception for user operations"
    pass
    
def _raise_user_operation_error(func_name: str, error: Exception) -> None:
    error_message = f"Failed to perform user operation in {func_name}: {error}"
    
    app.state.logger.log_error(error_message)
    raise UserError(error_message) from error

@router.get("/details", response_model=DetailsResponse)
@limiter.limit("30/minute")
async def details(request: Request, csrf_protect: CsrfProtect = Depends()):
    await csrf_protect.validate_csrf(request)
    
    try:
        session_key = request.cookies.get("session_key")
        
        session = Redis.get_session(session_key)
        user_id = session["user_id"]
        
        user_details = app.state.rds.read_user(user_id)
        user_preferences_details = app.state.rds.read_user_preference(user_id)
    
        details = user_details | user_preferences_details
        details["snap_count"] = S3.get_snap_count(user_id)
        
        if details["is_oauth"]:
            return OAuthDetailsResponse(**details)
        
        return NormalDetailsResponse(**details)
    
    except Exception as e:
        _raise_user_operation_error("details", e)

@router.put("/update")
@limiter.limit("30/minute")
async def update(
    request: Request,
    first_name: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    email: Optional[str] = None,
    theme: Optional[str] = None,
    csrf_protect: CsrfProtect = Depends(),
):
    await csrf_protect.validate_csrf(request)
    
    try:
        session_key = request.cookies.get("session_key")

        session = Redis.get_session(session_key)
        user_id = session["user_id"]
        
        app.state.rds.update_user(user_id, first_name, username, password, email)
        
        if theme:
            app.state.rds.update_user_preference(user_id, theme)
        
        return Response(status_code=200, content="Updated successfully")
    
    except Exception as e:
        _raise_user_operation_error("update", e)

@router.delete("/account")
async def delete(
    request: Request,
    response: Response,
    csrf_protect: CsrfProtect = Depends(),
):
    await csrf_protect.validate_csrf(request)
    
    try:
        session_key = request.cookies.get("session_key")
        
        session = Redis.get_session(session_key)
        user_id = session["user_id"]
        
        app.state.rds.delete_user_preference(user_id)
        app.state.rds.delete_user(user_id)
        Redis.delete_session(session_key)
        response.delete_cookie("session_key")
        
        return Response(status_code=200, content="Account deleted successfully")
    
    except Exception as e:
        _raise_user_operation_error("delete", e)
