from ..main import app
from ..routers.auth import _raise_auth_operation_error
from ..infra.sessions import Redis
from ..infra.storage import S3

def update_thumbnail(user_id: int, session_key: str) -> None:
    most_recent_snap = S3.read_newest_snap(user_id)

    if most_recent_snap == "":
        return
    
    Redis.place_thumbnail_img_url(session_key, most_recent_snap)
    return

def signup_or_login_oauth(first_name: str, provider: str, oauth_user_id: int) -> str:
    try:
        user_id = app.state.rds.check_and_fetch_oauth_login_creds(oauth_user_id)
        new_account = True
            
        if not user_id:
            new_user_id = app.state.rds.create_user(
                first_name=first_name,
                oauth_provider=provider,
                oauth_provider_user_id=oauth_user_id,
            )
            
            app.state.rds.create_user_preference(new_user_id, "light")
            
            user_id = new_user_id
            
        else:
            new_account = False
        
        session_key = Redis.add_new_session(user_id)
         
        if not new_account:
            update_thumbnail(user_id, session_key)
            
        return session_key
        
    except Exception as e:
        _raise_auth_operation_error("signup_or_login_oauth", e)
    
def redirect_and_set_cookie(session_key: str) -> RedirectResponse:
    response = RedirectResponse(url="http://localhost:3000/home", status_code=302)
    
    response.set_cookie(
        key="session_key",
        value=session_key,
        httponly=True,
        secure=True,
        same_site="lax",
        max_age=60 * 60 * 24 * 7 * 4 * 6,
    )
    
    return response
