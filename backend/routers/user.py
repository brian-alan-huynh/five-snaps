from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ..main import rds
from ..infra.sessions import Redis

router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={ 401: { "description": "Unauthorized" } },
)

@router.get("/details")
async def details(request: Request):
    try:
        session_key = request.cookies.get("session_key")
        session = Redis.get_session(session_key)
        user_id = session["user_id"]
        
        if not session:
            return RedirectResponse(url="http://localhost:3000/error?where=details&reason=session+fetch+error")
        
        user_details = rds.read_user(user_id)
        
        if not user_details:
            return RedirectResponse(url="http://localhost:3000/error?where=details&reason=user+fetch+error")
        
        user_preferences_details = rds.read_user_preference(user_id)
        
        if not user_preferences_details:
            return RedirectResponse(url="http://localhost:3000/error?where=details&reason=user+preferences+fetch+error")
    
        return user_details | user_preferences_details
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=details&reason={e}")

@router.post("/update")
async def update(
    request: Request,
    first_name: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    email: Optional[str] = None,
    theme: Optional[str] = None,
):
    try:
        session_key = request.cookies.get("session_key")
        session = Redis.get_session(session_key)
        user_id = session["user_id"]
        
        if not session:
            return RedirectResponse(url="http://localhost:3000/error?where=update&reason=session+fetch+error")
        
        res_user = rds.update_user(user_id, first_name, username, password, email)
        
        if not res_user:
            return RedirectResponse(url="http://localhost:3000/error?where=update&reason=user+update+error")
        
        if theme:
            res_user_preference = rds.update_user_preference(user_id, theme)
            
            if not res_user_preference:
                return RedirectResponse(url="http://localhost:3000/error?where=update&reason=user+preferences+update+error")
        
        return { "message": "Updated successfully" }
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=update&reason={e}")

@router.post("/delete")
async def delete(request: Request, response: Response):
    try:
        session_key = request.cookies.get("session_key")
        session = Redis.get_session(session_key)
        user_id = session["user_id"]
        
        if not session:
            return RedirectResponse(url="http://localhost:3000/error?where=delete&reason=session+fetch+error")
        
        res_user_preference = rds.delete_user_preference(user_id)
        
        if not res_user_preference:
            return RedirectResponse(url="http://localhost:3000/error?where=delete&reason=user+preferences+delete+error")
        
        res_user = rds.delete_user(user_id)
        
        if not res_user:
            return RedirectResponse(url="http://localhost:3000/error?where=delete&reason=user+delete+error")
        
        Redis.delete_session(session_key)
        response.delete_cookie("session_key")
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?where=delete&reason={e}")
