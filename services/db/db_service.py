import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from models import Base, Observation, Workflow

os.makedirs("/app/data/logs", exist_ok=True)

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/app/data/logs/db_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Env vars
DB_PATH = os.getenv("DB_PATH", "/app/data/agi_assistant.db")
DATA_PATH = os.getenv("DATA_PATH", "/app/data")
DAYS_OLD = int(os.getenv("PURGE_DAYS_OLD", "7"))
STABLE_RUNS = int(os.getenv("PURGE_STABLE_RUNS", "5"))

# DB Setup: WAL mode for better concurrency
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    pool_size=5,
    echo=False  # Set True for debug
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Startup: Create tables
def create_tables():
    try:
        Base.metadata.create_all(bind=engine)
        # Enable WAL mode
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.commit()
        logger.info("DB tables created and WAL enabled")
    except Exception as e:
        logger.error(f"Table creation failed: {e}")
        raise

app = FastAPI(title="AGI DB Service", version="1.0.0", description="SQLite CRUD for observations and workflows")

# Pydantic Models
class ObservationRequest(BaseModel):
    type: str = Field(..., description="'screen' or 'audio'")
    json_data: Dict[str, Any] = Field(..., description="Processed JSON from OCR/STT")
    clip_path: Optional[str] = Field(None, description="File path in /data/")

class ObservationResponse(BaseModel):
    id: int
    timestamp: datetime
    type: str
    json_data: Dict[str, Any]
    clip_path: Optional[str]

class WorkflowRequest(BaseModel):
    pattern_text: str = Field(..., max_length=1000)
    steps_json: List[Dict[str, Any]] = Field(..., description="List of automation steps")

class WorkflowResponse(BaseModel):
    id: int
    created_at: datetime
    pattern_text: str
    steps_json: List[Dict[str, Any]] = Field(..., description="List of steps as array of dicts")
    run_count: int

class PurgeRequest(BaseModel):
    days_old: Optional[int] = Field(None, description="Override DAYS_OLD")
    stable_runs: Optional[int] = Field(None, description="Override STABLE_RUNS")

class PurgeResponse(BaseModel):
    deleted_observations: int = 0
    deleted_workflows: int = 0
    message: str

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Startup event
@app.on_event("startup")
async def startup_event():
    create_tables()

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP error: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(status_code=400, content={"error": "Invalid input", "details": exc.errors()})

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request, exc):
    logger.error(f"DB error: {exc}")
    return JSONResponse(status_code=500, content={"error": "Database operation failed"})

# Endpoints: Observations
@app.get("/health")
async def health_check():
    """Health check: Test DB connection and table existence."""
    try:
        with SessionLocal() as db:
            result = db.execute(text("SELECT COUNT(*) FROM observations")).scalar()
            logger.info(f"Health check: {result} observations")
        return {
            "status": "healthy",
            "db_path": DB_PATH,
            "tables": list(Base.metadata.tables.keys()),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="DB unhealthy")

@app.post("/store_observation", response_model=ObservationResponse, status_code=201)
async def store_observation(
    request: ObservationRequest,
    db: Session = Depends(get_db)
):
    """Store a new observation from OCR/STT."""
    if request.type not in ["screen", "audio"]:
        raise HTTPException(status_code=400, detail="Type must be 'screen' or 'audio'")
    try:
        obs = Observation(
            type=request.type,
            json_data=request.json_data,
            clip_path=request.clip_path
        )
        db.add(obs)
        db.commit()
        db.refresh(obs)
        logger.info(f"Stored observation {obs.id}: {request.type}")
        return obs
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Duplicate entry")
    except Exception as e:
        logger.error(f"Store observation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to store")

@app.get("/get_observations", response_model=List[ObservationResponse])
async def get_observations(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get paginated observations, optional filter by type."""
    query = db.query(Observation)
    if type:
        query = query.filter(Observation.type == type)
    observations = query.order_by(Observation.timestamp.desc()).offset(offset).limit(limit).all()
    logger.info(f"Retrieved {len(observations)} observations")
    return observations

# Endpoints: Workflows
@app.post("/store_workflow", response_model=WorkflowResponse, status_code=201)
async def store_workflow(
    request: WorkflowRequest,
    db: Session = Depends(get_db)
):
    """Store a new learned workflow from analysis."""
    try:
        wf = Workflow(
            pattern_text=request.pattern_text,
            steps_json=request.steps_json
        )
        db.add(wf)
        db.commit()
        db.refresh(wf)
        logger.info(f"Stored workflow {wf.id}: {request.pattern_text[:50]}...")
        return wf
    except Exception as e:
        logger.error(f"Store workflow failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to store")

@app.get("/get_workflows", response_model=List[WorkflowResponse])
async def get_workflows(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    min_runs: Optional[int] = Query(None, description="Filter by run_count >= min_runs"),
    db: Session = Depends(get_db)
):
    """Get paginated workflows, optional filter by runs."""
    query = db.query(Workflow)
    if min_runs:
        query = query.filter(Workflow.run_count >= min_runs)
    workflows = query.order_by(Workflow.created_at.desc()).offset(offset).limit(limit).all()
    logger.info(f"Retrieved {len(workflows)} workflows")
    return workflows

@app.post("/increment_workflow_run/{workflow_id}", response_model=WorkflowResponse)
async def increment_workflow_run(
    workflow_id: int,
    db: Session = Depends(get_db)
):
    """Increment run_count after successful automation (for learning)."""
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    wf.run_count += 1
    db.commit()
    db.refresh(wf)
    logger.info(f"Incremented run_count for workflow {workflow_id} to {wf.run_count}")
    return wf

# Purge Endpoint
@app.post("/purge_old", response_model=PurgeResponse)
async def purge_old(
    request: PurgeRequest,
    db: Session = Depends(get_db)
):
    """Purge old observations and stable workflows for storage optimization."""
    days = request.days_old or DAYS_OLD
    stable = request.stable_runs or STABLE_RUNS
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Purge old observations
    deleted_obs = db.query(Observation).filter(
        Observation.timestamp < cutoff
    ).delete(synchronize_session=False)
    db.commit()

    # Purge stable workflows (high run_count, assume learned/stable)
    deleted_wf = db.query(Workflow).filter(
        Workflow.run_count >= stable
    ).delete(synchronize_session=False)
    db.commit()

    logger.info(f"Purged {deleted_obs} old observations and {deleted_wf} stable workflows")
    return PurgeResponse(
        deleted_observations=deleted_obs,
        deleted_workflows=deleted_wf,
        message=f"Purged data older than {days} days and workflows with >= {stable} runs"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)