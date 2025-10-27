import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from models import Base, Observation, Workflow
from db_service import app, engine, SessionLocal, DAYS_OLD, STABLE_RUNS

# Use in-memory DB for tests
TEST_ENGINE = create_engine("sqlite:///:memory:")
TEST_SESSION = sessionmaker(bind=TEST_ENGINE)
Base.metadata.create_all(bind=TEST_ENGINE)

client = TestClient(app)

# Override dependency for tests
def get_test_db():
    db = TEST_SESSION()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[SessionLocal] = get_test_db

class TestDBService:
    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Reset DB per test."""
        Base.metadata.drop_all(bind=TEST_ENGINE)
        Base.metadata.create_all(bind=TEST_ENGINE)
        with TEST_ENGINE.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))

    def test_health(self):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "observations" in data["tables"]

    def test_store_get_observation(self):
        """Test store and get observation."""
        obs_data = {
            "type": "screen",
            "json_data": {"extracted_text": "Test", "actions": []},
            "clip_path": "/data/test.png"
        }
        # Store
        response = client.post("/store_observation", json=obs_data)
        assert response.status_code == 201
        stored = response.json()
        assert stored["type"] == "screen"
        assert stored["json_data"]["extracted_text"] == "Test"

        # Get
        get_resp = client.get("/get_observations?limit=1")
        assert get_resp.status_code == 200
        obs_list = get_resp.json()
        assert len(obs_list) == 1
        assert obs_list[0]["id"] == stored["id"]

    def test_store_observation_invalid_type(self):
        """Test invalid type."""
        invalid_data = {"type": "invalid", "json_data": {}}
        response = client.post("/store_observation", json=invalid_data)
        assert response.status_code == 400
        assert "must be 'screen' or 'audio'" in response.json()["detail"]

    def test_store_get_workflow(self):
        """Test store and get workflow."""
        wf_data = {
            "pattern_text": "Open Excel daily",
            "steps_json": [{"step": "click", "element": "Excel icon"}]
        }
        # Store
        response = client.post("/store_workflow", json=wf_data)
        assert response.status_code == 201
        stored = response.json()
        assert stored["pattern_text"] == "Open Excel daily"
        assert stored["run_count"] == 0

        # Get
        get_resp = client.get("/get_workflows?limit=1")
        assert get_resp.status_code == 200
        wf_list = get_resp.json()
        assert len(wf_list) == 1

    def test_increment_workflow_run(self):
        """Test increment run_count."""
        # Store first
        wf_data = {"pattern_text": "Test", "steps_json": {}}
        store_resp = client.post("/store_workflow", json=wf_data)
        wf_id = store_resp.json()["id"]

        # Increment
        response = client.post(f"/increment_workflow_run/{wf_id}")
        assert response.status_code == 200
        updated = response.json()
        assert updated["run_count"] == 1

    def test_increment_nonexistent_workflow(self):
        """Test increment on non-existent."""
        response = client.post("/increment_workflow_run/999")
        assert response.status_code == 404

    def test_purge_old(self):
        """Test purge: Mock old data."""
        # Store old observation (patch timestamp)
        with patch.object(datetime, 'utcnow', return_value=datetime.utcnow() - timedelta(days=8)):
            obs_data = {"type": "screen", "json_data": {}}
            client.post("/store_observation", json=obs_data)

        # Store stable workflow
        wf_data = {"pattern_text": "Test", "steps_json": {}}
        store_wf = client.post("/store_workflow", json=wf_data)
        wf_id = store_wf.json()["id"]
        # Simulate 6 runs
        for _ in range(6):
            client.post(f"/increment_workflow_run/{wf_id}")

        # Purge
        response = client.post("/purge_old", json={})
        assert response.status_code == 200
        purge_data = response.json()
        assert purge_data["deleted_observations"] == 1
        assert purge_data["deleted_workflows"] == 1

        # Verify deleted
        get_obs = client.get("/get_observations")
        assert len(get_obs.json()) == 0
        get_wf = client.get("/get_workflows")
        assert len(get_wf.json()) == 0

    def test_purge_no_data(self):
        """Test purge on empty DB."""
        response = client.post("/purge_old", json={})
        assert response.status_code == 200
        purge_data = response.json()
        assert purge_data["deleted_observations"] == 0
        assert purge_data["deleted_workflows"] == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])