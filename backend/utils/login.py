from ..main import rds
from ..infra.sessions import Redis
from ..infra.storage import S3

def update_thumbnail(user_id: int, session_key: str) -> bool:
    most_recent_snap = S3.read_snaps(user_id, most_recent=True)
            
    if not most_recent_snap:
        Redis.place_thumbnail_img_url(session_key, "not found")
        return
    
    res = Redis.place_thumbnail_img_url(session_key, most_recent_snap)
    
    if not res:
        Redis.place_thumbnail_img_url(session_key, "error")
        return

def signup_or_login_oauth(first_name: str, provider: str, user_id: int) -> str | bool:
    try:
        user_id = rds.check_login_creds(oauth_user_id=user_id, after_successful_2fa_or_oauth=True)
        new_account = True
            
        if not user_id:
            new_user_id = rds.create_user(
                first_name=first_name,
                oauth_provider=provider,
                oauth_provider_user_id=user_id,
            )
            
            if not new_user_id:
                return False
            
            user_id = new_user_id
            
        else:
            new_account = False
        
        session_key = Redis.add_new_session(user_id)
        
        if not session_key:
            return False
         
        if not new_account:
            update_thumbnail(user_id, session_key)
            
        return session_key
        
    except Exception:
        return False
    
def redirect_and_set_cookie(session_key: str) -> RedirectResponse:
    response = RedirectResponse(url="http://localhost:3000/home")
    
    response.set_cookie(
        key="session_key",
        value=session_key,
        httponly=True,
        secure=True,
        same_site="lax",
        max_age=60 * 60 * 24 * 7 * 4 * 6,
    )
    
    return response
