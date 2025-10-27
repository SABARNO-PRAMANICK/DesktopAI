import pytest
import requests
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from PIL import Image
import io

from ocr_service import app, OCRResponse

client = TestClient(app)

# Sample image creation helper
def create_sample_image():
    img = Image.new("RGB", (100, 100), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()

SAMPLE_IMAGE = create_sample_image()

class TestOCRService:
    def test_health(self):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_process_image_valid(self):
        """Test valid image processing (mocks Ollama)."""
        mock_response = {
            "response": '{"extracted_text": "Test Text", "actions": [{"type": "click", "element": "Button"}]}'
        }
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.status_code = 200
            files = {"file": ("test.png", SAMPLE_IMAGE, "image/png")}
            response = client.post("/process_image", files=files)
            assert response.status_code == 200
            data = response.json()
            assert data["extracted_text"] == "Test Text"
            assert len(data["actions"]) == 1
            assert data["metadata"]["image_dimensions"] == [100, 100]

    def test_process_image_invalid_type(self):
        """Test non-image file."""
        invalid_data = b"not an image"
        files = {"file": ("test.txt", invalid_data, "text/plain")}
        response = client.post("/process_image", files=files)
        assert response.status_code == 400
        assert "must be an image" in response.json()["detail"]

    def test_process_image_too_large(self):
        """Test oversized image."""
        large_data = b"a" * (11 * 1024 * 1024)  # >10MB
        files = {"file": ("large.png", large_data, "image/png")}
        response = client.post("/process_image", files=files)
        assert response.status_code == 400
        assert "too large" in response.json()["detail"]

    def test_ollama_failure(self):
        """Test Ollama unavailable (503)."""
        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.RequestException("Connection error")
            files = {"file": ("test.png", SAMPLE_IMAGE, "image/png")}
            response = client.post("/process_image", files=files)
            assert response.status_code == 503
            assert "unavailable" in response.json()["detail"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])