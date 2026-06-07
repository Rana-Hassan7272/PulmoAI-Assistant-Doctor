"""
Configuration for LangGraph agents and LLM setup.
Primary: Google Gemini. Fallback: Groq. Optional: OpenAI.
"""
import os
import time
import random
import logging
from dotenv import load_dotenv
from typing import Optional, Literal, List, Dict, Any, Tuple
from groq import Groq
from ..core.error_handling import (
    LLMError, LLMTimeoutError, LLMRateLimitError,
    LLMConnectionError, LLMInvalidResponseError,
    log_error_with_context
)

logger = logging.getLogger(__name__)

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_GEMINI_MODEL = os.getenv("GOOGLE_GEMINI_MODEL", "gemini-2.0-flash")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

LLM_PROVIDER: Optional[Literal["google", "groq", "openai"]] = None

if GOOGLE_API_KEY:
    LLM_PROVIDER = "google"
    logger.info("Using Google Gemini as primary LLM provider")
elif GROQ_API_KEY:
    LLM_PROVIDER = "groq"
    logger.info("Using Groq as LLM provider")
elif OPENAI_API_KEY:
    LLM_PROVIDER = "openai"
    logger.info("Using OpenAI as LLM provider")
else:
    logger.warning("No LLM API key found. Set GOOGLE_API_KEY or GROQ_API_KEY.")


def get_groq_client():
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not found in environment variables.")
    return Groq(api_key=GROQ_API_KEY)


def get_openai_client():
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package not installed. Run: pip install openai")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not found in environment variables.")
    return OpenAI(api_key=OPENAI_API_KEY)


def _messages_to_gemini(messages: List[Dict[str, str]]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    system_parts: List[str] = []
    contents: List[Dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if not content:
            continue
        if role == "system":
            system_parts.append(content)
        elif role == "assistant":
            contents.append({"role": "model", "parts": [content]})
        else:
            contents.append({"role": "user", "parts": [content]})

    if not contents:
        contents = [{"role": "user", "parts": ["Hello"]}]

    merged: List[Dict[str, Any]] = []
    for item in contents:
        if merged and merged[-1]["role"] == item["role"]:
            merged[-1]["parts"][0] += "\n" + item["parts"][0]
        else:
            merged.append(item)

    if merged[0]["role"] == "model":
        merged.insert(0, {"role": "user", "parts": ["Continue the conversation."]})

    system_instruction = "\n".join(system_parts).strip() or None
    return system_instruction, merged


def _call_google_gemini(
    messages: List[Dict[str, str]],
    temperature: float,
    json_mode: bool,
    timeout: int,
) -> str:
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError("google-generativeai not installed. Run: pip install google-generativeai")

    if not GOOGLE_API_KEY:
        raise LLMConnectionError("GOOGLE_API_KEY not found.")

    genai.configure(api_key=GOOGLE_API_KEY)
    system_instruction, contents = _messages_to_gemini(messages)

    generation_config: Dict[str, Any] = {"temperature": temperature}
    if json_mode:
        generation_config["response_mime_type"] = "application/json"

    model = genai.GenerativeModel(
        model_name=GOOGLE_GEMINI_MODEL,
        system_instruction=system_instruction,
    )

    response = model.generate_content(
        contents,
        generation_config=genai.GenerationConfig(**generation_config),
        request_options={"timeout": timeout},
    )

    text = getattr(response, "text", None)
    if not text or not str(text).strip():
        raise LLMInvalidResponseError("Google Gemini returned empty response")
    return str(text).strip()


def _call_groq_provider(messages: List[Dict[str, str]], temperature: float, json_mode: bool, timeout: int) -> str:
    client = get_groq_client()
    params: Dict[str, Any] = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "timeout": timeout,
    }
    if json_mode:
        params["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**params)
    if not response or not response.choices or not response.choices[0].message.content:
        raise LLMInvalidResponseError("Groq returned empty response")
    return response.choices[0].message.content


def _call_openai_provider(messages: List[Dict[str, str]], temperature: float, json_mode: bool, timeout: int) -> str:
    client = get_openai_client()
    params: Dict[str, Any] = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "timeout": timeout,
    }
    if json_mode:
        params["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**params)
    if not response or not response.choices or not response.choices[0].message.content:
        raise LLMInvalidResponseError("OpenAI returned empty response")
    return response.choices[0].message.content


def _should_fallback_to_groq(provider: str, error: Exception) -> bool:
    return provider != "groq" and bool(GROQ_API_KEY) and not isinstance(error, LLMRateLimitError)


def call_llm(
    messages: list,
    temperature: float = None,
    provider: Optional[Literal["google", "groq", "openai"]] = None,
    max_retries: int = 3,
    json_mode: bool = False,
    timeout: int = 60,
) -> str:
    selected_provider = provider or LLM_PROVIDER
    if not selected_provider:
        raise LLMConnectionError(
            "No LLM provider available. Set GOOGLE_API_KEY or GROQ_API_KEY in .env."
        )

    temp = temperature if temperature is not None else TEMPERATURE

    for attempt in range(max_retries):
        try:
            if selected_provider == "google":
                return _call_google_gemini(messages, temp, json_mode, timeout)
            if selected_provider == "groq":
                return _call_groq_provider(messages, temp, json_mode, timeout)
            if selected_provider == "openai":
                return _call_openai_provider(messages, temp, json_mode, timeout)
            raise ValueError(f"Unknown provider: {selected_provider}")

        except Exception as e:
            error_str = str(e).lower()
            log_error_with_context(e, {"provider": selected_provider, "attempt": attempt + 1})

            if _should_fallback_to_groq(selected_provider, e):
                logger.warning(f"{selected_provider} failed, falling back to Groq: {e}")
                return call_llm(
                    messages,
                    temperature=temp,
                    provider="groq",
                    max_retries=max_retries,
                    json_mode=json_mode,
                    timeout=timeout,
                )

            is_rate_limit = any(x in error_str for x in ("rate limit", "429", "quota", "too many requests"))
            is_timeout = isinstance(e, TimeoutError) or "timeout" in error_str
            is_connection = any(x in error_str for x in ("connection", "network", "unavailable"))

            if attempt < max_retries - 1 and (is_rate_limit or is_timeout or is_connection):
                wait_time = (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(wait_time)
                continue

            if is_rate_limit:
                raise LLMRateLimitError("Rate limit exceeded. Please try again shortly.")
            if is_timeout:
                raise LLMTimeoutError("Request timed out. Please try again.")
            if is_connection:
                raise LLMConnectionError("Unable to connect to LLM service.")
            raise LLMError(f"LLM API error: {str(e)}")

    raise LLMError("Failed to get response after all retries")


def call_groq_llm(messages: list, temperature: float = None, json_mode: bool = False) -> str:
    return call_llm(messages, temperature, json_mode=json_mode)
