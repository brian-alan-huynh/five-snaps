import pytest
from fastapi.testclient import TestClient

from ..main import app

client = TestClient(app)

@pytest.fixture
def get_csrf_token_and_cookie() -> tuple[str, dict[str, str]]:
    res = client.get("/csrf")
    token = res.json()["csrf_token"]
    cookies = res.cookies
    
    return token, cookies

def test_health_ok():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "alive"

def test_csrf_issue_and_cookie():
    res = client.get("/csrf")
    assert res.status_code == 200

    data = res.json()
    assert "csrf_token" in data
    
    cookies = res.cookies
    names = ";".join(cookies.keys())
    assert "fastapi-csrf-token" in names

def test_root_redirect_with_csrf_and_without_session(get_csrf_token_and_cookie):
    token, cookies = get_csrf_token_and_cookie
    
    res_root = client.get(
        "/",
        headers={ "X-CSRF-Token": token },
        cookies=cookies,
        allow_redirects=False,
    )
    
    assert res_root.status_code in (302, 500)
    assert "login" in res_root.headers["Location"]
    
def test_rate_limit_on_root(get_csrf_token_and_cookie):
    token, cookies = get_csrf_token_and_cookie

    current_call = None
    
    for _ in range(36):
        current_call = client.get(
            "/",
            headers={ "X-CSRF-Token": token },
            cookies=cookies,
            allow_redirects=False,
        )
        
        if current_call.status_code == 429:
            break
    
    assert current_call is not None
    assert current_call.status_code == 429
    assert "Retry-After" in current_call.headers
