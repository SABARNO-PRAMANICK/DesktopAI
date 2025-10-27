import pytest
import io
import numpy as np
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from pydantic import ValidationError

from stt_service import app, STTResponse, model  # model global

client = TestClient(app)

# Synth audio helper (5s, 16kHz, sine wave + speech sim)
def create_sample_audio(duration=5, sample_rate=16000):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # Simple tone as placeholder (real: use TTS lib, but for test)
    audio = np.sin(440 * t * 2 * np.pi).astype(np.float32)
    buffer = io.BytesIO()
    import soundfile as sf  # pip install soundfile for test
    sf.write(buffer, audio, sample_rate)
    buffer.seek(0)
    return buffer.read(), sample_rate

SAMPLE_AUDIO, SAMPLE_RATE = create_sample_audio()

class TestSTTService:
    def test_health(self):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True

    @patch("faster_whisper.WhisperModel.transcribe")
    def test_transcribe_valid(self, mock_transcribe):
        """Test valid audio (mock transcribe)."""
        mock_segments = MagicMock()
        mock_segments.__iter__.return_value = [
            MagicMock(start=0.0, end=2.0, text="Hello world", avg_logprob=-0.5)
        ]
        mock_info = MagicMock(duration=5.0)
        mock_transcribe.return_value = (mock_segments, mock_info)

        files = {"file": ("test.wav", SAMPLE_AUDIO, "audio/wav")}
        response = client.post("/transcribe", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["full_transcript"] == "Hello world"
        assert len(data["segments"]) == 1
        assert data["segments"][0]["text"] == "Hello world"
        assert data["segments"][0]["confidence"] == -0.5
        assert data["metadata"]["language"] == "en"

    def test_transcribe_invalid_type(self):
        """Test non-audio file."""
        invalid_data = b"not audio"
        files = {"file": ("test.txt", invalid_data, "text/plain")}
        response = client.post("/transcribe", files=files)
        assert response.status_code == 400
        assert "must be audio" in response.json()["detail"]

    def test_transcribe_too_large(self):
        """Test oversized audio."""
        large_data = b"a" * (51 * 1024 * 1024)  # >50MB
        files = {"file": ("large.wav", large_data, "audio/wav")}
        response = client.post("/transcribe", files=files)
        assert response.status_code == 400
        assert "too large" in response.json()["detail"]

    def test_model_not_loaded(self):
        """Test if model fails to load (degraded)."""
        with patch("stt_service.model", None):
            files = {"file": ("test.wav", SAMPLE_AUDIO, "audio/wav")}
            response = client.post("/transcribe", files=files)
            assert response.status_code == 503
            assert "not loaded" in response.json()["detail"]

    @patch("faster_whisper.WhisperModel.transcribe")
    def test_empty_transcript(self, mock_transcribe):
        """Test silent/no-speech audio."""
        mock_segments = MagicMock()
        mock_segments.__iter__.return_value = []  # No segments
        mock_info = MagicMock(duration=5.0)
        mock_transcribe.return_value = (mock_segments, mock_info)

        files = {"file": ("silent.wav", SAMPLE_AUDIO, "audio/wav")}
        response = client.post("/transcribe", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["full_transcript"] == ""
        assert len(data["segments"]) == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])