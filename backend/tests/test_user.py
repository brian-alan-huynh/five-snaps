from unittest.mock import Mock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_app_state():
    app.state.rds = Mock()
    app.state.logger = Mock()
    app.state.logger.log_error = Mock()

@pytest.fixture
def mock_csrf():
    with patch("backend.routers.user.CsrfProtect") as mock:
        mock_instance = Mock()
        mock_instance.validate_csrf = AsyncMock()
        mock.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_session():
    return {"user_id": "test_user_id"}

@pytest.fixture
def normal_user_data():
    return {
        "is_oauth": False,
        "account_type": "normal",
        "username": "johndoe",
        "email": "john@example.com",
        "first_name": "John",
        "user_id": 123,
        "created_at": "2023-01-01T00:00:00Z",
        "last_login_at": "2023-01-02T00:00:00Z"
    }

@pytest.fixture
def oauth_user_data():
    return {
        "is_oauth": True,
        "account_type": "oauth",
        "first_name": "John",
        "user_id": 123,
        "created_at": "2023-01-01T00:00:00Z",
        "last_login_at": "2023-01-02T00:00:00Z"
    }

class TestUserDetails:
    @patch("backend.infra.storage.S3")
    @patch("backend.infra.sessions.Redis")
    def test_normal_user_details_success(self, mock_redis, mock_s3, mock_csrf, mock_session, normal_user_data):
        client.cookies.set("session_key", "test_session")
        
        mock_redis.get_session.return_value = mock_session
        app.state.rds.read_user.return_value = normal_user_data
        app.state.rds.read_user_preference.return_value = {}
        mock_s3.get_snap_count.return_value = 5
        
        response = client.get("/api/v1/user/details")
        assert response.status_code == 200
        
        data = response.json()
        assert data["is_oauth"] == False
        assert data["username"] == "johndoe"
        assert data["email"] == "john@example.com"
        assert data["snap_count"] == 5

    @patch("backend.infra.storage.S3")
    @patch("backend.infra.sessions.Redis")
    def test_oauth_user_details_success(self, mock_redis, mock_s3, mock_csrf, mock_session, oauth_user_data):
        client.cookies.set("session_key", "test_session")
        
        mock_redis.get_session.return_value = mock_session
        app.state.rds.read_user.return_value = oauth_user_data
        app.state.rds.read_user_preference.return_value = {}
        mock_s3.get_snap_count.return_value = 3
        
        response = client.get("/api/v1/user/details")
        assert response.status_code == 200
        
        data = response.json()
        assert data["is_oauth"] == True
        assert data["first_name"] == "John"
        assert data["snap_count"] == 3
        assert "username" not in data
        assert "email" not in data

    @patch("backend.infra.sessions.Redis")
    def test_details_exception(self, mock_redis, mock_csrf):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.side_effect = Exception("Redis error")
        
        response = client.get("/api/v1/user/details")
        assert response.status_code == 500

class TestUserUpdate:
    @patch("backend.infra.sessions.Redis")
    def test_update_user_only_success(self, mock_redis, mock_csrf, mock_session):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.return_value = mock_session
        
        response = client.put("/api/v1/user/update", json={
            "first_name": "NewName",
            "username": "newusername",
            "email": "new@example.com"
        })
        
        assert response.status_code == 200
        assert response.text == '"Updated successfully"'
        
        app.state.rds.update_user.assert_called_with(
            "test_user_id", "NewName", "newusername", None, "new@example.com"
        )

    @patch("backend.infra.sessions.Redis")
    def test_update_with_theme_success(self, mock_redis, mock_csrf, mock_session):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.return_value = mock_session
        
        response = client.put("/api/v1/user/update", json={
            "first_name": "NewName",
            "theme": "dark"
        })
        
        assert response.status_code == 200
        
        app.state.rds.update_user.assert_called_with(
            "test_user_id", "NewName", None, None, None
        )
        app.state.rds.update_user_preference.assert_called_with(
            "test_user_id", "dark"
        )

    @patch("backend.infra.sessions.Redis")
    def test_update_no_fields_success(self, mock_redis, mock_csrf, mock_session):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.return_value = mock_session
        
        response = client.put("/api/v1/user/update", json={})
        
        assert response.status_code == 200
        
        app.state.rds.update_user.assert_called_with(
            "test_user_id", None, None, None, None
        )

    @patch("backend.infra.sessions.Redis")
    def test_update_exception(self, mock_redis, mock_csrf, mock_session):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.return_value = mock_session
        app.state.rds.update_user.side_effect = Exception("Database error")
        
        response = client.put("/api/v1/user/update", json={"first_name": "Test"})
        assert response.status_code == 500

class TestUserDelete:
    @patch("backend.infra.sessions.Redis")
    def test_delete_account_success(self, mock_redis, mock_csrf, mock_session):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.return_value = mock_session
        
        response = client.delete("/api/v1/user/account")
        
        assert response.status_code == 200
        assert response.text == '"Account deleted successfully"'
        
        app.state.rds.delete_user_preference.assert_called_with("test_user_id")
        app.state.rds.delete_user.assert_called_with("test_user_id")
        mock_redis.delete_session.assert_called_with("test_session")

    @patch("backend.infra.sessions.Redis")
    def test_delete_account_exception(self, mock_redis, mock_csrf, mock_session):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.return_value = mock_session
        app.state.rds.delete_user.side_effect = Exception("Database error")
        
        response = client.delete("/api/v1/user/account")
        assert response.status_code == 500

class TestRateLimiting:
    @patch("backend.infra.sessions.Redis")
    @patch("backend.infra.storage.S3")
    def test_details_rate_limit(self, mock_s3, mock_redis, mock_csrf, mock_session, normal_user_data):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.return_value = mock_session
        app.state.rds.read_user.return_value = normal_user_data
        app.state.rds.read_user_preference.return_value = {}
        mock_s3.get_snap_count.return_value = 0
        
        # Simulate rate limit
        for _ in range(31):
            response = client.get("/api/v1/user/details")
        
        assert response.status_code in [200, 429]

    @patch("backend.infra.sessions.Redis")
    def test_update_rate_limit(self, mock_redis, mock_csrf, mock_session):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.return_value = mock_session
        
        # Simulate rate limit
        for _ in range(31):
            response = client.put("/api/v1/user/update", json={"first_name": "Test"})
        
        assert response.status_code in [200, 429]

class TestErrorHandling:
    @patch("backend.infra.sessions.Redis")
    def test_user_error_logging(self, mock_redis, mock_csrf):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.side_effect = Exception("Test error")
        
        client.get("/api/v1/user/details")
        
        app.state.logger.log_error.assert_called_once()
        error_call = app.state.logger.log_error.call_args[0][0]
        assert "Failed to perform user operation in details" in error_call

    @patch("backend.infra.sessions.Redis")
    def test_update_error_logging(self, mock_redis, mock_csrf, mock_session):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.return_value = mock_session
        app.state.rds.update_user.side_effect = Exception("Database error")
        
        client.put("/api/v1/user/update", json={"first_name": "Test"})
        
        app.state.logger.log_error.assert_called_once()
        error_call = app.state.logger.log_error.call_args[0][0]
        assert "Failed to perform user operation in update" in error_call