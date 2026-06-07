"""
Test Collector Agent - handles test collection with LLM intent parsing + ML processing.
"""
import json
import re
import logging
from typing import Dict, Any, Optional, List
from .state import AgentState
from .config import call_groq_llm
from ..ml_models.spirometry.featurizer import predict_spirometry, predict_spirometry_proba
from ..ml_models.bloodcount_report.feature import predict_blood_disease

logger = logging.getLogger(__name__)


def _pending_tests(state: AgentState, recommended: List[str]) -> List[str]:
    missing = state.get("missing_tests", [])
    pending = []
    for test in recommended:
        if test == "xray" and not state.get("xray_available") and "xray" not in missing:
            pending.append("xray")
        elif test == "spirometry" and not state.get("spirometry_available") and "spirometry" not in missing:
            pending.append("spirometry")
        elif test == "cbc" and not state.get("cbc_available") and "cbc" not in missing:
            pending.append("cbc")
    return pending


def _parse_test_actions_llm(state: AgentState, user_message: str, pending: List[str]) -> List[Dict[str, str]]:
    if not pending:
        return []

    messages = [
        {
            "role": "system",
            "content": (
                "You interpret patient messages during diagnostic test collection. "
                f"Pending tests: {', '.join(pending)}. "
                "Return JSON only: {\"actions\": [{\"type\": \"skip|show_form|prompt_upload\", \"test\": \"xray|cbc|spirometry\"}]}. "
                "Examples: "
                "'skip xray give spirometry form' -> skip xray + show_form spirometry. "
                "'give xray' or 'xray form' -> prompt_upload xray (X-ray uses image upload, not a form). "
                "'skip' alone -> skip the first pending test. "
                "'give cbc form' -> show_form cbc. "
                "Only use tests from the pending list."
            ),
        },
        {"role": "user", "content": user_message},
    ]

    try:
        raw = call_groq_llm(messages, temperature=0.0, json_mode=True)
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
            clean = clean.split("```")[0].strip()
        data = json.loads(clean)
        actions = data.get("actions", [])
        valid = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            atype = str(action.get("type", "")).lower()
            test = str(action.get("test", "")).lower().replace("x-ray", "xray")
            if atype in ("skip", "show_form", "prompt_upload") and test in ("xray", "cbc", "spirometry"):
                if test in pending or atype == "skip":
                    valid.append({"type": atype, "test": test})
        return valid
    except Exception as e:
        logger.warning(f"LLM test intent parse failed: {e}")
        return _parse_test_actions_fallback(user_message, pending)


def _parse_test_actions_fallback(message: str, pending: List[str]) -> List[Dict[str, str]]:
    msg = message.lower().replace("spiromtery", "spirometry").replace("x-ray", "xray")
    actions: List[Dict[str, str]] = []

    for test in ("xray", "cbc", "spirometry"):
        if test not in msg:
            continue
        if "skip" in msg and test in pending:
            actions.append({"type": "skip", "test": test})
        elif test == "xray" and test in pending:
            actions.append({"type": "prompt_upload", "test": "xray"})
        elif "form" in msg or "give" in msg or msg.strip() == test:
            if test in pending:
                actions.append({"type": "show_form" if test != "xray" else "prompt_upload", "test": test})

    if "skip" in msg and not any(a["type"] == "skip" for a in actions) and pending:
        actions.insert(0, {"type": "skip", "test": pending[0]})

    return actions


def _apply_skip(state: AgentState, test: str) -> None:
    missing = state.setdefault("missing_tests", [])
    if test not in missing:
        missing.append(test)


def _message_for_next_test(state: AgentState, next_test: str, ack: str = "") -> str:
    prefix = f"{ack} " if ack else ""
    if next_test == "xray":
        return (
            f"{prefix}Please upload your **X-ray image** using the 📎 attachment button below the chat, "
            "or say **'skip xray'** if you don't have one."
        )
    if next_test == "cbc":
        return (
            f"{prefix}Next, please provide your **CBC (Blood Test)** results. "
            "Say **'give cbc form'** for the form, or **'skip cbc'** to continue."
        )
    return (
        f"{prefix}Next, please provide your **Spirometry** results. "
        "Say **'give spirometry form'** for the form, or **'skip spirometry'** to continue."
    )


def test_collector_agent(state: AgentState) -> AgentState:
    state["current_step"] = "test_collector"
    state["show_spirometry_form_modal"] = False
    state["show_cbc_form_modal"] = False

    conversation = state.get("conversation_history", [])
    last_message = conversation[-1].get("content", "") if conversation else ""

    recommended = state.get("tests_recommended") or ["xray", "cbc", "spirometry"]
    state["tests_recommended"] = recommended

    just_collected = None

    if "x-ray image uploaded" in last_message.lower() or "[x-ray image uploaded" in last_message.lower():
        if state.get("xray_available"):
            just_collected = "X-ray"

    if not state.get("spirometry_available"):
        spirom_data = _extract_spirometry_from_conversation(conversation)
        if spirom_data:
            result = _call_spirometry_ml_api_tool(spirom_data, state.get("patient_age"), state.get("patient_gender"))
            if result:
                state["spirometry_available"] = True
                state["spirometry_result"] = result
                just_collected = "Spirometry"
    elif "spirometry test results submitted" in last_message.lower():
        just_collected = "Spirometry"

    if not state.get("cbc_available"):
        cbc_data = _extract_cbc_from_conversation(conversation)
        if cbc_data:
            result = _call_cbc_ml_api_tool(cbc_data, state.get("patient_age"), state.get("patient_gender"))
            if result:
                state["cbc_available"] = True
                state["cbc_result"] = result
                just_collected = "CBC"
    elif "cbc test results submitted" in last_message.lower():
        just_collected = "CBC"

    pending = _pending_tests(state, recommended)
    if not pending:
        return _structure_final_output(state)

    actions = _parse_test_actions_llm(state, last_message, pending)

    for action in actions:
        atype = action["type"]
        test = action["test"]
        if atype == "skip":
            _apply_skip(state, test)
        elif atype == "show_form" and test == "spirometry" and "spirometry" in pending:
            state["show_spirometry_form_modal"] = True
            state["message"] = (
                "I've opened the **Spirometry Form**. Enter FEV1 and FVC from your report, then submit."
            )
            return state
        elif atype == "show_form" and test == "cbc" and "cbc" in pending:
            state["show_cbc_form_modal"] = True
            state["message"] = (
                "I've opened the **CBC Form**. Enter your blood count values, then submit."
            )
            return state
        elif atype == "prompt_upload" and test == "xray" and "xray" in pending:
            state["message"] = (
                "Please upload your **X-ray image** using the 📎 attachment button below the chat, "
                "or say **'skip xray'** if you don't have one."
            )
            return state

    pending = _pending_tests(state, recommended)
    if not pending:
        ack = f"Thank you for providing the {just_collected}." if just_collected else ""
        return _structure_final_output(state, ack=ack)

    if just_collected:
        state["message"] = _message_for_next_test(state, pending[0], f"Thank you for providing the {just_collected}.")
        return state

    state["message"] = _message_for_next_test(state, pending[0])
    return state


def _extract_cbc_from_conversation(conversation: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    last_message = conversation[-1].get("content", "") if conversation else ""

    def safe_float(match: Optional[re.Match]) -> Optional[float]:
        if not match:
            return None
        try:
            groups = match.groups()
            val = groups[-1] if len(groups) > 1 else groups[0]
            return float(val)
        except (TypeError, ValueError):
            return None

    patterns = {
        "WBC": re.search(r"wbc[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
        "RBC": re.search(r"rbc[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
        "HGB": re.search(r"(hgb|hemoglobin)[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
        "HCT": re.search(r"(hct|hematocrit)[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
        "PLT": re.search(r"(plt|platelets)[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
        "MCV": re.search(r"mcv[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
        "MCH": re.search(r"mch[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
        "MCHC": re.search(r"mchc[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
        "LYMp": re.search(r"lymp[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
        "NEUTp": re.search(r"neutp[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
        "LYMn": re.search(r"lymn[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
        "NEUTn": re.search(r"neutn[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
        "PDW": re.search(r"pdw[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
        "PCT": re.search(r"pct[:\s=]+([\d.]+)", last_message, re.IGNORECASE),
    }

    if any(patterns.values()):
        return {k: safe_float(v) for k, v in patterns.items()}
    return None


def _extract_spirometry_from_conversation(conversation: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    last_message = conversation[-1].get("content", "") if conversation else ""
    fev1_match = re.search(r"fev1[:\s=]+([\d.]+)", last_message, re.IGNORECASE)
    fvc_match = re.search(r"fvc[:\s=]+([\d.]+)", last_message, re.IGNORECASE)

    if fev1_match and fvc_match:
        return {"fev1": float(fev1_match.group(1)), "fvc": float(fvc_match.group(1))}
    return None


def _call_cbc_ml_api_tool(cbc_data: Dict[str, Any], age, gender) -> Optional[Dict[str, Any]]:
    try:
        input_data = {
            "WBC": float(cbc_data.get("WBC") or 7.0),
            "LYMp": float(cbc_data.get("LYMp") or 30.0),
            "NEUTp": float(cbc_data.get("NEUTp") or 60.0),
            "LYMn": float(cbc_data.get("LYMn") or 2.0),
            "NEUTn": float(cbc_data.get("NEUTn") or 4.0),
            "RBC": float(cbc_data.get("RBC") or 4.5),
            "HGB": float(cbc_data.get("HGB") or 14.0),
            "HCT": float(cbc_data.get("HCT") or 42.0),
            "MCV": float(cbc_data.get("MCV") or 90.0),
            "MCH": float(cbc_data.get("MCH") or 30.0),
            "MCHC": float(cbc_data.get("MCHC") or 33.0),
            "PLT": float(cbc_data.get("PLT") or 250.0),
            "PDW": float(cbc_data.get("PDW") or 12.0),
            "PCT": float(cbc_data.get("PCT") or 0.2),
        }
        prediction = predict_blood_disease(input_data)
        return {
            "input_values": input_data,
            "prediction": {
                "disease_name": prediction.get("disease_name", "Unknown"),
                "confidence": float(prediction.get("confidence", 0.0)),
            },
        }
    except Exception as e:
        logger.error(f"CBC ML call failed: {e}")
        return None


def _call_spirometry_ml_api_tool(spirometry_data: Dict[str, Any], age, gender) -> Optional[Dict[str, Any]]:
    try:
        fev1 = float(spirometry_data["fev1"])
        fvc = float(spirometry_data["fvc"])
        ratio = fev1 / fvc if fvc > 0 else 0.0

        input_data = {
            "sex": "Male" if str(gender).lower().startswith("m") else "Female",
            "age": float(age or 45),
            "fev1": fev1,
            "fvc": fvc,
            "fev1_fvc": ratio,
            "height": 170.0,
            "weight": 70.0,
            "bmi": 24.0,
            "race": "White",
        }
        predictions = predict_spirometry(input_data)
        probabilities = predict_spirometry_proba(input_data)

        pattern = "Normal"
        confidence = 0.0
        active_diseases = [k for k, v in predictions.items() if v == 1]

        if active_diseases:
            max_p = 0.0
            best_d = "Normal"
            for d in active_diseases:
                if probabilities.get(d, 0.0) > max_p:
                    max_p = probabilities[d]
                    best_d = d.capitalize()
            pattern = best_d
            confidence = max_p
        else:
            max_disease_p = max(probabilities.values()) if probabilities else 0.0
            confidence = 1.0 - max_disease_p

        confidence = min(max(confidence, 0.01), 0.999)

        return {
            "input_values": input_data,
            "pattern": pattern,
            "severity": "Normal" if pattern == "Normal" else "Mild",
            "confidence": float(confidence),
            "prediction": {"pattern": pattern, "confidence": float(confidence)},
        }
    except Exception as e:
        logger.error(f"Spirometry ML call failed: {e}")
        return None


def _structure_final_output(state: AgentState, ack: str = "") -> AgentState:
    results = []
    if state.get("xray_available") and state.get("xray_result"):
        p = state["xray_result"].get("prediction", {})
        results.append(f"X-ray: {p.get('disease_name')} ({p.get('confidence', 0):.1%})")
    if state.get("spirometry_available") and state.get("spirometry_result"):
        res = state["spirometry_result"]
        conf = res.get("confidence", res.get("prediction", {}).get("confidence", 0))
        results.append(f"Spirometry: {res.get('pattern')} ({conf:.1%})")
    if state.get("cbc_available") and state.get("cbc_result"):
        p = state["cbc_result"].get("prediction", {})
        results.append(f"CBC: {p.get('disease_name')} ({p.get('confidence', 0):.1%})")

    missing = state.get("missing_tests", [])
    if missing:
        results.append(f"Skipped: {', '.join(missing)}")

    test_summary = "\n".join(results) if results else "No tests submitted."
    intro = f"{ack}\n\n" if ack else ""
    state["message"] = (
        f"{intro}**All requested tests are complete.**\n\n"
        f"**Results:**\n{test_summary}\n\n"
        "I'm now preparing your diagnosis and treatment plan..."
    )
    state["test_collection_complete"] = True
    state["test_collector_findings"] = test_summary
    return state
