from unittest.mock import Mock, patch

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
    with patch("backend.routers.auth.CsrfProtect") as mock:
        mock_instance = Mock()
        
        mock_instance.validate_csrf = Mock()
        mock.return_value = mock_instance
        
        yield mock_instance

@pytest.fixture
def valid_signup_data():
    return {
        "first_name": "John",
        "username": "johndoe",
        "password": "Password123!",
        "email": "john@example.com"
    }

@pytest.fixture
def valid_login_data():
    return {
        "username_or_email": "johndoe",
        "password": "Password123!"
    }

class TestOAuth:
    @patch("backend.infra.oauth.oauth")
    def test_google_login_redirect(self, mock_oauth):
        mock_oauth.google.authorize_redirect.return_value = Mock()
        
        response = client.get("/auth/login/google")
        assert response.status_code in [200, 302]
        
        mock_oauth.google.authorize_redirect.assert_called_once()

    @patch("backend.infra.oauth.oauth")
    @patch("backend.utils.login.signup_or_login_oauth")
    @patch("backend.utils.login.redirect_and_set_cookie")
    def test_google_auth_callback(self, mock_redirect, mock_signup, mock_oauth):
        mock_oauth.google.authorize_access_token.return_value = {"access_token": "token"}
        mock_oauth.google.parse_id_token.return_value = {
            "sub": "google_user_id",
            "given_name": "John"
        }
        mock_signup.return_value = "session_key"
        
        client.get("/api/v1/auth/google")
        
        mock_signup.assert_called_with("John", "google", "google_user_id")

class TestOTP:
    @patch("backend.infra.sessions.Redis")
    @patch("backend.routers.auth.smtplib.SMTP")
    @patch("backend.routers.auth.pyotp.TOTP")
    def test_request_otp_success(self, mock_totp, mock_smtp, mock_redis, valid_signup_data, mock_csrf):
        mock_totp_instance = Mock()
        
        mock_totp_instance.now.return_value = "123456"
        mock_totp.return_value = mock_totp_instance
        
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        response = client.post("/api/v1/auth/request-otp", json=valid_signup_data)
        assert response.status_code == 200
        
        mock_redis.add_otp.assert_called_once()

    @patch("backend.infra.sessions.Redis")
    def test_verify_otp_success(self, mock_redis, mock_csrf):
        mock_redis.verify_otp.return_value = True
        
        response = client.post("/api/v1/auth/verify-otp", json={
            "email": "john@example.com",
            "user_otp": 123456
        })
        
        assert response.status_code == 200
        assert response.text == '"Verification successful"'

    @patch("backend.infra.sessions.Redis")
    def test_verify_otp_invalid(self, mock_redis, mock_csrf):
        mock_redis.verify_otp.return_value = False
        
        response = client.post("/api/v1/auth/verify-otp", json={
            "email": "john@example.com",
            "user_otp": 123456
        })
        
        assert response.status_code == 401

class TestSignupLogin:
    @patch("backend.infra.sessions.Redis")
    @patch("backend.utils.login.redirect_and_set_cookie")
    def test_signup_success(self, mock_redirect, mock_redis, valid_signup_data, mock_csrf):
        app.state.rds = Mock()

        app.state.rds.create_user.return_value = "user_id"
        app.state.rds.create_user_preference.return_value = None
        mock_redis.add_new_session.return_value = "session_key"
        
        client.post("/api/v1/auth/signup", json=valid_signup_data)
        
        app.state.rds.create_user.assert_called_with(
            "John", "johndoe", "Password123!", "john@example.com"
        )

    @patch("backend.infra.sessions.Redis")
    def test_validate_credentials_success(self, mock_redis, valid_login_data, mock_csrf):
        app.state.rds = Mock()
        
        app.state.rds.check_or_fetch_normal_login_creds.return_value = {
            "email": "john@example.com",
            "first_name": "John"
        }
        
        response = client.post("/api/v1/auth/validate", json=valid_login_data)
        assert response.status_code == 200
        
        data = response.json()
        
        assert data["email"] == "john@example.com"
        assert data["first_name"] == "John"

    @patch("backend.infra.sessions.Redis")
    def test_validate_credentials_invalid(self, mock_redis, mock_csrf):
        app.state.rds = Mock()
        app.state.rds.check_or_fetch_normal_login_creds.return_value = None
        
        response = client.post("/api/v1/auth/validate", json={
            "username_or_email": "wrong",
            "password": "wrong"
        })
        
        assert response.status_code == 401

    @patch("backend.infra.sessions.Redis")
    @patch("backend.utils.login.update_thumbnail")
    @patch("backend.utils.login.redirect_and_set_cookie")
    def test_login_success(self, mock_redirect, mock_thumbnail, mock_redis, valid_login_data, mock_csrf):
        app.state.rds = Mock()
        
        app.state.rds.check_or_fetch_normal_login_creds.return_value = "user_id"
        mock_redis.add_new_session.return_value = "session_key"
        
        client.post("/api/v1/auth/login", json=valid_login_data)
        
        mock_thumbnail.assert_called_with("user_id", "session_key")

    @patch("backend.infra.sessions.Redis")
    def test_logout(self, mock_redis, mock_csrf):
        client.cookies.set("session_key", "test_session")
        client.post("/api/v1/auth/logout")
        mock_redis.delete_session.assert_called_with("test_session")

class TestValidation:
    def test_invalid_first_name(self, mock_csrf):
        response = client.post("/api/v1/auth/request-otp", json={
            "first_name": "John123",  # Invalid: Contains numbers
            "username": "johndoe",
            "password": "Password123!",
            "email": "john@example.com"
        })
        
        assert response.status_code == 422

    def test_invalid_username(self, mock_csrf):
        response = client.post("/api/v1/auth/request-otp", json={
            "first_name": "John",
            "username": "john@doe",  # Invalid: Contains @
            "password": "Password123!",
            "email": "john@example.com"
        })
        
        assert response.status_code == 422

    def test_weak_password(self, mock_csrf):
        response = client.post("/api/v1/auth/request-otp", json={
            "first_name": "John",
            "username": "johndoe",
            "password": "password",  # Invalid: No uppercase, numbers, or special chars
            "email": "john@example.com"
        })
        
        assert response.status_code == 422

    def test_invalid_email(self, mock_csrf):
        response = client.post("/api/v1/auth/request-otp", json={
            "first_name": "John",
            "username": "johndoe",
            "password": "Password123!",
            "email": "not-an-email"  # Invalid: Not an email
        })
        
        assert response.status_code == 422

class TestErrorHandling:
    @patch("backend.infra.sessions.Redis")
    def test_request_otp_exception(self, mock_redis, valid_signup_data, mock_csrf):
        mock_redis.add_otp.side_effect = Exception("Redis error")
        response = client.post("/api/v1/auth/request-otp", json=valid_signup_data)
        
        assert response.status_code == 500

    @patch("backend.infra.oauth.oauth")
    def test_oauth_exception(self, mock_oauth):
        mock_oauth.google.authorize_redirect.side_effect = Exception("OAuth error")
        response = client.get("/api/v1/auth/login/google")
        
        assert response.status_code == 500
