"""
End-to-end integration tests for the diagnostic workflow.

Covers:
  - Full session: intake → confirm → emergency → doctor note → tests → RAG → approval → dosage → report
  - 9 Pydantic schema unit tests (PatientExtraction, RAGTreatmentPlanOutput, DosageOutput, AgentStateValidator)
  - WebSocket connection and message exchange
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.agents.schemas import (
    AgentStateValidator,
    DosageOutput,
    PatientExtraction,
    RAGTreatmentPlanOutput,
)


# ===========================================================================
# Schema unit tests
# ===========================================================================

class TestPatientExtraction:
    def test_basic_extraction(self):
        data = {"name": "Alice", "age": 30, "gender": "Female", "smoker": False}
        p = PatientExtraction.model_validate(data)
        assert p.name == "Alice"
        assert p.age == 30
        assert p.smoker is False

    def test_age_coercion_from_string(self):
        p = PatientExtraction.model_validate({"age": "25"})
        assert p.age == 25

    def test_age_coercion_invalid_returns_none(self):
        p = PatientExtraction.model_validate({"age": "unknown"})
        assert p.age is None

    def test_smoker_coercion_yes_string(self):
        p = PatientExtraction.model_validate({"smoker": "yes"})
        assert p.smoker is True

    def test_smoker_coercion_no_string(self):
        p = PatientExtraction.model_validate({"smoker": "no"})
        assert p.smoker is False

    def test_weight_coercion_from_string(self):
        p = PatientExtraction.model_validate({"weight": "70.5"})
        assert p.weight == 70.5

    def test_all_none_defaults(self):
        p = PatientExtraction.model_validate({})
        assert p.name is None
        assert p.age is None
        assert p.smoker is None


class TestRAGTreatmentPlanOutput:
    def test_flat_strings(self):
        data = {
            "diagnosis": "Pneumonia",
            "treatment_plan": ["Rest", "Antibiotics"],
            "home_remedies": ["Hydration"],
            "followup_instruction": "Follow up in 7 days",
        }
        r = RAGTreatmentPlanOutput.model_validate(data)
        assert r.diagnosis == "Pneumonia"
        assert r.treatment_plan == ["Rest", "Antibiotics"]

    def test_diagnosis_from_dict(self):
        data = {"diagnosis": {"primary_diagnosis": "COPD"}}
        r = RAGTreatmentPlanOutput.model_validate(data)
        assert r.diagnosis == "COPD"

    def test_treatment_plan_with_dicts(self):
        data = {
            "treatment_plan": [
                {"activity": "Rest", "description": "Complete bed rest"},
                "Drink fluids",
            ]
        }
        r = RAGTreatmentPlanOutput.model_validate(data)
        assert "Rest: Complete bed rest" in r.treatment_plan
        assert "Drink fluids" in r.treatment_plan

    def test_followup_from_list(self):
        data = {"followup_instruction": ["Return in 1 week", "Blood test"]}
        r = RAGTreatmentPlanOutput.model_validate(data)
        assert "Return in 1 week" in r.followup_instruction

    def test_defaults_on_empty(self):
        r = RAGTreatmentPlanOutput.model_validate({})
        assert r.diagnosis == "Diagnosis pending"
        assert r.treatment_plan == []
        assert r.followup_instruction == "Follow up as needed"


class TestDosageOutput:
    def test_valid_response(self):
        data = {
            "dose": "500mg",
            "frequency": "twice daily",
            "with_food": True,
            "notes": "Take with water",
            "calculation": "Standard adult dose",
        }
        d = DosageOutput.model_validate(data)
        assert d.dose == "500mg"
        assert d.with_food is True

    def test_safe_defaults_on_empty(self):
        d = DosageOutput.model_validate({})
        assert d.dose == "As prescribed"
        assert d.frequency == "As directed"
        assert d.with_food is None

    def test_with_food_coercion(self):
        d = DosageOutput.model_validate({"with_food": "yes"})
        assert d.with_food is True


class TestAgentStateValidator:
    def test_generates_visit_id_when_missing(self):
        s = AgentStateValidator(patient_id=1)
        assert s.visit_id != ""

    def test_preserves_provided_visit_id(self):
        s = AgentStateValidator(patient_id=1, visit_id="custom-123")
        assert s.visit_id == "custom-123"

    def test_to_agent_state_returns_dict(self):
        state = AgentStateValidator(patient_id=42).to_agent_state()
        assert isinstance(state, dict)
        assert state["patient_id"] == 42
        assert state["emergency_flag"] is False
        assert state["history_saved"] is False
        assert state["conversation_history"] == []


# ===========================================================================
# E2E REST API tests
# ===========================================================================

MOCK_LLM_GREETING = "Hello! Please tell me your name, age, gender, weight, and symptoms."
MOCK_LLM_EXTRACT = json.dumps({
    "name": "John Doe",
    "age": 35,
    "gender": "Male",
    "weight": 75,
    "smoker": False,
    "symptoms": "cough and fever",
    "duration": "3 days",
    "history": "None",
    "occupation": "Engineer",
})
MOCK_DOCTOR_NOTE = "35-year-old male with productive cough and fever for 3 days. Suspect bacterial pneumonia."
MOCK_RAG_PLAN = json.dumps({
    "diagnosis": "Bacterial Pneumonia",
    "treatment_plan": ["Amoxicillin 500mg twice daily for 7 days", "Rest for 5 days"],
    "home_remedies": ["Steam inhalation", "Drink 2L water daily"],
    "followup_instruction": "Return in 7 days for reassessment",
})
MOCK_DOSAGE = json.dumps({
    "dose": "500mg",
    "frequency": "twice daily",
    "with_food": True,
    "notes": "Take with food",
    "calculation": "Standard adult dose",
})
MOCK_REPORT = "FINAL REPORT: John Doe, 35M. Diagnosis: Bacterial Pneumonia. Treatment: Amoxicillin."


@pytest.fixture
def mock_llm():
    """Mock call_groq_llm to return deterministic responses."""
    call_count = {"n": 0}
    responses = [
        MOCK_LLM_GREETING,   # 0: intake greeting
        MOCK_LLM_EXTRACT,    # 1: patient data extraction
        "end",               # 2: supervisor (after intake confirm)
        "false|",            # 3: emergency check → no emergency
        MOCK_DOCTOR_NOTE,    # 4: doctor note
        "xray cbc spirometry",  # 5: recommend tests (not used directly)
        MOCK_RAG_PLAN,       # 6: RAG treatment
        "treatment_approval",  # 7: supervisor → treatment approval
        MOCK_DOSAGE,         # 8: dosage calc
        MOCK_REPORT,         # 9: report
    ]

    def side_effect(messages, **kwargs):
        idx = call_count["n"] % len(responses)
        call_count["n"] += 1
        return responses[idx]

    with patch("app.agents.config.call_groq_llm", side_effect=side_effect):
        yield


@pytest.mark.usefixtures("mock_llm")
class TestDiagnosticE2E:
    def test_start_diagnostic_session(self, client, auth_headers):
        """Starting a session returns a greeting message."""
        response = client.post("/diagnostic/start", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["visit_id"] is not None

    def test_send_patient_info(self, client, auth_headers):
        """Sending patient info returns an extraction/confirmation step."""
        start = client.post("/diagnostic/start", headers=auth_headers)
        assert start.status_code == 200
        visit_id = start.json()["visit_id"]

        response = client.post(
            "/diagnostic/chat",
            headers=auth_headers,
            json={
                "message": "My name is John Doe, 35 years old, male, 75kg, non-smoker. I have cough and fever for 3 days.",
                "visit_id": visit_id,
            },
        )
        assert response.status_code == 200
        assert "message" in response.json()

    def test_confirm_patient_data(self, client, auth_headers):
        """Confirming patient data advances the workflow."""
        start = client.post("/diagnostic/start", headers=auth_headers)
        visit_id = start.json()["visit_id"]

        client.post(
            "/diagnostic/chat",
            headers=auth_headers,
            json={"message": "John Doe, 35, Male, 75kg, non-smoker, cough and fever", "visit_id": visit_id},
        )

        confirm = client.post(
            "/diagnostic/chat",
            headers=auth_headers,
            json={"message": "yes, that is correct", "visit_id": visit_id},
        )
        assert confirm.status_code == 200


# ===========================================================================
# WebSocket tests
# ===========================================================================

class TestDiagnosticWebSocket:
    def test_ws_rejects_without_auth(self, client):
        """WebSocket should close if auth message is not the first message."""
        with client.websocket_connect("/diagnostic/ws") as ws:
            ws.send_json({"type": "chat", "message": "hello"})
            data = ws.receive_json()
            assert data["type"] == "error"

    def test_ws_rejects_invalid_token(self, client):
        """WebSocket should close with error on bad JWT."""
        with client.websocket_connect("/diagnostic/ws") as ws:
            ws.send_json({"type": "auth", "token": "invalid.token.here"})
            data = ws.receive_json()
            assert data["type"] == "error"

    def test_ws_auth_ok_and_greeting(self, client, auth_headers, auth_token):
        """Authenticated WS connection receives an auth_ok then a greeting."""
        with patch("app.agents.config.call_groq_llm", return_value=MOCK_LLM_GREETING):
            with patch("app.fastapi_routers.ws_diagnostic._get_graph") as mock_graph:
                mock_result = AgentStateValidator(patient_id=1).to_agent_state()
                mock_result["message"] = MOCK_LLM_GREETING
                mock_result["current_step"] = "patient_intake_waiting_input"
                mock_graph.return_value.invoke.return_value = mock_result

                with client.websocket_connect("/diagnostic/ws") as ws:
                    ws.send_json({"type": "auth", "token": auth_token})
                    auth_resp = ws.receive_json()
                    assert auth_resp["type"] == "auth_ok"
                    assert "visit_id" in auth_resp

                    greeting = ws.receive_json()
                    assert greeting["type"] == "stream_end"
                    assert "message" in greeting
