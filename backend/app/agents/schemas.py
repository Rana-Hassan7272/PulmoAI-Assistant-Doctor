"""
Pydantic schemas for agent LLM output validation and state initialization.

Provides structured validation with safe defaults for:
- PatientExtraction: LLM patient data coercion (str→int age, str→bool smoker)
- RAGTreatmentPlanOutput: normalizes diagnosis/treatment from nested LLM JSON
- DosageOutput: validates dosage calc responses with safe defaults
- AgentStateValidator: mirrors AgentState TypedDict for safe state construction
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, field_validator, model_validator


# ---------------------------------------------------------------------------
# PatientExtraction
# ---------------------------------------------------------------------------

class PatientExtraction(BaseModel):
    """Validates and coerces LLM-extracted patient data."""

    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    weight: Optional[float] = None
    smoker: Optional[bool] = None
    symptoms: Optional[str] = None
    duration: Optional[str] = None
    history: Optional[str] = None
    occupation: Optional[str] = None

    @field_validator("age", mode="before")
    @classmethod
    def coerce_age(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    @field_validator("weight", mode="before")
    @classmethod
    def coerce_weight(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    @field_validator("smoker", mode="before")
    @classmethod
    def coerce_smoker(cls, v: Any) -> Optional[bool]:
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("yes", "true", "1")
        try:
            return bool(v)
        except (TypeError, ValueError):
            return None


# ---------------------------------------------------------------------------
# RAGTreatmentPlanOutput
# ---------------------------------------------------------------------------

class RAGTreatmentPlanOutput(BaseModel):
    """Normalizes LLM treatment plan JSON — handles nested dicts/lists."""

    diagnosis: str = "Diagnosis pending"
    treatment_plan: List[str] = []
    home_remedies: List[str] = []
    followup_instruction: str = "Follow up as needed"

    @field_validator("diagnosis", mode="before")
    @classmethod
    def flatten_diagnosis(cls, v: Any) -> str:
        if v is None:
            return "Diagnosis pending"
        if isinstance(v, dict):
            return v.get("primary_diagnosis") or str(v)
        return str(v)

    @field_validator("followup_instruction", mode="before")
    @classmethod
    def flatten_followup(cls, v: Any) -> str:
        if v is None:
            return "Follow up as needed"
        if isinstance(v, dict):
            return ". ".join(f"{k}: {val}" for k, val in v.items())
        if isinstance(v, list):
            return ". ".join(str(i) for i in v)
        return str(v)

    @field_validator("treatment_plan", "home_remedies", mode="before")
    @classmethod
    def flatten_list(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            return [str(v)]
        result = []
        for item in v:
            if isinstance(item, dict):
                if "activity" in item and "description" in item:
                    result.append(f"{item['activity']}: {item['description']}")
                else:
                    result.append(". ".join(f"{k}: {val}" for k, val in item.items()))
            else:
                result.append(str(item))
        return result


# ---------------------------------------------------------------------------
# DosageOutput
# ---------------------------------------------------------------------------

class DosageOutput(BaseModel):
    """Validates LLM dosage calculation responses with safe defaults."""

    dose: str = "As prescribed"
    frequency: str = "As directed"
    with_food: Optional[bool] = None
    notes: str = "Please follow your healthcare provider's instructions"
    calculation: str = "Standard dosing"

    @field_validator("dose", "frequency", "notes", "calculation", mode="before")
    @classmethod
    def coerce_str(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)

    @field_validator("with_food", mode="before")
    @classmethod
    def coerce_with_food(cls, v: Any) -> Optional[bool]:
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("true", "yes", "1")
        try:
            return bool(v)
        except (TypeError, ValueError):
            return None


# ---------------------------------------------------------------------------
# AgentStateValidator
# ---------------------------------------------------------------------------

class AgentStateValidator(BaseModel):
    """
    Mirrors AgentState TypedDict — provides safe default construction.

    Usage:
        state = AgentStateValidator(patient_id=1, visit_id="abc").to_agent_state()
    """

    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    patient_smoker: Optional[bool] = None
    patient_chronic_conditions: Optional[str] = None
    patient_occupation: Optional[str] = None

    visit_id: str = ""
    symptoms: Optional[str] = None
    symptom_duration: Optional[str] = None
    patient_weight: Optional[float] = None
    vitals: Optional[Dict[str, Any]] = None

    emergency_flag: bool = False
    emergency_reason: Optional[str] = None
    emergency_checked: bool = False

    doctor_note: Optional[str] = None

    xray_result: Optional[Dict[str, Any]] = None
    xray_available: bool = False
    spirometry_result: Optional[Dict[str, Any]] = None
    spirometry_available: bool = False
    cbc_result: Optional[Dict[str, Any]] = None
    cbc_available: bool = False

    missing_tests: List[str] = []
    tests_collected: List[str] = []
    tests_skipped: List[str] = []
    test_collector_findings: Optional[str] = None

    rag_context: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment_plan: Optional[List[str]] = None
    tests_recommended: List[str] = []
    home_remedies: List[str] = []
    followup_instruction: Optional[str] = None

    previous_visits: List[Dict[str, Any]] = []
    progress_summary: Optional[str] = None
    patient_history_summary: Optional[str] = None

    conversation_history: List[Dict[str, str]] = []

    current_step: Optional[str] = None
    message: Optional[str] = None

    patient_data_confirmed: bool = False
    treatment_approved: bool = False
    treatment_modifications: Optional[str] = None

    calculated_dosages: Optional[Dict[str, Any]] = None

    error_count: int = 0
    workflow_error: Optional[str] = None

    next_step: Optional[str] = None
    test_collection_complete: bool = False
    visit_summary: Optional[str] = None
    history_saved: bool = False

    @model_validator(mode="before")
    @classmethod
    def generate_visit_id(cls, values: Any) -> Any:
        if isinstance(values, dict) and not values.get("visit_id"):
            values["visit_id"] = str(uuid.uuid4())
        return values

    def to_agent_state(self) -> Dict[str, Any]:
        """Return a plain dict compatible with AgentState TypedDict."""
        return self.model_dump()
