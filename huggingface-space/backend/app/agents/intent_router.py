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


def normalize_clinical_text(text: str, kind: str = "symptoms") -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text.strip())
    fixes = {
        "throught": "throat", "caugh": "cough", "brething": "breathing",
        "spiromtery": "spirometry", "alergy": "allergy", "chestpain": "chest pain",
    }
    lower = t.lower()
    for wrong, right in fixes.items():
        if wrong in lower:
            t = re.sub(re.escape(wrong), right, t, flags=re.IGNORECASE)
    return t


def _is_test_command_message(message: str) -> bool:
    msg = message.lower()
    if not msg.strip():
        return False
    markers = (
        "skip", "xray", "x-ray", "cbc", "spiro", "cray", "upload", "form",
        "fev1", "fvc", "blood", "chest", "image uploaded", "submitted", "only",
    )
    return any(m in msg for m in markers)


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
                "You are a pulmonology assistant. Recommend the MINIMUM necessary tests "
                "from ONLY: xray, cbc, spirometry.\n"
                "Return JSON: {\"tests\": [\"...\"], \"reason\": \"...\"}\n\n"
                "Rules:\n"
                "- Return 1, 2, or 3 tests — never default to all three unless clinically justified.\n"
                "- Mild isolated cough/wheeze → often spirometry only.\n"
                "- Fever + cough/chest pain → often xray + cbc.\n"
                "- Infection suspicion without imaging need → cbc only possible.\n"
                "- Complex or unclear cases → 2-3 tests as needed.\n"
                "- Never return tests outside xray, cbc, spirometry."
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

    pattern_actions = _parse_test_actions_pattern(user_message, pending)
    if pattern_actions:
        return pattern_actions

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
    msg = (
        message.lower()
        .replace("spiromtery", "spirometry")
        .replace("x-ray", "xray")
        .replace("x ray", "xray")
        .replace("cray", "xray")
    )
    actions: List[Dict[str, str]] = []

    def add_action(atype: str, test: str) -> None:
        if test not in pending:
            return
        for a in actions:
            if a["test"] == test and a["type"] == atype:
                return
        actions.append({"type": atype, "test": test})

    skip_checks = [
        ("xray", (r"skip\s+(?:the\s+)?(?:xray|x-ray|x\s*ray|cray|chest\s*scan)",)),
        ("cbc", (r"skip\s+(?:the\s+)?(?:cbc|blood(?:\s*test)?)",)),
        ("spirometry", (r"skip\s+(?:the\s+)?(?:spirometry|spiro(?:metry)?)",)),
    ]
    for test, patterns in skip_checks:
        for pat in patterns:
            if re.search(pat, msg):
                add_action("skip", test)

    only_match = re.search(
        r"only\s+(?:(?:give|want|need)\s+)?(?:the\s+)?(xray|cbc|spirometry|spiro|cray|blood)",
        msg,
    )
    if only_match:
        only_test = _normalize_test_name(only_match.group(1))
        if only_test:
            for t in pending:
                if t != only_test:
                    add_action("skip", t)
            atype = "prompt_upload" if only_test == "xray" else "show_form"
            add_action(atype, only_test)
            return actions

    for test in ("xray", "cbc", "spirometry"):
        if test not in pending:
            continue
        mentioned = test in msg
        if test == "xray" and ("chest" in msg and "skip" not in msg.split("chest")[0][-10:]):
            mentioned = True
        if test == "cbc" and "blood" in msg:
            mentioned = True
        if test == "spirometry" and ("spiro" in msg or "fev" in msg):
            mentioned = True
        if not mentioned:
            continue
        if re.search(rf"skip\s+(?:the\s+)?{test}", msg) or (
            test == "xray" and re.search(r"skip\s+(?:the\s+)?(?:cray|xray)", msg)
        ):
            add_action("skip", test)
        elif ("form" in msg or "give" in msg) and test in msg:
            atype = "prompt_upload" if test == "xray" else "show_form"
            add_action(atype, test)
        elif test == "xray" and ("upload" in msg or "attach" in msg):
            add_action("prompt_upload", "xray")

    if "skip" in msg and not any(a["type"] == "skip" for a in actions) and pending:
        add_action("skip", pending[0])

    return actions


def parse_approval_intent(state: AgentState) -> Dict[str, Any]:
    last_msg = last_user_message(state)
    lower = last_msg.lower()
    if any(w in lower for w in ("yes", "approve", "accept", "proceed", "agreed", "looks good", "ok")):
        return {"intent": "approve", "reason": "pattern"}
    if any(w in lower for w in ("give", "upload", "form", "provide", "need", "want")) and any(
        t in lower for t in ("xray", "cbc", "spiro", "blood", "chest", "cray")
    ):
        return {"intent": "more_tests", "reason": "pattern"}

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

    return {"intent": "unclear", "reason": "pattern fallback"}


def route_user_intent(state: AgentState, flags: Dict[str, Any]) -> Dict[str, Any]:
    last_msg = last_user_message(state)
    pending = flags.get("pending_tests") or []

    if pending and _is_test_command_message(last_msg):
        actions = _parse_test_actions_pattern(last_msg, pending)
        if actions:
            logger.info(f"Fast-path test_collector: {actions}")
            return {
                "next_agent": "test_collector",
                "user_intent": "test_command",
                "test_actions": actions,
                "clear_treatment_plan": False,
                "reason": "fast-path test command",
            }

    if pending:
        return {
            "next_agent": "test_collector",
            "user_intent": "pending_tests",
            "test_actions": _parse_test_actions_pattern(last_msg, pending) if last_msg else [],
            "clear_treatment_plan": False,
            "reason": "pending tests must be collected first",
        }

    if flags.get("treatment_plan_ready") and not flags.get("treatment_approved"):
        lower = last_msg.lower()
        wants_tests = any(w in lower for w in ("give", "upload", "form", "provide", "want", "need", "more test"))
        if wants_tests and _is_test_command_message(last_msg):
            return {
                "next_agent": "test_collector",
                "user_intent": "more_tests",
                "test_actions": [],
                "clear_treatment_plan": True,
                "reason": "user requested more tests during treatment review",
            }

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
    test_actions = _parse_test_actions_pattern(last_msg, pending) if pending else []
    return {
        "next_agent": agent,
        "user_intent": "fallback",
        "test_actions": test_actions,
        "clear_treatment_plan": False,
        "reason": "rule-based fallback after LLM failure",
    }


def validate_routing_decision(decision: Dict[str, Any], flags: Dict[str, Any], state: AgentState) -> str:
    agent = decision.get("next_agent", "end")

    if flags.get("pending_tests"):
        return "test_collector"

    if agent == "emergency_detector" and flags["emergency_checked"]:
        agent = "doctor_note_generator" if not flags["doctor_note_ready"] else "test_collector"

    if agent == "rag_treatment_planner" and not flags["doctor_note_ready"]:
        agent = "doctor_note_generator"

    if agent == "rag_treatment_planner" and flags.get("pending_tests"):
        agent = "test_collector"

    if agent == "rag_treatment_planner" and flags["treatment_plan_ready"]:
        if not flags["treatment_approved"]:
            agent = "treatment_approval"
        elif not flags["dosage_calculated"]:
            agent = "dosage_calculator"
        else:
            agent = "end"

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
        state["force_treatment_regen"] = True

    actions = decision.get("test_actions") or []
    if actions:
        state["pending_test_actions"] = actions

    intent = decision.get("user_intent", "")
    state["last_user_intent"] = intent
