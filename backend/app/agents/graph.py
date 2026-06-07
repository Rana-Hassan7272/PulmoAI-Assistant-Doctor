"""
LangGraph Graph Setup for Pulmonologist Assistant
This sets up the main LangGraph workflow with all agent nodes.
"""
from typing import Literal, Optional, Dict, Any
import json
import os
import sqlite3
from langgraph.graph import StateGraph, END
from .state import AgentState
from langgraph.checkpoint.memory import MemorySaver

_CHECKPOINTER = None


def _get_checkpointer():
    global _CHECKPOINTER
    if _CHECKPOINTER is not None:
        return _CHECKPOINTER
    db_path = os.environ.get("CHECKPOINT_DB_PATH", "/tmp/langgraph_checkpoints.db")
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        conn = sqlite3.connect(db_path, check_same_thread=False)
        _CHECKPOINTER = SqliteSaver(conn)
    except Exception:
        _CHECKPOINTER = MemorySaver()
    return _CHECKPOINTER

from .patient_intake import patient_intake_agent
from .emergency_detector import emergency_detector_agent
from .test_collector import test_collector_agent
from .supervisor import supervisor_agent, check_supervisor_routing
from .config import call_groq_llm
from .tools import format_test_results_for_llm, calculate_dosage_tool, generate_final_report_tool, summarize_report_tool, generate_visit_id_tool, save_to_db_tool


def create_diagnostic_graph():
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("patient_intake", patient_intake_agent)
    workflow.add_node("emergency_detector", emergency_detector_agent)
    workflow.add_node("supervisor", supervisor_agent)
    workflow.add_node("doctor_note_generator", doctor_note_generator_agent)
    workflow.add_node("test_collector", test_collector_agent)
    workflow.add_node("rag_specialist", rag_specialist_agent)
    workflow.add_node("treatment_approval", treatment_approval_agent)
    workflow.add_node("report_generator", report_generator_agent) # Now handles dosages too
    workflow.add_node("history_saver", history_saver_agent)
    workflow.add_node("followup_agent", followup_agent)
    
    workflow.set_entry_point("patient_intake")
    
    # Edges
    workflow.add_conditional_edges("patient_intake", check_patient_confirmation, {"awaiting_confirmation": END, "confirmed": "emergency_detector", "error": END, "waiting": END})
    workflow.add_conditional_edges("emergency_detector", check_emergency, {"emergency": END, "continue": "supervisor"})
    
    # Supervisor routing - maps logical agent names to node names
    workflow.add_conditional_edges("supervisor", check_supervisor_routing, {
        "emergency_detector": "emergency_detector",
        "doctor_note_generator": "doctor_note_generator",
        "test_collector": "test_collector",
        "rag_treatment_planner": "rag_specialist",
        "treatment_approval": "treatment_approval",
        "dosage_calculator": "report_generator", 
        "report_generator": "report_generator",
        "history_saver": "history_saver",
        "end": END
    })
    
    workflow.add_edge("doctor_note_generator", END)
    workflow.add_conditional_edges("test_collector", check_test_collection_complete, {
        "awaiting_tests": END,
        "awaiting_rag": "rag_specialist",
    })
    workflow.add_conditional_edges("rag_specialist", check_treatment_approval, {"awaiting_approval": END, "approved": "supervisor"})
    workflow.add_conditional_edges("treatment_approval", check_treatment_approval, {
        "awaiting_approval": END,
        "approved": "report_generator",
        "more_tests": "supervisor",
    })
    
    workflow.add_edge("report_generator", "history_saver")
    workflow.add_edge("history_saver", "followup_agent")
    workflow.add_edge("followup_agent", END)
    
    return workflow.compile(checkpointer=_get_checkpointer())


def _recover_doctor_note_from_conversation(conversation: list) -> str:
    for msg in reversed(conversation or []):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        if "clinical assessment" in content.lower():
            parts = content.split("**Clinical Assessment:**", 1)
            if len(parts) > 1:
                note_part = parts[1].split("Based on this", 1)[0].strip()
                if note_part:
                    return note_part
    return ""


def doctor_note_generator_agent(state: AgentState) -> AgentState:
    from .intent_router import recommend_tests_llm

    if state.get("doctor_note"):
        if not state.get("tests_recommended"):
            state["tests_recommended"] = recommend_tests_llm(state)
        return state

    recovered_note = _recover_doctor_note_from_conversation(state.get("conversation_history", []))
    if recovered_note:
        state["doctor_note"] = recovered_note
        if not state.get("tests_recommended"):
            from .patient_intake import _recover_tests_from_conversation
            recovered_tests = _recover_tests_from_conversation(state.get("conversation_history", []))
            state["tests_recommended"] = recovered_tests or recommend_tests_llm(state)
        return state

    test_results_text = format_test_results_for_llm(state)

    prompt = (
        f"Patient: {state.get('patient_age')}yo {state.get('patient_gender')}. "
        f"Symptoms: {state.get('symptoms')} for {state.get('symptom_duration')}. "
        f"History: {state.get('patient_chronic_conditions')}. "
        f"Test Results so far: {test_results_text}. "
        "Generate a 2-sentence clinical assessment note."
    )
    note = call_groq_llm([{"role": "user", "content": prompt}], temperature=0.2)
    state["doctor_note"] = note

    state["tests_recommended"] = recommend_tests_llm(state)
    tests = state["tests_recommended"]
    if len(tests) == 1:
        rec_text = tests[0].upper()
        rec_line = f"I recommend **{rec_text}** for your symptoms."
    else:
        rec_text = ", ".join([t.upper() for t in tests])
        rec_line = f"I recommend: **{rec_text}**."
    state["message"] = (
        f"**Clinical Assessment:**\n{note}\n\n"
        f"Based on this, {rec_line} "
        "Say **give form** or **skip** for any test you cannot provide."
    )
    return state


def rag_specialist_agent(state: AgentState) -> AgentState:
    from .tools import rag_treatment_planner_tool

    if state.get("treatment_plan") and not state.get("force_treatment_regen"):
        state["message"] = state.get("message") or (
            "Your treatment plan is ready. Please review it and let me know if you approve."
        )
        return state

    result = rag_treatment_planner_tool(state)
    state["diagnosis"] = result["diagnosis"]
    state["treatment_plan"] = result["treatment_plan"]
    state["home_remedies"] = result["home_remedies"]
    state["followup_instruction"] = result["followup_instruction"]
    
    # Build a natural, user-friendly message
    message_parts = [f"Based on your clinical assessment and test results, I've prepared a treatment plan for you.\n\n**Diagnosis:** {state['diagnosis']}\n"]
    
    # Treatment plan in natural language
    if state.get("treatment_plan"):
        message_parts.append("**Treatment Plan:**")
        for i, treatment in enumerate(state['treatment_plan'], 1):
            message_parts.append(f"{i}. {treatment}")
    
    # Home remedies in natural language
    if state.get("home_remedies"):
        message_parts.append("\n**Home Care Recommendations:**")
        for remedy in state['home_remedies']:
            message_parts.append(f"• {remedy}")
    
    # Follow-up instructions
    if state.get("followup_instruction"):
        message_parts.append(f"\n**Follow-up:** {state['followup_instruction']}")
    
    message_parts.append("\nPlease review this plan and let me know if you approve it. If you have any questions about the medications or treatment, I'm here to help!")
    
    state["message"] = "\n".join(message_parts)
    state["force_treatment_regen"] = False
    return state


def treatment_approval_agent(state: AgentState) -> AgentState:
    from .intent_router import parse_approval_intent

    history = state.get("conversation_history", [])
    if not history:
        return state

    result = parse_approval_intent(state)
    intent = result.get("intent", "unclear")

    if intent == "approve":
        state["treatment_approved"] = True
        state["message"] = "Processing your approval and generating the final report..."
    elif intent == "more_tests":
        state["redirect_to_test_collector"] = True
        state["test_collection_complete"] = False
        state["force_treatment_regen"] = True
        state["treatment_plan"] = None
        state["diagnosis"] = None
        state["message"] = (
            "Understood — let's continue with your tests. "
            "You can upload an **X-ray**, open the **CBC** or **Spirometry** form, or **skip** any test."
        )
    elif intent == "reject":
        state["message"] = "What would you like to change in the treatment plan? Describe your concerns."
    elif intent == "question":
        state["message"] = (
            "That's a good question. Please share any concerns about the plan, "
            "or say **approve** to proceed, or tell me if you need more tests (X-ray, CBC, Spirometry)."
        )
    else:
        state["message"] = (
            "Please **approve** the treatment plan, ask a question, request more tests, "
            "or tell me what you'd like to change."
        )
    return state


def report_generator_agent(state: AgentState) -> AgentState:
    """Unified step for Dosages and Final Report to prevent timeout hangs."""
    state["current_step"] = "report_generator"
    
    # 1. Calculate Dosages
    dose_result = calculate_dosage_tool(state)
    state["calculated_dosages"] = dose_result.get("dosages", {})
    
    # 2. Generate Final Report
    report_result = generate_final_report_tool(state)
    state["final_report"] = report_result["report"]
    state["message"] = report_result["report"]
    return state


def history_saver_agent(state: AgentState) -> AgentState:
    """Saves the visit to the DB. Prevents duplicates."""
    if state.get("history_saved"): return state
    
    # Create summary for DB
    summary_res = summarize_report_tool(state)
    # Ensure visit_id is set
    if not state.get("visit_id"):
        vid_res = generate_visit_id_tool(state)
        state["visit_id"] = vid_res["visit_id"]
        
    # Save
    save_res = save_to_db_tool(state, summary_res.get("summary", "Visit completed."))
    if save_res["status"] == "success":
        state["history_saved"] = True
        print(f"DEBUG: Visit {state['visit_id']} saved successfully.")
    return state


def followup_agent(state: AgentState) -> AgentState:
    """Compares current diagnosis/results with past visits."""
    if not state.get("previous_visits"): return state
    if state.get("progress_summary"): return state # Already done
    
    prompt = f"Current Diagnosis: {state.get('diagnosis')}. Previous History: {state.get('patient_history_summary')}. Compare them and provide a brief 2-sentence progress analysis for the patient."
    progress = call_groq_llm([{"role": "user", "content": prompt}])
    state["progress_summary"] = progress
    
    # Append to the final message
    if state.get("message"):
        state["message"] = f"{state['message']}\n\n**Progress Analysis:**\n{progress}"
    return state


# Conditional Edge Logic
def check_patient_confirmation(state):
    if state.get("patient_data_confirmed"): return "confirmed"
    if state.get("current_step") == "patient_intake_awaiting_confirmation": return "awaiting_confirmation"
    return "waiting"

def check_emergency(state):
    return "emergency" if state.get("emergency_flag") else "continue"

def check_treatment_approval(state):
    if state.get("redirect_to_test_collector"):
        state["redirect_to_test_collector"] = False
        return "more_tests"
    return "approved" if state.get("treatment_approved") else "awaiting_approval"

def check_test_collection_complete(state):
    if not state.get("test_collection_complete"):
        return "awaiting_tests"
    if state.get("auto_run_treatment_plan") and not state.get("treatment_plan"):
        state["auto_run_treatment_plan"] = False
        return "awaiting_rag"
    return "awaiting_tests"
