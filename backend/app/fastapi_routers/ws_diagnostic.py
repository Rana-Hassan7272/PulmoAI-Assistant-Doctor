"""
WebSocket endpoint for real-time diagnostic streaming.

Protocol (client → server):
  1. auth   : {"type": "auth", "token": "<JWT>"}
  2. chat   : {"type": "chat", "message": "<user text>"}

Protocol (server → client):
  stream_start : {"type": "stream_start"}
  stream_token : {"type": "stream_token", "token": "<text chunk>"}
  stream_end   : {"type": "stream_end", "message": "<full message>",
                  "current_step": "...", "visit_id": "...", ...}
  error        : {"type": "error", "message": "..."}
"""
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from ..agents.graph import create_diagnostic_graph
from ..agents.schemas import AgentStateValidator
from ..agents.state import AgentState
from ..core.auth import SECRET_KEY, ALGORITHM
from ..core.database import SessionLocal
from ..db_models.user import User

router = APIRouter(prefix="/diagnostic", tags=["Diagnostic WebSocket"])
logger = logging.getLogger(__name__)

# One graph instance shared across WS connections (thread-safe)
_graph_instance = None


def _get_graph():
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = create_diagnostic_graph()
    return _graph_instance


def _authenticate(token: str) -> Optional[User]:
    """Validate JWT and return the User, or None on failure."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            return None
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            return user
        finally:
            db.close()
    except JWTError:
        return None


async def _send(ws: WebSocket, data: dict) -> None:
    await ws.send_text(json.dumps(data))


async def _send_error(ws: WebSocket, message: str) -> None:
    await _send(ws, {"type": "error", "message": message})


@router.websocket("/ws")
async def diagnostic_ws(websocket: WebSocket):
    """
    WebSocket endpoint for streaming diagnostic chat.

    Flow:
      client connects → sends auth message → sends chat messages
      server streams tokens then sends stream_end with full state snapshot
    """
    await websocket.accept()
    logger.info("WS: new connection accepted")

    current_user: Optional[User] = None
    visit_id: Optional[str] = None
    state: Optional[AgentState] = None
    graph = _get_graph()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _send_error(websocket, "Invalid JSON")
                continue

            msg_type = msg.get("type", "")

            # ------------------------------------------------------------------
            # AUTH handshake
            # ------------------------------------------------------------------
            if msg_type == "auth":
                token = msg.get("token", "")
                user = _authenticate(token)
                if user is None:
                    await _send_error(websocket, "Authentication failed")
                    await websocket.close(code=4001)
                    return

                current_user = user
                patient_id = user.patient_id
                if not patient_id:
                    await _send_error(websocket, "No patient profile linked to this account")
                    await websocket.close(code=4002)
                    return

                # Build initial state via AgentStateValidator
                visit_id = str(uuid.uuid4())
                state = AgentStateValidator(
                    patient_id=patient_id,
                    visit_id=visit_id,
                ).to_agent_state()

                await _send(websocket, {"type": "auth_ok", "visit_id": visit_id})
                logger.info(f"WS: authenticated user_id={user.id}, visit_id={visit_id}")

                # Kick off the first graph step (patient intake greeting)
                config = {"configurable": {"thread_id": visit_id}, "recursion_limit": 50}
                try:
                    result = graph.invoke(state, config=config)
                    state = result
                    greeting = result.get("message") or "Hello! I'm your pulmonology assistant. How can I help you today?"
                    await _send(websocket, {
                        "type": "stream_end",
                        "message": greeting,
                        "current_step": result.get("current_step"),
                        "visit_id": visit_id,
                    })
                except Exception as exc:
                    logger.exception(f"WS: graph invoke error on start: {exc}")
                    await _send_error(websocket, "Failed to start diagnostic session")

            # ------------------------------------------------------------------
            # CHAT message
            # ------------------------------------------------------------------
            elif msg_type == "chat":
                if current_user is None or state is None:
                    await _send_error(websocket, "Not authenticated. Send an auth message first.")
                    continue

                user_text = msg.get("message", "").strip()
                if not user_text:
                    continue

                # Append user message to conversation history
                state["conversation_history"] = state.get("conversation_history", []) + [
                    {"role": "user", "content": user_text}
                ]

                await _send(websocket, {"type": "stream_start"})

                config = {"configurable": {"thread_id": visit_id}, "recursion_limit": 50}
                try:
                    result = graph.invoke(state, config=config)
                    state = result
                    full_message = result.get("message") or ""

                    # Stream tokens word-by-word for a typing effect
                    words = full_message.split(" ")
                    for i, word in enumerate(words):
                        chunk = word if i == len(words) - 1 else word + " "
                        await _send(websocket, {"type": "stream_token", "token": chunk})

                    await _send(websocket, {
                        "type": "stream_end",
                        "message": full_message,
                        "current_step": result.get("current_step"),
                        "visit_id": visit_id,
                        "emergency_flag": result.get("emergency_flag", False),
                        "emergency_reason": result.get("emergency_reason"),
                        "patient_data_confirmed": result.get("patient_data_confirmed", False),
                        "treatment_approved": result.get("treatment_approved", False),
                        "final_report": result.get("final_report"),
                    })

                    # Append assistant reply to conversation history
                    state["conversation_history"] = state.get("conversation_history", []) + [
                        {"role": "assistant", "content": full_message}
                    ]

                except Exception as exc:
                    logger.exception(f"WS: graph invoke error: {exc}")
                    await _send_error(websocket, "An error occurred while processing your message")

            else:
                await _send_error(websocket, f"Unknown message type: {msg_type}")

    except WebSocketDisconnect:
        logger.info(f"WS: client disconnected (visit_id={visit_id})")
    except Exception as exc:
        logger.exception(f"WS: unexpected error: {exc}")
        try:
            await _send_error(websocket, "Unexpected server error")
        except Exception:
            pass
