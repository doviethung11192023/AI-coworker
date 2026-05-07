
from langchain_core.prompts import ChatPromptTemplate
from app.core.state import SimulationState
from app.core.llm import get_llm
import json
import re

_ALLOWED_AGENTS = {"ceo", "chro", "regional", "end"}
_STUCK_PHRASES = [
    "not sure",
    "confused",
    "dont know",
    "don't know",
    "do not know",
    "stuck",
    "going in circles",
    "i don't understand",
    "khong biet",
    "khong ro",
    "bi mac",
]


def _parse_director_json(text: str) -> dict:
    """Best-effort JSON extraction from model output."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def _extract_user_messages(messages) -> list:
    texts = []
    for msg in messages or []:
        if isinstance(msg, (list, tuple)) and len(msg) >= 2:
            role, content = msg[0], msg[1]
        else:
            role = getattr(msg, "type", None) or getattr(msg, "role", None)
            content = getattr(msg, "content", None)
            if role is None and isinstance(msg, dict):
                role = msg.get("type") or msg.get("role")
                content = msg.get("content")

        if role == "user" and isinstance(content, str):
            texts.append(content)
    return texts


def _tokenize(text: str) -> list:
    return re.findall(r"[a-z0-9]+", text.lower())


def _jaccard(a: list, b: list) -> float:
    set_a, set_b = set(a), set(b)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _detect_stuck(messages, user_progress: dict) -> dict:
    user_messages = _extract_user_messages(messages)
    if not user_messages:
        return {"is_stuck": False, "reason": "", "hint": ""}

    last_msg = user_messages[-1]
    last_tokens = _tokenize(last_msg)
    prev_tokens = _tokenize(user_messages[-2]) if len(user_messages) > 1 else []

    repeated = False
    if prev_tokens:
        repeated = _jaccard(last_tokens, prev_tokens) >= 0.8

    confusion = any(phrase in last_msg.lower() for phrase in _STUCK_PHRASES)
    is_stuck = repeated or confusion
    reason = "repeated intent" if repeated else "confusion signal" if confusion else ""
    hint = "Try outlining a concrete deliverable and 1-2 KPIs to move forward." if is_stuck else ""

    return {"is_stuck": is_stuck, "reason": reason, "hint": hint}


def _pick_enabled_agent(preferred: str, enabled: dict) -> str:
    if enabled.get(preferred, False):
        return preferred
    for candidate in ["chro", "ceo", "regional"]:
        if enabled.get(candidate, False):
            return candidate
    return "end"
       

def supervisor_node(state: SimulationState):
    llm = get_llm(model_type="local", temperature=0, model_name="qwen2.5:3b")

    prompt = ChatPromptTemplate.from_template("""
    You are the invisible Simulation Director for Edtronaut's Gucci Leadership Simulation.

    Current Module: {current_module}
    Enabled coworkers: {enabled_coworkers}
    User Progress: {user_progress}
    Director Notes from previous: {director_notes}
    Stuck signal: {stuck_signal}
    Stuck reason: {stuck_reason}

    Recent conversation:
    {messages}

    Your job:
    - Keep the user on track with the simulation objectives
    - Detect if user is stuck or going in circles
    - Choose the most appropriate Co-worker to respond next
    - Provide a short hint if needed

    Respond in JSON format only. Do not wrap in markdown:
    {{
        "next_agent": "ceo" | "chro" | "regional" | "end",
        "hint": "Short hint for the chosen agent (if any)",
        "reason": "Brief reasoning"
    }}
    """)

    enabled_coworkers = state.get("enabled_coworkers") or {
        "ceo": True,
        "chro": True,
        "regional": True,
    }
    user_progress = state.get("user_progress") or {}
    stuck_info = _detect_stuck(state.get("messages"), user_progress)

    response = llm.invoke(
        prompt.format_messages(
            **{
                **state,
                "enabled_coworkers": enabled_coworkers,
                "stuck_signal": stuck_info["is_stuck"],
                "stuck_reason": stuck_info["reason"],
            }
        )
    )
    
    decision = _parse_director_json(response.content)
    next_agent = str(decision.get("next_agent", "chro")).lower().strip()
    if next_agent not in _ALLOWED_AGENTS:
        next_agent = "chro"

    if enabled_coworkers:
        next_agent = _pick_enabled_agent(next_agent, enabled_coworkers)

    reason = str(decision.get("reason", "")).strip()
    hint = str(decision.get("hint", "")).strip()
    if stuck_info["is_stuck"] and not hint:
        hint = stuck_info["hint"]
    if hint:
        reason = f"{reason} Hint: {hint}" if reason else f"Hint: {hint}"

    stuck_count = int(user_progress.get("stuck_count", 0))
    if stuck_info["is_stuck"]:
        stuck_count += 1
    else:
        stuck_count = max(stuck_count - 1, 0)

    updated_progress = {
        **user_progress,
        "turn_count": len(_extract_user_messages(state.get("messages"))),
        "last_user_message": _extract_user_messages(state.get("messages"))[-1] if _extract_user_messages(state.get("messages")) else "",
        "stuck_count": stuck_count,
        "stuck_reason": stuck_info["reason"],
    }

    sentiment = state.get("co_worker_sentiment") or {}
    if next_agent in ["ceo", "chro", "regional"]:
        sentiment[next_agent] = "impatient" if stuck_count >= 2 else "neutral"

    return {
        "next_agent": next_agent,
        "director_notes": reason or "Default to CHRO",
        "user_progress": updated_progress,
        "co_worker_sentiment": sentiment,
    }