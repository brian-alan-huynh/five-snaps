import pytest
from fastapi.testclient import TestClient

from ..main import app
from ..routers.snap import router

client_app = TestClient(app)
client_snap = TestClient(router)

def test_rate_limit_on_all():
    res_csrf = client_app.get("/csrf")
    token = res_csrf.json()["csrf_token"]
    cookies = res_csrf.cookies
    
    current_call = None
    
    for _ in range(31):
        current_call = client_snap.get(
            "/all",
            cookies=cookies,
            headers={ "X-CSRF-Token": token },
            allow_redirects=False,
        )
        
        if current_call.status_code == 429:
            break
        
    assert current_call is not None
    assert current_call.status_code == 429
    assert "Retry-After" in current_call.headers
