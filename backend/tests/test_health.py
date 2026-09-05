from fastapi.testclient import TestClient
from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_websocket_manual_analysis() -> None:
    with TestClient(app).websocket_connect("/ws/live-analysis") as ws:
        started = ws.receive_json()
        assert started["type"] == "session_started"
        ws.send_json({"type": "manual_transcript", "text": "This is your bank. Tell me the OTP immediately."})
        update = ws.receive_json()
        assert update["type"] == "analysis_update"
        assert update["context"]["otp_request"] is True
        assert update["policy_decision"] == "BLOCK / ESCALATE"
