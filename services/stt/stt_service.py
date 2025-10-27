import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import io
import numpy as np

import torch  # Via faster-whisper
import soundfile as sf  # For loading audio
from faster_whisper import WhisperModel
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/app/data/logs/stt_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Env vars
DATA_PATH = os.getenv("DATA_PATH", "/app/data")
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")  # small/medium for CPU
DEVICE = "cpu"  # Fixed for offline Docker
COMPUTE_TYPE = "int8"  # Fast on CPU
LANGUAGE = "en"  # Default

# Load model once at startup
try:
    model = WhisperModel(
        MODEL_SIZE,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        download_root=Path(DATA_PATH) / "whisper_models"  # Persist in volume
    )
    logger.info(f"Whisper model '{MODEL_SIZE}' loaded on {DEVICE} with {COMPUTE_TYPE}")
except Exception as e:
    logger.error(f"Model load failed: {e}")
    model = None

app = FastAPI(title="AGI STT Service", version="1.0.0", description="Offline Speech-to-Text using faster-whisper")

# Pydantic Models
class STTRequest(BaseModel):
    """Optional params for transcription."""
    language: str = Field(default=LANGUAGE, description="Audio language (ISO code)")
    save_to_disk: bool = Field(default=False, description="Save audio to DATA_PATH")

class STTSegment(BaseModel):
    """Single transcription segment."""
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcribed text")
    confidence: Optional[float] = Field(None, description="Average probability")

class STTResponse(BaseModel):
    """Full transcription response."""
    full_transcript: str = Field(..., description="Concatenated text")
    segments: List[STTSegment] = Field(..., description="Timed segments")
    metadata: Dict[str, Any] = Field(..., description="Processing info")

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP error: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(status_code=400, content={"error": "Invalid input", "details": exc.errors()})

# Endpoints
@app.get("/health")
async def health_check():
    """Health check for Docker."""
    global model
    is_healthy = model is not None
    logger.info(f"Health check: Model loaded = {is_healthy}")
    return {
        "status": "healthy" if is_healthy else "degraded",
        "service": "stt",
        "model_loaded": is_healthy,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/transcribe", response_model=STTResponse)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file (WAV/MP3/etc.)"),
    request: STTRequest = Depends()
):
    """
    Transcribe audio file to text with timestamps.
    - Upload audio clip.
    - Uses faster-whisper for offline processing.
    - Optional: Save to disk.
    """
    global model
    if model is None:
        raise HTTPException(status_code=503, detail="STT model not loaded")

    start_time = datetime.utcnow()
    logger.info(f"Transcribing: {file.filename}, size: {file.size}, lang: {request.language}")

    # Validate audio
    if file.content_type is None:
        logger.warning("No content_type provided; defaulting to invalid")
        raise HTTPException(status_code=400, detail="Missing content-type header; ensure valid audio upload")
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be audio (WAV/MP3/etc.)")
    if file.size > 50 * 1024 * 1024:  # 50MB limit for clips
        raise HTTPException(status_code=400, detail="Audio too large (>50MB)")
    if file.size == 0:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    # Read bytes
    try:
        audio_bytes = await file.read()
        logger.debug(f"Audio bytes loaded: {len(audio_bytes)}")
    except Exception as e:
        logger.error(f"File read failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid audio file")

    # Save to disk if requested
    saved_path = None
    if request.save_to_disk:
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"stt_{timestamp}_{Path(file.filename).stem}.{Path(file.filename).suffix}"
        saved_path = Path(DATA_PATH) / filename
        try:
            saved_path.parent.mkdir(parents=True, exist_ok=True)
            with open(saved_path, "wb") as f:
                f.write(audio_bytes)
            logger.info(f"Audio saved: {saved_path}")
        except Exception as e:
            logger.warning(f"Save failed (non-fatal): {e}")

    # Transcribe (FIX: Omit sample_rate for array input; handle sf.read errors)
    try:
        # Load audio bytes as np.array
        try:
            audio_data, sample_rate = sf.read(io.BytesIO(audio_bytes))
            logger.debug(f"Audio loaded: shape {audio_data.shape}, dtype {audio_data.dtype}, sample_rate {sample_rate}")
        except Exception as load_e:
            logger.error(f"Audio format error: {load_e}")
            raise HTTPException(status_code=400, detail="Invalid audio format (not a recognized WAV/MP3)")

        # Ensure mono (average channels if stereo)
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)

        # Resample to 16kHz if needed (optional, faster-whisper handles but for consistency)
        if sample_rate != 16000:
            from scipy.signal import resample
            num_samples = int(len(audio_data) * 16000 / sample_rate)
            audio_data = resample(audio_data, num_samples)
            sample_rate = 16000
            logger.debug(f"Resampled to 16kHz: {len(audio_data)} samples")

        # Convert to float32
        audio_data = audio_data.astype(np.float32)

        # Check for too short audio
        if len(audio_data) < 1000:  # ~0.06s at 16kHz
            raise HTTPException(status_code=400, detail="Audio too short (no speech detected)")

        # Transcribe from array (omit sample_rate for array input)
        segments, info = model.transcribe(
            audio_data,  # Array input—no sample_rate
            language=request.language,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            beam_size=5,
            no_repeat_ngram_size=3,
            best_of=1
        )
        logger.debug(f"Transcription info: {info}")

        # Collect segments
        transcript_segments = []
        full_text = []
        for segment in segments:
            confidence = getattr(segment, 'avg_logprob', None)
            seg_dict = {
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
                "confidence": round(confidence, 2) if confidence else None
            }
            transcript_segments.append(STTSegment(**seg_dict))
            full_text.append(seg_dict["text"])

        full_transcript = " ".join(full_text).strip()

        if not full_transcript:
            logger.warning("No transcript generated (silent audio?)")
            full_transcript = "[No speech detected]"

        logger.info(f"Transcription complete: {len(transcript_segments)} segments, text: {full_transcript[:100]}...")
    except HTTPException:
        raise  # Re-raise validation errors
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")

    # Metadata
    metadata = {
        "processed_at": start_time.isoformat(),
        "file_size_bytes": len(audio_bytes),
        "language": request.language,
        "model_size": MODEL_SIZE,
        "device": DEVICE,
        "duration_s": info.duration if hasattr(info, 'duration') else None,
        "sample_rate": sample_rate,
        "saved_path": str(saved_path) if saved_path else None,
        "transcription_time_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
    }

    response_data = STTResponse(
        full_transcript=full_transcript,
        segments=transcript_segments,
        metadata=metadata
    )

    return response_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)