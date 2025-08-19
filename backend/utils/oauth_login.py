from ..main import rds
from ..infra.sessions import Redis
from ..infra.storage import S3

def signup_or_login_oauth(first_name: str, provider: str, user_id: int) -> dict[str, str | int]:
    try:
        res_login = rds.check_login_creds(oauth_user_id=user_id)
            
        if not res_login:
            user_id = rds.create_user(
                first_name=first_name,
                oauth_provider=provider,
                oauth_provider_user_id=user_id,
            )
        else:
            user_id = rds.check_login_creds(oauth_user_id=user_id, after_successful_2fa_or_oauth=True)
        
        session_key = Redis.add_new_session(user_id)
        
        if not session_key:
            return { "success": False, "message": "Failed to create session" }
        
        if res_login:
            most_recent_snap = S3.read_snaps(user_id, most_recent=True)
            
            if not most_recent_snap:
                return {
                    "success": True, 
                    "message": "Failed to get the most recent snap for thumbnail", 
                    "session_key": session_key,
                }
            
            res_thumbnail = Redis.place_thumbnail_img_url(session_key, most_recent_snap)
            
            if not res_thumbnail:
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
