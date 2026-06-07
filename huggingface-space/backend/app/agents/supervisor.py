"""
Supervisor Agent - delegates routing to central LLM intent router.
"""
import logging
from typing import Dict, Any, Literal, List
from .state import AgentState
from .intent_router import (
    route_user_intent,
    validate_routing_decision,
    apply_routing_to_state,
)

logger = logging.getLogger(__name__)


def _compute_workflow_flags(state: AgentState) -> Dict[str, Any]:
    tests_recommended = state.get("tests_recommended") or []
    xray_available = state.get("xray_available", False)
    spirometry_available = state.get("spirometry_available", False)
    cbc_available = state.get("cbc_available", False)
    missing_tests = state.get("missing_tests") or []

    pending_tests: List[str] = []
    if tests_recommended:
        for t in tests_recommended:
            if t == "xray" and not xray_available and "xray" not in missing_tests:
                pending_tests.append("xray")
            if t == "spirometry" and not spirometry_available and "spirometry" not in missing_tests:
                pending_tests.append("spirometry")
            if t == "cbc" and not cbc_available and "cbc" not in missing_tests:
                pending_tests.append("cbc")

    test_collection_complete = len(pending_tests) == 0 and bool(tests_recommended)

    return {
        "patient_confirmed": state.get("patient_data_confirmed", False),
        "emergency_detected": state.get("emergency_flag", False),
        "emergency_checked": state.get("emergency_checked", False),
        "doctor_note_ready": state.get("doctor_note") is not None,
        "tests_recommended": tests_recommended,
        "pending_tests": pending_tests,
        "test_collection_complete": test_collection_complete,
        "xray_available": xray_available,
        "spirometry_available": spirometry_available,
        "cbc_available": cbc_available,
        "treatment_plan_ready": bool(state.get("treatment_plan")),
        "treatment_approved": state.get("treatment_approved", False),
        "dosage_calculated": state.get("calculated_dosages") is not None,
        "final_report_ready": state.get("final_report") is not None,
        "history_saved": state.get("history_saved", False),
    }


def _rule_based_routing(state: AgentState, flags: Dict[str, Any] = None) -> str:
    from .intent_router import _rule_based_routing as rule_route
    if flags is None:
        flags = _compute_workflow_flags(state)
    return rule_route(state, flags)


_fallback_routing = _rule_based_routing


def supervisor_agent(state: AgentState) -> AgentState:
    state["current_step"] = "supervisor"
    flags = _compute_workflow_flags(state)
    state["test_collection_complete"] = flags["test_collection_complete"]

    if state.get("redirect_to_test_collector"):
        state["redirect_to_test_collector"] = False
        state["test_collection_complete"] = False
        state["treatment_plan"] = None
        state["diagnosis"] = None
        state["next_step"] = "test_collector"
        logger.info("Supervisor: test_collector (redirect flag)")
        return state

    decision = route_user_intent(state, flags)
    apply_routing_to_state(state, decision)

    next_agent = validate_routing_decision(decision, flags, state)

    if flags.get("pending_tests"):
        state["test_collection_complete"] = False

    state["next_step"] = next_agent
    logger.info(
        f"Supervisor: {next_agent} | intent={decision.get('user_intent')} | {decision.get('reason')}"
    )
    return state


def check_supervisor_routing(state: AgentState) -> Literal[
    "emergency_detector",
    "doctor_note_generator",
    "test_collector",
    "rag_treatment_planner",
    "treatment_approval",
    "dosage_calculator",
    "report_generator",
    "history_saver",
    "end"
]:
    next_step = state.get("next_step", "end")
    valid_steps = {
        "emergency_detector": "emergency_detector",
        "doctor_note_generator": "doctor_note_generator",
        "test_collector": "test_collector",
        "rag_treatment_planner": "rag_treatment_planner",
        "treatment_approval": "treatment_approval",
        "dosage_calculator": "dosage_calculator",
        "report_generator": "report_generator",
        "history_saver": "history_saver",
        "end": "end",
    }
    return valid_steps.get(next_step.lower(), "end")
