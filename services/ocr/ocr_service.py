import os
import json
import base64
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from io import BytesIO
from pathlib import Path
from PIL import Image  # Already imported

import requests
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
        logging.FileHandler("/app/data/logs/ocr_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Env vars
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DATA_PATH = os.getenv("DATA_PATH", "/app/data")
MODEL_NAME = "gemma3:latest"  # Matches pulled model (4B variant, 3.3GB)

app = FastAPI(title="AGI OCR Service", version="1.0.0", description="Vision-based OCR for UI actions")

# Pydantic Models
class OCRRequest(BaseModel):
    """Request model for optional params."""
    save_to_disk: bool = Field(default=False, description="Save image to DATA_PATH")

class OCRAction(BaseModel):
    """Structured action from OCR."""
    type: str = Field(..., description="e.g., 'click', 'type', 'scroll'")
    element: str = Field(..., description="UI element description")
    position: Optional[List[float]] = Field(None, description="Approximate [x, y] coords")
    value: Optional[str] = Field(None, description="Typed value or text")

class OCRResponse(BaseModel):
    """Response model with extracted data."""
    extracted_text: str = Field(..., description="Full OCR text")
    actions: List[OCRAction] = Field(..., description="Inferred UI actions")
    metadata: Dict[str, Any] = Field(..., description="Processing info")

# Global exception handlers
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
    logger.info("Health check requested")
    return {"status": "healthy", "service": "ocr", "timestamp": datetime.utcnow().isoformat()}

@app.post("/process_image", response_model=OCRResponse)
async def process_image(
    file: UploadFile = File(..., description="Screenshot or image file"),
    request: OCRRequest = Depends()
):
    """
    Process image for OCR and UI action inference.
    - Upload PNG/JPG screenshot.
    - Uses Gemma 3 to extract text + structured actions.
    - Optional: Save to disk for DB reference.
    """
    start_time = datetime.utcnow()
    logger.info(f"Processing image: {file.filename}, size: {file.size}")

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (PNG/JPG)")
    if file.size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="Image too large (>10MB)")

    # Read and validate image
    try:
        image_bytes = await file.read()
        image = Image.open(BytesIO(image_bytes))
        if image.mode != "RGB":
            image = image.convert("RGB")
        logger.debug(f"Image validated: {image.size}, mode: {image.mode}")
    except Exception as e:
        logger.error(f"Image validation failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Resize for faster inference (512x512 max, keeps aspect)
    max_size = (512, 512)
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    logger.debug(f"Resized to: {image.size}")

    # Save to disk if requested
    saved_path = None
    if request.save_to_disk:
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"ocr_{timestamp}_{Path(file.filename).stem}.png"
        saved_path = Path(DATA_PATH) / filename
        try:
            saved_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(saved_path, "PNG")
            logger.info(f"Image saved: {saved_path}")
        except Exception as e:
            logger.warning(f"Save failed (non-fatal): {e}")

    # Encode to base64
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
    logger.debug("Image base64 encoded")

    # Improved prompt: Explicit, image-focused, no examples (Gemma follows better)
    prompt = """You are analyzing a screenshot of a VS Code editor showing a file tree for an AGI Assistant project.

1. Extract ALL visible text accurately (OCR) from file names, folders, code snippets.
2. Infer UI actions: clicks on files/folders, typing in editor.

Output ONLY valid JSON, no markdown or extra text:
{
  "extracted_text": "Concatenated all text from the image",
  "actions": [
    {"type": "click", "element": "specific file/folder name", "position": [approx_x, approx_y]},
    {"type": "type", "element": "editor line", "value": "code snippet"}
  ]
}

Focus on THIS image only. Be precise with file names like 'docker-compose.yml', 'ocr_service.py'."""

    # Call Ollama (increase timeout to 120s for vision)
    ollama_payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "images": [base64_image],
        "stream": False,
        "options": {
            "temperature": 0.0,  # 0 for strict JSON
            "num_predict": 1024  # Longer for full output
        }
    }
    try:
        response = _call_ollama(ollama_payload)
        raw_output = response.get("response", "").strip()
        logger.info(f"Ollama raw response (first 300 chars): {raw_output[:300]}...")  # Better debug
    except Exception as e:
        logger.error(f"Ollama call failed: {e}")
        raise HTTPException(status_code=503, detail="OCR model unavailable")

    # Improved Parse: Strip markdown, multiple regex attempts
    try:
        # Strip common markdown wrappers
        raw_output = raw_output.strip("```json")
        ocr_data = json.loads(raw_output)
        logger.debug("JSON parsed successfully")
    except json.JSONDecodeError:
        logger.warning("Direct JSON parse failed, using regex fallback")
        import re
        # Robust regex for JSON block (handles whitespace)
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_output, re.DOTALL)
        if json_match:
            try:
                ocr_data = json.loads(json_match.group())
                logger.debug("Regex JSON parsed successfully")
            except json.JSONDecodeError:
                ocr_data = {"extracted_text": raw_output[:500], "actions": []}
                logger.warning("Regex fallback also failed")
        else:
            logger.error("No JSON block found in response")
            ocr_data = {"extracted_text": raw_output[:500], "actions": []}

    # Ensure structure
    extracted_text = ocr_data.get("extracted_text", "")
    actions = [
        OCRAction(**action) for action in ocr_data.get("actions", [])
        if isinstance(action, dict)
    ]

    # Build response
    metadata = {
        "processed_at": start_time.isoformat(),
        "file_size_bytes": len(image_bytes),
        "image_dimensions": list(image.size),  # Original size
        "saved_path": str(saved_path) if saved_path else None,
        "model_used": MODEL_NAME,
        "duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
    }

    response_data = OCRResponse(
        extracted_text=extracted_text,
        actions=actions,
        metadata=metadata
    )

    logger.info(f"OCR complete: {len(actions)} actions detected, text length: {len(extracted_text)}")
    return response_data

# Helper Functions
def _call_ollama(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call Ollama /api/generate with retry."""
    url = f"{OLLAMA_URL}/api/generate"
    for attempt in range(2):
        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=120,  # Increased for vision
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ollama attempt {attempt+1} failed: {e}")
            if attempt == 1:
                raise HTTPException(status_code=503, detail=f"Ollama unavailable: {e}")
    raise HTTPException(status_code=500, detail="Unexpected error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)