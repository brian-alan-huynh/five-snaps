from ..main import rds
from ..infra.sessions import Redis
from ..infra.storage import S3

def update_thumbnail(user_id: int, session_key: str) -> bool:
    most_recent_snap = S3.read_snaps(user_id, most_recent=True)
            
    if not most_recent_snap:
        return False
    
    res = Redis.place_thumbnail_img_url(session_key, most_recent_snap)
    
    if not res:
        return False
    
    return True

def signup_or_login_oauth(first_name: str, provider: str, user_id: int) -> dict[str, str | int]:
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
                return { "success": False, "message": "Failed to create account" }
            
            user_id = new_user_id
            
        else:
            new_account = False
        
        session_key = Redis.add_new_session(user_id)
        
        if not session_key:
            return { "success": False, "message": "Failed to create session" }
        
        if not new_account and not update_thumbnail(user_id, session_key):
            return {
                "success": True, 
                "message": "Failed to get the most recent snap for thumbnail", 
                "session_key": session_key,
            }
            
        return {
            "success": True, 
            "message": "Successfully logged in!", 
            "session_key": session_key,
        }
        
    except Exception:
        return { "success": False, "message": "Failed to login" }
