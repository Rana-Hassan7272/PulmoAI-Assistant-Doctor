"""
Patient Intake Agent
Collects initial patient information and handles returning patients by loading history.
"""
import json
import re
import logging
from typing import Dict, Any, List, Union
from .state import AgentState
from .config import call_groq_llm
from .intent_router import normalize_clinical_text
from .tools import fetch_patient_history_tool, hydrate_agent_state_from_patient, save_patient_profile_tool
from ..core.error_handling import (
    LLMError, LLMInvalidResponseError, log_error_with_context
)
from .schemas import PatientExtraction

logger = logging.getLogger(__name__)

_TEST_ONLY_MESSAGES = {
    "cbc", "xray", "x-ray", "spirometry", "spiromtery",
    "give form", "form", "give cbc", "give xray", "give spirometry",
    "ok give cbc", "give me xray", "give me cbc",
}
_SYMPTOM_BLOCKLIST = {"cbc", "xray", "x-ray", "spirometry", "spiromtery", "form", "yes", "no"}


def _detect_smoker_from_text(text: str) -> Union[bool, None]:
    lower = text.lower()
    if re.search(r"\b(non[- ]?smok|never smoked|don't smoke|do not smoke|not a smoker)\b", lower):
        return False
    if re.search(
        r"\b(smok|smoking|smoker|cigarette|cigarettes|tobacco|vap(e|ing)|chain[- ]?smok)\b",
        lower,
    ):
        return True
    return None


def _normalize_extraction_dict(data: Any) -> Dict[str, Any]:
    if data is None:
        return {}
    if isinstance(data, PatientExtraction):
        return data.model_dump()
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        if not data:
            return {}
        merged: Dict[str, Any] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            for key, val in item.items():
                if val is None or val == "":
                    continue
                if key not in merged or merged[key] in (None, ""):
                    merged[key] = val
                elif key == "symptoms":
                    merged[key] = f"{merged[key]}, {val}"
        if merged:
            return merged
        if isinstance(data[0], dict):
            return data[0]
    return {}


def _safe_validate_extraction(
    data: Any,
    conversation: List[Dict[str, str]],
    symptoms_only: bool = False,
) -> PatientExtraction:
    normalized = _normalize_extraction_dict(data)
    try:
        return PatientExtraction.model_validate(normalized)
    except Exception:
        fallback = _extract_symptoms_fallback(conversation) if symptoms_only else _extract_basic_info_fallback(conversation)
        return PatientExtraction.model_validate(_normalize_extraction_dict(fallback))


def _last_user_message(conversation: List[Dict[str, str]]) -> str:
    for msg in reversed(conversation):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


def _capture_symptoms_directly(state: AgentState, conversation: List[Dict[str, str]]) -> bool:
    if state.get("symptoms"):
        return False
    last_user = _last_user_message(conversation)
    if not last_user or len(last_user.strip()) < 15:
        return False
    if _is_confirmation_message(last_user) or _is_workflow_action_message(last_user):
        return False
    state["symptoms"] = normalize_clinical_text(last_user.strip(), "symptoms")
    smoker_hint = _detect_smoker_from_text(last_user)
    if smoker_hint is not None:
        state["patient_smoker"] = smoker_hint
    duration_match = re.search(
        r"(?:for|lasting|last)\s+(\d+\s*(?:days?|weeks?|months?|hours?)|last few days)",
        last_user,
        re.IGNORECASE,
    )
    if duration_match:
        state["symptom_duration"] = duration_match.group(1).strip()
    return True


def _is_test_only_message(message: str) -> bool:
    return _is_workflow_action_message(message)


def _is_workflow_action_message(message: str) -> bool:
    msg = message.strip().lower()
    if msg in _TEST_ONLY_MESSAGES:
        return True
    keywords = ("skip", "xray", "x-ray", "cbc", "spirometry", "spiromtery", "form", "upload", "fev1", "fvc")
    return any(k in msg for k in keywords)


def _conversation_past_intake(conversation: List[Dict[str, str]]) -> bool:
    for msg in reversed(conversation):
        if msg.get("role") != "assistant":
            continue
        text = msg.get("content", "").lower()
        if "clinical assessment" in text:
            return True
        if "recommend" in text and any(t in text for t in ("xray", "cbc", "spirometry")):
            return True
    return False


def _recover_tests_from_conversation(conversation: List[Dict[str, str]]) -> List[str]:
    for msg in reversed(conversation):
        if msg.get("role") != "assistant":
            continue
        text = msg.get("content", "")
        upper = text.upper()
        if "RECOMMEND" not in upper:
            continue
        tests = []
        for token, name in (("XRAY", "xray"), ("CBC", "cbc"), ("SPIROMETRY", "spirometry")):
            if token in upper:
                tests.append(name)
        if tests:
            return tests
    return []


def _recover_symptoms_from_conversation(conversation: List[Dict[str, str]]) -> str:
    for msg in reversed(conversation):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            match = re.search(r"\*\*symptoms:\*\*\s*(.+)", content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    for msg in conversation:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        lower = content.lower()
        if _is_workflow_action_message(content) or _is_confirmation_message(content):
            continue
        if len(content.split()) >= 3 and any(
            kw in lower for kw in ("cough", "pain", "breath", "fever", "chest", "allergy", "mucus")
        ):
            return content.strip()
    return ""


def _should_bypass_intake(state: AgentState, last_msg: str) -> bool:
    if state.get("patient_data_confirmed"):
        return True
    if state.get("doctor_note"):
        return True
    if state.get("tests_recommended"):
        return True
    if state.get("test_collection_complete"):
        return True
    if state.get("treatment_plan"):
        return True
    if _is_workflow_action_message(last_msg):
        return True
    conversation = state.get("conversation_history", [])
    if _conversation_past_intake(conversation):
        return True
    return False


def _is_confirmation_message(message: str) -> bool:
    msg = message.lower().strip()
    if any(x in msg for x in ("not correct", "incorrect", "wrong", "change")):
        return False
    confirm_words = (
        "yes", "correct", "confirm", "confirmed", "right", "yep",
        "okay", "ok", "approve", "accurate", "that's right", "that is correct",
    )
    return any(word in msg for word in confirm_words)


def _last_assistant_asked_confirmation(conversation: List[Dict[str, str]]) -> bool:
    for msg in reversed(conversation[:-1]):
        if msg.get("role") == "assistant":
            text = msg.get("content", "").lower()
            return "confirm" in text and ("reply" in text or "review" in text)
    return False


def patient_intake_agent(state: AgentState) -> AgentState:
    previous_step = state.get("current_step")
    state["current_step"] = "patient_intake"

    hydrate_agent_state_from_patient(state)

    conversation = state.get("conversation_history", [])
    last_msg = conversation[-1]["content"] if conversation else ""
    last_msg_lower = last_msg.lower()

    if _should_bypass_intake(state, last_msg):
        if not state.get("symptoms"):
            recovered = _recover_symptoms_from_conversation(conversation)
            if recovered:
                state["symptoms"] = recovered
        if not state.get("tests_recommended"):
            recovered_tests = _recover_tests_from_conversation(conversation)
            if recovered_tests:
                state["tests_recommended"] = recovered_tests
        if _conversation_past_intake(conversation) and not state.get("emergency_checked"):
            state["emergency_checked"] = True
        state["patient_data_confirmed"] = True
        state["current_step"] = "patient_intake_complete"
        return state

    if state.get("returning_patient_profile") and state.get("patient_name") and state.get("patient_age") is not None:
        if _is_test_only_message(last_msg) or state.get("doctor_note"):
            state["patient_data_confirmed"] = True
            state["current_step"] = "patient_intake_complete"
            return state

    if state.get("patient_data_confirmed"):
        state["current_step"] = "patient_intake_complete"
        return state

    patient_id = state.get("patient_id")
    if patient_id and not state.get("patient_history_summary"):
        history_result = fetch_patient_history_tool(state)
        if history_result["status"] == "success" and history_result["visits"]:
            state["previous_visits"] = history_result["visits"]
            state["patient_history_summary"] = history_result["formatted_history"]

    if not conversation:
        if state.get("returning_patient_profile") and state.get("patient_name"):
            state["message"] = _generate_returning_greeting(state)
        else:
            state["message"] = _generate_greeting(state)
        state["current_step"] = "patient_intake_waiting_input"
        return state

    awaiting_confirm = (
        previous_step == "patient_intake_awaiting_confirmation"
        or _last_assistant_asked_confirmation(conversation)
    )
    if awaiting_confirm and _is_confirmation_message(last_msg_lower):
        state["patient_data_confirmed"] = True
        state["current_step"] = "patient_intake_complete"
        save_patient_profile_tool(state)
        logger.info("Patient data confirmed and saved to profile")
        return state

    if awaiting_confirm and (
        re.search(r"\b(no|wrong|incorrect)\b", last_msg_lower)
        or "not correct" in last_msg_lower
        or re.search(r"\bchange\b", last_msg_lower)
    ):
        state["message"] = "I'm sorry. Please tell me what information is incorrect."
        state["current_step"] = "patient_intake_waiting_input"
        return state

    returning = bool(state.get("returning_patient_profile") and state.get("patient_name") and state.get("patient_age") is not None)

    if not state.get("patient_data_confirmed"):
        if returning and _capture_symptoms_directly(state, conversation):
            extracted = PatientExtraction(
                symptoms=state.get("symptoms"),
                duration=state.get("symptom_duration"),
            )
        else:
            data = _extract_patient_data(conversation, symptoms_only=returning)
            extracted = _safe_validate_extraction(data, conversation, symptoms_only=returning)

        if not returning:
            if extracted.name and not state.get("patient_name"):
                state["patient_name"] = extracted.name
            if extracted.age is not None and state.get("patient_age") is None:
                state["patient_age"] = extracted.age
            if extracted.gender and not state.get("patient_gender"):
                state["patient_gender"] = extracted.gender
            if extracted.weight is not None and state.get("patient_weight") is None:
                state["patient_weight"] = extracted.weight
            if extracted.smoker is not None and state.get("patient_smoker") is None:
                state["patient_smoker"] = extracted.smoker
            if extracted.history and not state.get("patient_chronic_conditions"):
                state["patient_chronic_conditions"] = extracted.history
            if extracted.occupation and not state.get("patient_occupation"):
                state["patient_occupation"] = extracted.occupation

        if extracted.symptoms:
            symptom_text = extracted.symptoms.strip().lower()
            if symptom_text not in _SYMPTOM_BLOCKLIST and len(symptom_text) > 3:
                state["symptoms"] = normalize_clinical_text(extracted.symptoms.strip(), "symptoms")
        if extracted.duration:
            state["symptom_duration"] = extracted.duration
        if extracted.smoker is not None:
            state["patient_smoker"] = extracted.smoker

        smoker_hint = _detect_smoker_from_text(last_msg)
        if smoker_hint is not None:
            state["patient_smoker"] = smoker_hint

    has_name = bool(state.get("patient_name"))
    has_age = state.get("patient_age") is not None
    has_symptoms = bool(state.get("symptoms"))

    if has_name and has_age and has_symptoms:
        state["message"] = _generate_confirmation_request(state)
        state["current_step"] = "patient_intake_awaiting_confirmation"
    else:
        missing_fields = []
        if not has_name:
            missing_fields.append("name")
        if not has_age:
            missing_fields.append("age")
        if not has_symptoms:
            missing_fields.append("symptoms")
        state["message"] = _generate_followup_question(state, missing_fields, returning)
        state["current_step"] = "patient_intake_waiting_input"

    return state


def _extract_patient_data(conversation: List[Dict[str, str]], symptoms_only: bool = False) -> Dict[str, Any]:
    if symptoms_only:
        last_user = _last_user_message(conversation)
        if last_user and len(last_user.strip()) >= 15 and not _is_confirmation_message(last_user):
            return _extract_symptoms_fallback(conversation)

    if symptoms_only:
        system_prompt = (
            "Extract today's visit details from the latest user messages. "
            "Return a single JSON object (not an array) with keys: "
            "symptoms (string), duration (string), smoker (boolean or null). "
            "Set smoker=true if they mention smoking recently, cigarettes, or tobacco. "
            "Set smoker=false only if they clearly deny smoking. Use null if not mentioned."
        )
    else:
        system_prompt = (
            "Extract patient details into a single JSON object (not an array) with keys: "
            "name, age, gender, weight, smoker, symptoms, duration, history, occupation. "
            "Use null for missing fields."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": "Extract info from:\n" + "\n".join(
                f"{m['role']}: {m['content']}" for m in conversation[-6:]
            ),
        },
    ]

    try:
        response = call_groq_llm(messages, temperature=0.1, json_mode=True)
        clean = response.strip()
        if clean.startswith("```json"):
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif clean.startswith("```"):
            clean = clean.split("```")[1].split("```")[0].strip()
        parsed = json.loads(clean)
        return _normalize_extraction_dict(parsed)
    except (LLMError, json.JSONDecodeError, LLMInvalidResponseError) as e:
        log_error_with_context(e, {"operation": "patient_data_extraction"})
        if symptoms_only:
            return _extract_symptoms_fallback(conversation)
        return _extract_basic_info_fallback(conversation)
    except Exception as e:
        log_error_with_context(e, {"operation": "patient_data_extraction"})
        if symptoms_only:
            return _extract_symptoms_fallback(conversation)
        return _extract_basic_info_fallback(conversation)


def _extract_symptoms_fallback(conversation: List[Dict[str, str]]) -> Dict[str, Any]:
    last_user = ""
    for msg in reversed(conversation):
        if msg.get("role") == "user":
            last_user = msg.get("content", "")
            break
    data: Dict[str, Any] = {}
    if last_user and len(last_user.strip()) > 10:
        data["symptoms"] = last_user.strip()
        duration_match = re.search(
            r'(?:for|lasting|last)\s+(\d+\s*(?:days?|weeks?|months?|hours?)|last few days)',
            last_user,
            re.IGNORECASE,
        )
        if duration_match:
            data["duration"] = duration_match.group(1).strip()
    return data


def _extract_basic_info_fallback(conversation: List[Dict[str, str]]) -> Dict[str, Any]:
    data = {}
    full_text = " ".join([msg.get("content", "") for msg in conversation]).lower()

    name_match = re.search(r'name\s*(?:is|:)?\s+([a-z]+)', full_text)
    if name_match:
        data["name"] = name_match.group(1).title()

    age_match = re.search(r'age\s*(?:is|:)?\s+(\d+)', full_text)
    if age_match:
        try:
            data["age"] = int(age_match.group(1))
        except ValueError:
            pass

    if "male" in full_text:
        data["gender"] = "male"
    elif "female" in full_text:
        data["gender"] = "female"

    weight_match = re.search(r'weight\s*(?:is|:)?\s+(\d+(?:\.\d+)?)\s*(?:kg|lbs)?', full_text)
    if weight_match:
        try:
            data["weight"] = float(weight_match.group(1))
        except ValueError:
            pass

    if "smoker" in full_text:
        smoker_match = re.search(r'smoker\s*(?:is|:)?\s*(yes|no|true|false)', full_text)
        if smoker_match:
            data["smoker"] = smoker_match.group(1).lower() in ("yes", "true")
        elif "non-smoker" in full_text or "non smoker" in full_text:
            data["smoker"] = False
        else:
            smoker_index = full_text.find("smoker")
            next_words = full_text[smoker_index:smoker_index + 15]
            data["smoker"] = "yes" in next_words or "true" in next_words
    elif "non-smoker" in full_text or "non smoker" in full_text:
        data["smoker"] = False
    else:
        smoker_hint = _detect_smoker_from_text(full_text)
        if smoker_hint is not None:
            data["smoker"] = smoker_hint

    symptom_match = re.search(
        r'symptoms?\s*(?:is|:)?\s*([^\.]+?)(?:\s+for\s+|\s+medical|\s+occupation|$)',
        full_text,
        re.IGNORECASE,
    )
    if symptom_match:
        data["symptoms"] = symptom_match.group(1).strip()
    else:
        symptoms = []
        for keyword in ("cough", "fever", "pain", "breath", "chest", "headache", "nausea", "breathing", "fatigue"):
            if keyword in full_text:
                symptoms.append(keyword)
        if symptoms:
            data["symptoms"] = ", ".join(symptoms)

    duration_match = re.search(
        r'(?:for|duration|last)\s+(\d+\s*(?:days?|weeks?|months?|hours?))',
        full_text,
        re.IGNORECASE,
    )
    if duration_match:
        data["duration"] = duration_match.group(1).strip()

    history_match = re.search(
        r'(?:medical\s+history|history)\s*(?:is|:)?\s*([^\.]+?)(?:\s+occupation|$)',
        full_text,
        re.IGNORECASE,
    )
    if history_match:
        data["history"] = history_match.group(1).strip()

    occupation_match = re.search(r'occupation\s*(?:is|:)?\s*([a-z]+)', full_text, re.IGNORECASE)
    if occupation_match:
        data["occupation"] = occupation_match.group(1).strip()

    return data


def _generate_returning_greeting(state: AgentState) -> str:
    name = state.get("patient_name", "")
    parts = [f"Welcome back, **{name}**! I have your profile on file"]
    if state.get("patient_age") is not None:
        parts.append(f"(Age {state['patient_age']}")
        if state.get("patient_gender"):
            parts[-1] += f", {str(state['patient_gender']).title()}"
        if state.get("patient_smoker") is not None:
            parts[-1] += f", {'Smoker' if state['patient_smoker'] else 'Non-smoker'}"
        parts[-1] += ")"
    msg = parts[0] + " " + parts[1] + "." if len(parts) > 1 else parts[0] + "."
    msg += "\n\nWhat's bringing you in today? Please describe your **symptoms** and how long you've had them."
    history = state.get("patient_history_summary")
    if history:
        msg += f"\n\n**Previous visits:**\n{history}"
    return msg


def _generate_greeting(state: AgentState) -> str:
    history = state.get("patient_history_summary")
    if history:
        return (
            f"Welcome back! I've reviewed your previous visits:\n{history}\n\n"
            "How are you feeling today? Please share your current **symptoms**."
        )
    return """Hello! How are you, sir? I am your pulmonology doctor.

To provide you with the best care, could you please tell me these details:

• **Name**
• **Age**
• **Gender**
• **Weight** (in kg or lbs)
• **Smoker or not**
• **Symptoms**
• **Medical history**
• **Symptom duration**

You can share all this information in one message, and I'll organize it for you."""


def _generate_confirmation_request(state: AgentState) -> str:
    weight = state.get("patient_weight")
    weight_str = f"{weight} kg" if weight is not None else "Not provided"
    smoker = state.get("patient_smoker")
    smoker_str = "Yes" if smoker else "No" if smoker is not None else "Not provided"
    info = [
        f"**Name:** {state.get('patient_name')}",
        f"**Age:** {state.get('patient_age')}",
        f"**Gender:** {state.get('patient_gender') or 'Not provided'}",
        f"**Symptoms:** {state.get('symptoms')}",
        f"**Weight:** {weight_str}",
        f"**Smoker:** {smoker_str}",
    ]
    return (
        "Thank you! Please review your information and confirm if it's correct:\n\n"
        + "\n".join(info)
        + "\n\nReply **'Yes'** to confirm or tell me what to change."
    )


def _generate_followup_question(state: AgentState, missing: List[str], returning: bool = False) -> str:
    if returning and "symptoms" in missing:
        return f"Thanks {state.get('patient_name')}. What symptoms are you experiencing today and for how long?"
    if "name" in missing or "age" in missing:
        return "Could you please tell me your name and age?"
    if "symptoms" in missing:
        return f"Thanks {state.get('patient_name')}. What symptoms are you experiencing today and for how long?"
    return "I see. Could you also tell me your weight and if you are a smoker?"
