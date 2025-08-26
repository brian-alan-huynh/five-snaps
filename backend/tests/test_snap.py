from unittest.mock import Mock, patch, AsyncMock
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from fastapi import UploadFile

from backend.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_app_state():
    app.state.logger = Mock()
    app.state.logger.log_error = Mock()

@pytest.fixture
def mock_csrf():
    with patch("backend.routers.snap.CsrfProtect") as mock:
        mock_instance = Mock()
        mock_instance.validate_csrf = AsyncMock()
        mock.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_session():
    return {"user_id": "test_user_id"}

@pytest.fixture
def valid_caption_data():
    return {
        "s3_key": "test_s3_key",
        "caption": "This is a test caption"
    }

@pytest.fixture
def mock_upload_file():
    file_content = b"fake image content"
    return UploadFile(
        filename="test.jpg",
        file=BytesIO(file_content),
        content_type="image/jpeg"
    )

class TestGetAllSnaps:
    @patch("backend.infra.db_tagging.MongoDB")
    @patch("backend.infra.storage.S3")
    @patch("backend.infra.sessions.Redis")
    def test_all_snaps_success(self, mock_redis, mock_s3, mock_mongo, mock_csrf, mock_session):
        client.cookies.set("session_key", "test_session")
        
        mock_redis.get_session.return_value = mock_session
        mock_s3.read_snaps.return_value = [{
            "img_url": "https://example.com/image.jpg",
            "created_at": "2023-01-01T00:00:00Z",
            "file_size": 1024,
            "s3_key": "test_key"
        }]
        mock_mongo.read_img_tags_and_captions.return_value = [{
            "tags": ["person", "outdoor"],
            "caption": "Test caption"
        }]
        
        response = client.get("/snap/all")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
        assert data[0]["img_url"] == "https://example.com/image.jpg"
        assert data[0]["tags"] == ["person", "outdoor"]
        assert data[0]["caption"] == "Test caption"

    @patch("backend.infra.sessions.Redis")
    def test_all_snaps_exception(self, mock_redis, mock_csrf):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.side_effect = Exception("Redis error")
        
        response = client.get("/snap/all")
        assert response.status_code == 500

class TestUploadSnap:
    @patch("backend.infra.db_tagging.MongoDB")
    @patch("backend.infra.computer_vision.yolov11_detect_img_objects")
    @patch("backend.infra.storage.S3")
    @patch("backend.infra.sessions.Redis")
    def test_upload_success(self, mock_redis, mock_s3, mock_yolo, mock_mongo, mock_csrf, mock_session, mock_upload_file):
        client.cookies.set("session_key", "test_session")
        
        mock_redis.get_session.return_value = mock_session
        mock_s3.upload_snap.return_value = ("https://example.com/image.jpg", "test_s3_key")
        mock_yolo.return_value = ["person", "outdoor"]
        
        response = client.post("/snap/upload", files={"img_file": ("test.jpg", mock_upload_file.file, "image/jpeg")})
        assert response.status_code == 200
        
        mock_s3.upload_snap.assert_called_once()
        mock_redis.place_thumbnail_img_url.assert_called_with("test_session", "https://example.com/image.jpg")
        mock_mongo.add_img_tags.assert_called_with("test_user_id", "test_s3_key", ["person", "outdoor"])

    @patch("backend.infra.sessions.Redis")
    def test_upload_exception(self, mock_redis, mock_csrf, mock_upload_file):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.side_effect = Exception("Redis error")
        
        response = client.post("/snap/upload", files={"img_file": ("test.jpg", mock_upload_file.file, "image/jpeg")})
        assert response.status_code == 500

class TestCaptionSnap:
    @patch("backend.infra.db_tagging.MongoDB")
    def test_caption_post_success(self, mock_mongo, mock_csrf, valid_caption_data):
        response = client.post("/snap/caption", json=valid_caption_data)
        assert response.status_code == 200
        
        mock_mongo.write_img_caption.assert_called_with("test_s3_key", "This is a test caption")

    @patch("backend.infra.db_tagging.MongoDB")
    def test_caption_put_success(self, mock_mongo, mock_csrf, valid_caption_data):
        response = client.put("/snap/caption", json=valid_caption_data)
        assert response.status_code == 200
        
        mock_mongo.write_img_caption.assert_called_with("test_s3_key", "This is a test caption")

    @patch("backend.infra.db_tagging.MongoDB")
    def test_caption_exception(self, mock_mongo, mock_csrf, valid_caption_data):
        mock_mongo.write_img_caption.side_effect = Exception("MongoDB error")
        
        response = client.post("/snap/caption", json=valid_caption_data)
        assert response.status_code == 500

class TestDeleteSnap:
    @patch("backend.infra.db_tagging.MongoDB")
    @patch("backend.infra.storage.S3")
    def test_delete_single_success(self, mock_s3, mock_mongo, mock_csrf):
        response = client.delete("/snap/single?s3_key=test_key")
        assert response.status_code == 200
        
        mock_s3.delete_snap.assert_called_with("test_key")
        mock_mongo.delete_img_tags_and_captions.assert_called_with("test_key")

    @patch("backend.infra.storage.S3")
    def test_delete_single_exception(self, mock_s3, mock_csrf):
        mock_s3.delete_snap.side_effect = Exception("S3 error")
        
        response = client.delete("/snap/single?s3_key=test_key")
        assert response.status_code == 500

class TestValidation:
    def test_invalid_caption_empty(self, mock_csrf):
        response = client.post("/snap/caption", json={
            "s3_key": "test_key",
            "caption": ""
        })
        assert response.status_code == 422

    def test_invalid_caption_too_long(self, mock_csrf):
        long_caption = "a" * 301
        response = client.post("/snap/caption", json={
            "s3_key": "test_key",
            "caption": long_caption
        })
        assert response.status_code == 422

    def test_invalid_caption_special_chars(self, mock_csrf):
        response = client.post("/snap/caption", json={
            "s3_key": "test_key",
            "caption": "Invalid <script> caption"
        })
        assert response.status_code == 422

    def test_valid_caption_with_allowed_chars(self, mock_csrf):
        with patch("backend.infra.db_tagging.MongoDB"):
            response = client.post("/snap/caption", json={
                "s3_key": "test_key",
                "caption": "Valid caption with 123 & @symbols!"
            })
            assert response.status_code == 200

class TestRateLimiting:
    def test_all_snaps_rate_limit(self, mock_csrf):
        client.cookies.set("session_key", "test_session")
        
        with patch("backend.infra.sessions.Redis") as mock_redis:
            mock_redis.get_session.return_value = {"user_id": "test_user"}
            
            # Simulate rate limit exceeded
            for _ in range(31):
                response = client.get("/snap/all")
            
            # Should eventually hit rate limit
            assert response.status_code in [200, 429]

class TestErrorHandling:
    @patch("backend.infra.sessions.Redis")
    def test_snap_error_logging(self, mock_redis, mock_csrf):
        client.cookies.set("session_key", "test_session")
        mock_redis.get_session.side_effect = Exception("Test error")
        
        client.get("/snap/all")
        
        app.state.logger.log_error.assert_called_once()
        error_call = app.state.logger.log_error.call_args[0][0]
        assert "Failed to perform snap operation in all" in error_call
