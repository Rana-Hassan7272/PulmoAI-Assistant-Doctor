"""
Central LLM intent router for the diagnostic workflow.

Primary: LLM understands user message + workflow state → next agent + actions.
Fallback: deterministic rules only when LLM fails.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from .config import call_groq_llm
from .state import AgentState

logger = logging.getLogger(__name__)

ALLOWED_TESTS = ("xray", "cbc", "spirometry")
VALID_AGENTS = {
    "emergency_detector",
    "doctor_note_generator",
    "test_collector",
    "rag_treatment_planner",
    "treatment_approval",
    "dosage_calculator",
    "report_generator",
    "history_saver",
    "end",
}


def _parse_json_llm(raw: str) -> Dict[str, Any]:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("```", 1)[1]
        if clean.startswith("json"):
            clean = clean[4:]
        clean = clean.split("```", 1)[0].strip()
    return json.loads(clean)


def last_user_message(state: AgentState) -> str:
    for msg in reversed(state.get("conversation_history", [])):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


def _conversation_snippet(state: AgentState, n: int = 6) -> str:
    lines = []
    for msg in state.get("conversation_history", [])[-n:]:
        role = msg.get("role", "?")
        content = str(msg.get("content", ""))[:300]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _normalize_test_name(name: str) -> Optional[str]:
    n = name.lower().strip().replace("x-ray", "xray").replace("spiromtery", "spirometry")
    if n in ALLOWED_TESTS:
        return n
    if "xray" in n or "x ray" in n or "chest" in n and "imag" in n:
        return "xray"
    if "cbc" in n or "blood" in n:
        return "cbc"
    if "spiro" in n or "fev1" in n or "fvc" in n or "lung function" in n:
        return "spirometry"
    return None


def _sanitize_test_list(tests: Any) -> List[str]:
    if not isinstance(tests, list):
        return []
    out: List[str] = []
    for t in tests:
        norm = _normalize_test_name(str(t))
        if norm and norm not in out:
            out.append(norm)
    return out


def recommend_tests_llm(state: AgentState) -> List[str]:
    symptoms = state.get("symptoms") or ""
    age = state.get("patient_age")
    gender = state.get("patient_gender")
    note = state.get("doctor_note") or ""

    messages = [
        {
            "role": "system",
            "content": (
                "You are a pulmonology assistant. Choose which diagnostic tests to recommend "
                "from ONLY these three options: xray, cbc, spirometry.\n"
                "Return JSON: {\"tests\": [\"xray\", \"cbc\", \"spirometry\"], \"reason\": \"...\"}\n"
                "Pick 1-3 tests based on clinical need. You may recommend all three when appropriate.\n"
                "Never return tests outside xray, cbc, spirometry."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Patient: {age}yo {gender}\n"
                f"Symptoms: {symptoms}\n"
                f"Duration: {state.get('symptom_duration')}\n"
                f"Clinical note: {note[:400]}"
            ),
        },
    ]

    try:
        raw = call_groq_llm(messages, temperature=0.1, json_mode=True)
        data = _parse_json_llm(raw)
        tests = _sanitize_test_list(data.get("tests", []))
        if tests:
            order = ["xray", "cbc", "spirometry"]
            tests.sort(key=lambda t: order.index(t) if t in order else 99)
            logger.info(f"LLM recommended tests: {tests} — {data.get('reason', '')}")
            return tests
    except Exception as exc:
        logger.warning(f"LLM test recommendation failed: {exc}")

    from .tools import recommend_tests
    return recommend_tests(symptoms, age, gender)


def parse_test_actions(user_message: str, pending: List[str]) -> List[Dict[str, str]]:
    if not pending or not user_message.strip():
        return []

    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "Interpret the patient message during pulmonary diagnostic test collection.\n"
                    f"Pending tests (not yet done/skipped): {', '.join(pending)}\n"
                    "Available tests ONLY: xray (image upload), cbc (blood form), spirometry (lung form).\n\n"
                    "Return JSON:\n"
                    '{"actions": [{"type": "skip|show_form|prompt_upload", "test": "xray|cbc|spirometry"}]}\n\n'
                    "Rules:\n"
                    "- xray always uses prompt_upload (patient uploads image, no form)\n"
                    "- cbc and spirometry use show_form when patient wants to enter values\n"
                    "- Handle typos: spiromtery, x ray, blood test, chest scan, lung test\n"
                    "- Mixed intents: 'skip xray give cbc' → two actions\n"
                    "- 'skip' alone → skip first pending test\n"
                    "- If message says image uploaded / xray uploaded → no action needed (empty actions)\n"
                    "- Only use tests from the pending list"
                ),
            },
            {"role": "user", "content": user_message},
        ]
        raw = call_groq_llm(messages, temperature=0.0, json_mode=True)
        data = _parse_json_llm(raw)
        valid: List[Dict[str, str]] = []
        for action in data.get("actions", []):
            if not isinstance(action, dict):
                continue
            atype = str(action.get("type", "")).lower()
            test = _normalize_test_name(str(action.get("test", "")))
            if not test or atype not in ("skip", "show_form", "prompt_upload"):
                continue
            if atype == "skip" or test in pending:
                if test == "xray" and atype == "show_form":
                    atype = "prompt_upload"
                valid.append({"type": atype, "test": test})
        if valid:
            return valid
    except Exception as exc:
        logger.warning(f"LLM test action parse failed: {exc}")

    return _parse_test_actions_pattern(user_message, pending)


def _parse_test_actions_pattern(message: str, pending: List[str]) -> List[Dict[str, str]]:
    msg = message.lower().replace("spiromtery", "spirometry").replace("x-ray", "xray")
    actions: List[Dict[str, str]] = []

    for test in ("xray", "cbc", "spirometry"):
        if test not in pending:
            continue
        mentioned = test in msg
        if test == "xray" and ("x ray" in msg or "chest" in msg):
            mentioned = True
        if test == "cbc" and "blood" in msg:
            mentioned = True
        if test == "spirometry" and ("spiro" in msg or "fev" in msg):
            mentioned = True
        if not mentioned:
            continue
        if "skip" in msg:
            actions.append({"type": "skip", "test": test})
        elif test == "xray":
            actions.append({"type": "prompt_upload", "test": "xray"})
        elif "form" in msg or "give" in msg or msg.strip() == test:
            actions.append({"type": "show_form", "test": test})

    if "skip" in msg and not any(a["type"] == "skip" for a in actions) and pending:
        actions.insert(0, {"type": "skip", "test": pending[0]})

    return actions


def parse_approval_intent(state: AgentState) -> Dict[str, Any]:
    last_msg = last_user_message(state)
    context = _conversation_snippet(state, 4)

    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "Classify patient intent during treatment plan review.\n"
                    "Return JSON:\n"
                    '{"intent": "approve|reject|more_tests|question|unclear", "reason": "..."}\n'
                    "approve = agrees to treatment plan\n"
                    "reject = wants changes to plan (not asking for tests)\n"
                    "more_tests = wants xray/cbc/spirometry before approving\n"
                    "question = asking about medications/diagnosis/plan\n"
                    "Handle typos and informal language."
                ),
            },
            {"role": "user", "content": f"Recent chat:\n{context}\n\nLatest message: {last_msg}"},
        ]
        raw = call_groq_llm(messages, temperature=0.0, json_mode=True)
        data = _parse_json_llm(raw)
        intent = str(data.get("intent", "unclear")).lower()
        if intent in ("approve", "reject", "more_tests", "question", "unclear"):
            return data
    except Exception as exc:
        logger.warning(f"LLM approval intent failed: {exc}")

    lower = last_msg.lower()
    if any(w in lower for w in ("yes", "approve", "accept", "proceed", "agreed", "looks good", "ok")):
        return {"intent": "approve", "reason": "pattern fallback"}
    if any(w in lower for w in ("xray", "cbc", "spiro", "upload", "form", "test", "skip")):
        return {"intent": "more_tests", "reason": "pattern fallback"}
    return {"intent": "unclear", "reason": "pattern fallback"}


def route_user_intent(state: AgentState, flags: Dict[str, Any]) -> Dict[str, Any]:
    last_msg = last_user_message(state)
    context = _conversation_snippet(state, 8)

    workflow = (
        f"patient_confirmed={flags['patient_confirmed']}\n"
        f"emergency_checked={flags['emergency_checked']}\n"
        f"emergency_detected={flags['emergency_detected']}\n"
        f"doctor_note_ready={flags['doctor_note_ready']}\n"
        f"tests_recommended={flags['tests_recommended']}\n"
        f"pending_tests={flags['pending_tests']}\n"
        f"tests_complete={flags['test_collection_complete']}\n"
        f"xray_done={flags['xray_available']}\n"
        f"cbc_done={flags['cbc_available']}\n"
        f"spirometry_done={flags['spirometry_available']}\n"
        f"treatment_plan_ready={flags['treatment_plan_ready']}\n"
        f"treatment_approved={flags['treatment_approved']}\n"
        f"dosage_calculated={flags['dosage_calculated']}\n"
        f"final_report_ready={flags['final_report_ready']}\n"
        f"history_saved={flags['history_saved']}\n"
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are the master intent router for a pulmonology diagnostic chatbot.\n"
                "Read workflow state + conversation + latest user message.\n"
                "Understand typos, informal language, and mixed intents.\n\n"
                "Return JSON only:\n"
                "{\n"
                '  "next_agent": "emergency_detector|doctor_note_generator|test_collector|'
                'rag_treatment_planner|treatment_approval|dosage_calculator|report_generator|'
                'history_saver|end",\n'
                '  "user_intent": "short label",\n'
                '  "test_actions": [{"type": "skip|show_form|prompt_upload", "test": "xray|cbc|spirometry"}],\n'
                '  "clear_treatment_plan": false,\n'
                '  "reason": "one sentence"\n'
                "}\n\n"
                "Agents:\n"
                "- emergency_detector: first safety check only if emergency_checked=false\n"
                "- doctor_note_generator: need clinical assessment (no doctor_note yet)\n"
                "- test_collector: user providing/skipping tests OR pending tests remain after partial collection\n"
                "- rag_treatment_planner: all recommended tests done/skipped, no treatment plan yet\n"
                "- treatment_approval: treatment plan shown, user reviewing (not requesting more tests)\n"
                "- dosage_calculator: treatment approved, need dosages\n"
                "- report_generator: need final report\n"
                "- history_saver: save completed visit\n"
                "- end: wait for user input, nothing to process now\n\n"
                "Tests available ONLY: xray (image upload), cbc (form), spirometry (form).\n"
                "If user wants more tests during treatment approval → test_collector + clear_treatment_plan=true.\n"
                "If user just uploaded/submitted one test and others pending → test_collector.\n"
                "Never route to rag_treatment_planner while pending_tests is non-empty.\n"
                "Never route to doctor_note_generator if doctor_note already exists."
            ),
        },
        {
            "role": "user",
            "content": f"Workflow state:\n{workflow}\n\nConversation:\n{context}\n\nLatest user message:\n{last_msg}",
        },
    ]

    try:
        raw = call_groq_llm(messages, temperature=0.0, json_mode=True)
        data = _parse_json_llm(raw)
        agent = str(data.get("next_agent", "end")).lower().strip()
        agent = agent.split()[0] if agent else "end"
        if agent not in VALID_AGENTS:
            raise ValueError(f"invalid agent {agent}")
        data["next_agent"] = agent
        data["test_actions"] = data.get("test_actions") or []
        data["clear_treatment_plan"] = bool(data.get("clear_treatment_plan", False))
        logger.info(f"Intent router: {agent} | {data.get('user_intent')} | {data.get('reason')}")
        return data
    except Exception as exc:
        logger.warning(f"LLM intent router failed, using rule fallback: {exc}")
        return _route_user_intent_fallback(state, flags, last_msg)


def _rule_based_routing(state: AgentState, flags: Dict[str, Any]) -> str:
    if not flags["emergency_checked"]:
        return "emergency_detector"
    if flags["emergency_detected"]:
        return "history_saver" if not flags["history_saved"] else "end"
    if not flags["doctor_note_ready"]:
        return "doctor_note_generator"
    if flags.get("pending_tests"):
        return "test_collector"
    if not flags["treatment_plan_ready"]:
        return "rag_treatment_planner"
    if flags["treatment_plan_ready"] and not flags["treatment_approved"]:
        return "treatment_approval"
    if flags["treatment_approved"] and not flags["dosage_calculated"]:
        return "dosage_calculator"
    if not flags["final_report_ready"]:
        return "report_generator"
    if not flags["history_saved"]:
        return "history_saver"
    return "end"


def _route_user_intent_fallback(
    state: AgentState, flags: Dict[str, Any], last_msg: str
) -> Dict[str, Any]:
    agent = _rule_based_routing(state, flags)
    pending = flags.get("pending_tests") or []
    test_actions = parse_test_actions(last_msg, pending) if pending else []
    return {
        "next_agent": agent,
        "user_intent": "fallback",
        "test_actions": test_actions,
        "clear_treatment_plan": False,
        "reason": "rule-based fallback after LLM failure",
    }


def validate_routing_decision(decision: Dict[str, Any], flags: Dict[str, Any], state: AgentState) -> str:
    agent = decision.get("next_agent", "end")

    if agent == "emergency_detector" and flags["emergency_checked"]:
        agent = "doctor_note_generator" if not flags["doctor_note_ready"] else "test_collector"

    if agent == "rag_treatment_planner" and not flags["doctor_note_ready"]:
        agent = "doctor_note_generator"

    if agent == "rag_treatment_planner" and flags.get("pending_tests"):
        agent = "test_collector"

    if agent == "doctor_note_generator" and flags["doctor_note_ready"]:
        if flags.get("pending_tests"):
            agent = "test_collector"
        elif not flags["treatment_plan_ready"]:
            agent = "rag_treatment_planner"
        elif not flags["treatment_approved"]:
            agent = "treatment_approval"
        elif not flags["dosage_calculated"]:
            agent = "dosage_calculator"
        elif not flags["final_report_ready"]:
            agent = "report_generator"
        elif not flags["history_saved"]:
            agent = "history_saver"
        else:
            agent = "end"

    if agent == "history_saver" and flags["history_saved"]:
        agent = "end"
    if agent == "history_saver" and not flags["final_report_ready"]:
        agent = "report_generator"

    if flags.get("pending_tests") and agent in ("rag_treatment_planner", "treatment_approval", "dosage_calculator"):
        if decision.get("test_actions") or decision.get("clear_treatment_plan"):
            agent = "test_collector"

    return agent


def apply_routing_to_state(state: AgentState, decision: Dict[str, Any]) -> None:
    if decision.get("clear_treatment_plan"):
        state["treatment_plan"] = None
        state["diagnosis"] = None
        state["home_remedies"] = []
        state["followup_instruction"] = None
        state["test_collection_complete"] = False

    actions = decision.get("test_actions") or []
    if actions:
        state["pending_test_actions"] = actions

    intent = decision.get("user_intent", "")
    state["last_user_intent"] = intent
