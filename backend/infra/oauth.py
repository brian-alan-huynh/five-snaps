import os

from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv

load_dotenv()
env = os.getenv

oauth = OAuth()

oauth.register(
    name="google",
    client_id=env("GOOGLE_CLIENT_ID"),
    client_secret=env("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
        "prompt": "select_account",
    }
)

oauth.register(
    name="facebook",
    client_id=env("FACEBOOK_CLIENT_ID"),
    client_secret=env("FACEBOOK_CLIENT_SECRET"),
    access_token_url="https://graph.facebook.com/v12.0/oauth/access_token",
    authorize_url="https://www.facebook.com/v12.0/dialog/oauth",
    api_base_url="https://graph.facebook.com/v12.0/",
    client_kwargs={
        "scope": "email public_profile",
        "prompt": "select_account",
    }
)

oauth.register(
    name="apple",
    client_id=env("APPLE_CLIENT_ID"),
    client_secret=env("APPLE_CLIENT_SECRET"),
    access_token_url="https://appleid.apple.com/auth/token",
    authorize_url="https://appleid.apple.com/auth/authorize",
    api_base_url="https://appleid.apple.com/auth/",
    client_kwargs={
        "scope": "name email",
        "response_type": "code id_token",
        "response_mode": "form_post",
        "prompt": "select_account",
    }
)
