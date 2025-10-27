from sqlalchemy import Column, Integer, String, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Observation(Base):
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    type = Column(String(20), nullable=False)  # 'screen' or 'audio'
    json_data = Column(JSON, nullable=False)  # OCR/STT output
    clip_path = Column(String(500), nullable=True)  # Optional file path

    __table_args__ = (
        Index('ix_observations_timestamp', 'timestamp'),
        Index('ix_observations_type', 'type'),
    )

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    pattern_text = Column(String(1000), nullable=False)  # e.g., "Open Excel and save report"
    steps_json = Column(JSON, nullable=False)  # [{"step": "click", "element": "File > Save"}]
    run_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index('ix_workflows_created_at', 'created_at'),
        Index('ix_workflows_pattern_text', 'pattern_text'),
    )

# For future: Patterns table if separate, but merged into workflows for MVP