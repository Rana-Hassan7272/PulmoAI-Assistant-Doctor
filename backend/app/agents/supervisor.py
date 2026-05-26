"""
Supervisor Agent - Master Orchestrator

LLM-first routing with rule-based safety net:
- _llm_routing()          : calls LLM first (temperature=0.0)
- _validate_llm_decision(): checks hard safety constraints, overrides if violated
- _rule_based_routing()   : deterministic fallback used when LLM fails
- _compute_workflow_flags(): extracts all flags into a reusable dict
"""
import logging
from typing import Dict, Any, Literal, Optional
from .state import AgentState
from .config import call_groq_llm

logger = logging.getLogger(__name__)


def _compute_workflow_flags(state: AgentState) -> Dict[str, Any]:
    """Extract all workflow flags from state into a single reusable dict."""
    tests_recommended = state.get("tests_recommended") or []
    xray_available = state.get("xray_available", False)
    spirometry_available = state.get("spirometry_available", False)
    cbc_available = state.get("cbc_available", False)
    missing_tests = state.get("missing_tests") or []

    test_collection_complete = state.get("test_collection_complete", False)
    if tests_recommended:
        all_accounted = True
        for t in tests_recommended:
            if t == "xray" and not xray_available and "xray" not in missing_tests:
                all_accounted = False
            if t == "spirometry" and not spirometry_available and "spirometry" not in missing_tests:
                all_accounted = False
            if t == "cbc" and not cbc_available and "cbc" not in missing_tests:
                all_accounted = False
        if not all_accounted:
            test_collection_complete = False
        elif test_collection_complete:
            pass
        else:
            test_collection_complete = True

    return {
        "patient_confirmed": state.get("patient_data_confirmed", False),
        "emergency_detected": state.get("emergency_flag", False),
        "emergency_checked": state.get("emergency_checked", False),
        "doctor_note_ready": state.get("doctor_note") is not None,
        "tests_recommended": tests_recommended,
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


def _llm_routing(state: AgentState, flags: Dict[str, Any]) -> str:
    """Call LLM to decide next agent. Returns agent name string."""
    workflow_context = f"""
Current Workflow State:
- Patient confirmed: {flags['patient_confirmed']}
- Emergency detected: {flags['emergency_detected']}
- Emergency checked: {flags['emergency_checked']}
- Doctor note ready: {flags['doctor_note_ready']}
- Tests recommended: {flags['tests_recommended']}
- Tests complete: {flags['test_collection_complete']}
  - X-ray available: {flags['xray_available']}
  - Spirometry available: {flags['spirometry_available']}
  - CBC available: {flags['cbc_available']}
- Treatment plan ready: {flags['treatment_plan_ready']}
- Treatment approved: {flags['treatment_approved']}
- Dosage calculated: {flags['dosage_calculated']}
- Final report ready: {flags['final_report_ready']}
- History saved: {flags['history_saved']}
"""
    messages = [
        {
            "role": "system",
            "content": """You are a Supervisor Agent that orchestrates a medical diagnostic workflow.
Return ONLY the agent name (e.g., "test_collector") with no explanation.

Workflow sequence (STRICT):
1. emergency_detector  (only if emergency_checked=False)
2. doctor_note_generator
3. test_collector      (only if tests recommended and not complete)
4. rag_treatment_planner (only after tests complete)
5. treatment_approval
6. dosage_calculator
7. report_generator
8. history_saver       (only if final_report exists and history_saved=False)
9. END""",
        },
        {
            "role": "user",
            "content": f"{workflow_context}\nWhich agent should run next? Return only the agent name.",
        },
    ]
    response = call_groq_llm(messages, temperature=0.0)
    return response.strip().lower().replace('"', "").replace("'", "").split()[0]


def _validate_llm_decision(decision: str, flags: Dict[str, Any], state: AgentState) -> str:
    """Check hard safety constraints and override LLM decision if violated."""
    if decision == "emergency_detector" and flags["emergency_checked"]:
        logger.warning("Supervisor: LLM wanted emergency_detector but already checked — overriding")
        return "doctor_note_generator"

    if decision == "rag_treatment_planner" and not flags["doctor_note_ready"]:
        logger.warning("Supervisor: LLM skipped doctor_note_generator — overriding")
        return "doctor_note_generator"

    if decision == "rag_treatment_planner" and flags["tests_recommended"] and not flags["test_collection_complete"]:
        logger.warning("Supervisor: LLM skipped test_collector — overriding")
        return "test_collector"

    if decision == "history_saver" and flags["history_saved"]:
        logger.warning("Supervisor: LLM wanted history_saver but already saved — overriding to end")
        return "end"

    if decision == "history_saver" and not flags["final_report_ready"]:
        logger.warning("Supervisor: LLM wanted history_saver without final report — overriding to report_generator")
        return "report_generator"

    return decision


def _rule_based_routing(state: AgentState, flags: Optional[Dict[str, Any]] = None) -> str:
    """Deterministic fallback routing — enforces strict linear workflow."""
    if flags is None:
        flags = _compute_workflow_flags(state)

    if not flags["emergency_checked"]:
        logger.info("Supervisor: routing to emergency_detector")
        return "emergency_detector"

    if flags["emergency_detected"]:
        if not flags["history_saved"]:
            logger.info("Supervisor: emergency detected, routing to history_saver")
            return "history_saver"
        logger.info("Supervisor: emergency saved, routing to end")
        return "end"

    if not flags["doctor_note_ready"]:
        logger.info("Supervisor: routing to doctor_note_generator")
        return "doctor_note_generator"

    tests_recommended = flags["tests_recommended"]
    if tests_recommended and not flags["test_collection_complete"]:
        logger.info("Supervisor: routing to test_collector")
        return "test_collector"

    if not flags["treatment_plan_ready"]:
        if tests_recommended and not flags["test_collection_complete"]:
            logger.info("Supervisor: blocking RAG — tests not complete")
            return "test_collector"
        logger.info("Supervisor: routing to rag_treatment_planner")
        return "rag_treatment_planner"

    if flags["treatment_plan_ready"] and not flags["treatment_approved"]:
        logger.info("Supervisor: routing to treatment_approval")
        return "treatment_approval"

    if flags["treatment_approved"] and not flags["dosage_calculated"]:
        logger.info("Supervisor: routing to dosage_calculator")
        return "dosage_calculator"

    if not flags["final_report_ready"]:
        logger.info("Supervisor: routing to report_generator")
        return "report_generator"

    if not flags["history_saved"]:
        logger.info("Supervisor: routing to history_saver")
        return "history_saver"

    if not state.get("progress_summary") and state.get("previous_visits"):
        logger.info("Supervisor: routing to followup_agent")
        return "followup_agent"

    logger.info("Supervisor: workflow complete, routing to end")
    return "end"


# Alias so any legacy code referencing _fallback_routing still works
_fallback_routing = _rule_based_routing


def supervisor_agent(state: AgentState) -> AgentState:
    """
    Supervisor Agent — LLM-first routing with rule-based safety net.
    """
    state["current_step"] = "supervisor"
    flags = _compute_workflow_flags(state)
    state["test_collection_complete"] = flags["test_collection_complete"]

    next_agent = "end"
    try:
        llm_decision = _llm_routing(state, flags)
        logger.info(f"Supervisor: LLM decision = '{llm_decision}'")
        next_agent = _validate_llm_decision(llm_decision, flags, state)
        if next_agent != llm_decision:
            logger.info(f"Supervisor: overridden to '{next_agent}'")
    except Exception as exc:
        logger.warning(f"Supervisor: LLM routing failed ({exc}), using rule-based fallback")
        next_agent = _rule_based_routing(state, flags)

    state["next_step"] = next_agent
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
    """
    Routing function for supervisor conditional edges.
    
    Returns:
        Next agent to call based on supervisor decision
    """
    next_step = state.get("next_step", "end")
    
    # Map to valid routing options
    valid_steps = {
        "emergency_detector": "emergency_detector",
        "doctor_note_generator": "doctor_note_generator",
        "test_collector": "test_collector",
        "rag_treatment_planner": "rag_treatment_planner",
        "treatment_approval": "treatment_approval",
        "dosage_calculator": "dosage_calculator",
        "report_generator": "report_generator",
        "history_saver": "history_saver",
        "end": "end"
    }
    
    return valid_steps.get(next_step.lower(), "end")

