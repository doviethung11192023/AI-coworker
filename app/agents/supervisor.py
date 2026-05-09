
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from langchain_core.messages.tool import ToolMessage, tool_call
from app.core.state import SimulationState
from app.core.simulation_config import load_simulation_config
from app.core.tool_config import get_allowed_tools
from app.core.llm import get_llm
from app.memory.vector_store import add_memory_entry, query_memory
from uuid import uuid4
import json
import re
import logging

# MEDIUM: Route Regional for voice diversity when last agent was CHRO

logger = logging.getLogger(__name__)

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

_DELIVERABLE_INTENT_PATTERNS = [
    r"\bdefine\b",
    r"\bmap\b",
    r"\bdraft\b",
    r"\bpropose\b",
    r"\bbuild\b",
    r"\bcreate\b",
    r"\bfinalize\b",
    r"\balign\b",
    r"\bdesign\b",
    r"\bplan\b",
    r"\bshould\b",
    r"\bwe can\b",
    r"\bxac dinh\b",
    r"\bđịnh nghĩa\b",
    r"\bthiet ke\b",
    r"\bthiết kế\b",
    r"\bde xuat\b",
    r"\bđề xuất\b",
    r"\bke hoach\b",
    r"\bkế hoạch\b",
]

_FRAMEWORK_TOPIC_PATTERNS = [
    r"competency",
    r"competencies",
    r"framework",
    r"standardiz",
    r"alignment",
    r"talent mobility",
    r"vision",
    r"entrepreneurship",
    r"passion",
    r"trust",
    r"brand dna",
    r"group dna",
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

        if role in ("user", "human") and isinstance(content, str):
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


def _detect_framework_loop(messages) -> dict:
    user_messages = _extract_user_messages(messages)
    recent_messages = user_messages[-4:]
    if len(recent_messages) < 2:
        return {"repeat_count": 0, "is_repeated": False}

    repeat_count = 0
    for message in recent_messages:
        lowered = message.lower()
        if any(re.search(pattern, lowered) for pattern in _FRAMEWORK_TOPIC_PATTERNS):
            repeat_count += 1

    return {
        "repeat_count": repeat_count,
        "is_repeated": repeat_count >= 2,
    }


def _build_director_event(current_stage: str, framework_loop: dict, stuck_info: dict) -> dict | None:
    if not framework_loop.get("is_repeated") and not stuck_info.get("is_stuck"):
        return None

    if current_stage in {"discovery", "alignment", "design"} and framework_loop.get("is_repeated"):
        return {
            "speaker": "regional",
            "message": "Regional offices are pushing back. They think the framework is becoming too centralized and will be hard to localize.",
            "hidden_objective": "Force the user to address adoption resistance before continuing with the framework.",
            "pressure_type": "resistance",
        }

    if stuck_info.get("is_stuck"):
        return {
            "speaker": "ceo" if current_stage in {"alignment", "wrap_up"} else "regional",
            "message": "We need a sharper decision. The current direction is too abstract and risks losing support from brand leadership.",
            "hidden_objective": "Push the user to make one concrete tradeoff decision.",
            "pressure_type": "pressure",
        }

    return None


def _pick_enabled_agent(preferred: str, enabled: dict) -> str:
    if enabled.get(preferred, False):
        return preferred
    for candidate in ["chro", "ceo", "regional"]:
        if enabled.get(candidate, False):
            return candidate
    return "end"


def _pick_preferred_agent(preferred_agents: list[str], enabled: dict) -> str | None:
    for agent in preferred_agents:
        if enabled.get(agent, False):
            return agent
    return None


def _pick_stage_guarded_agent(
    stage: dict,
    enabled_coworkers: dict,
    current_stage: str,
    next_agent: str,
) -> str:
    preferred_agents = stage.get("preferred_agents", [])
    if next_agent == "end" and stage.get("required_deliverables"):
        next_agent = _pick_preferred_agent(preferred_agents, enabled_coworkers) or _pick_enabled_agent("chro", enabled_coworkers)
        return next_agent

    if next_agent in {"ceo", "chro", "regional"} and enabled_coworkers.get(next_agent, False):
        if preferred_agents and next_agent not in preferred_agents and current_stage != "wrap_up":
            stage_preferred = _pick_preferred_agent(preferred_agents, enabled_coworkers)
            if stage_preferred:
                return stage_preferred
    return next_agent


def _build_preferred_agent_weights(preferred_agents: list[str]) -> dict[str, float]:
    weights: dict[str, float] = {}
    if not preferred_agents:
        return weights

    base_weight = 0.45
    step = 0.10
    for index, agent in enumerate(preferred_agents):
        weight = max(base_weight - (index * step), 0.05)
        weights[agent] = weight
    return weights


def _format_sentiment_snapshot(co_worker_sentiment: dict | None) -> str:
    co_worker_sentiment = co_worker_sentiment or {}
    lines = []
    for agent_name in ["ceo", "chro", "regional"]:
        mood = co_worker_sentiment.get(agent_name)
        if mood:
            lines.append(f"- {agent_name.upper()}: {mood}")
    if not lines:
        return "No active emotional state yet."
    return "\n".join(lines)


def _emotion_default_for_context(agent_name: str, current_stage: str, stuck_info: dict, framework_loop: dict) -> str:
    if stuck_info.get("is_stuck"):
        return "impatient"
    if framework_loop.get("is_repeated"):
        if agent_name == "ceo":
            return "defensive"
        if agent_name == "regional":
            return "skeptical"
        return "skeptical"
    if current_stage in {"execution_planning", "wrap_up"} and agent_name == "regional":
        return "collaborative"
    return "collaborative"


def _evolve_co_worker_sentiment(
    current_sentiment: dict | None,
    next_agent: str,
    current_stage: str,
    stuck_info: dict,
    framework_loop: dict,
    director_event: dict | None,
) -> dict:
    sentiment = dict(current_sentiment or {})
    for agent_name in ["ceo", "chro", "regional"]:
        sentiment.setdefault(agent_name, "collaborative")

    if director_event:
        speaker = director_event.get("speaker")
        pressure_type = director_event.get("pressure_type")
        if speaker in sentiment:
            sentiment[speaker] = "defensive" if pressure_type == "resistance" else "skeptical"

    if stuck_info.get("is_stuck") or framework_loop.get("is_repeated"):
        sentiment[next_agent] = _emotion_default_for_context(next_agent, current_stage, stuck_info, framework_loop)
    else:
        sentiment[next_agent] = "collaborative"

    if current_stage == "alignment" and next_agent == "ceo":
        sentiment[next_agent] = "defensive"
    if current_stage == "discovery" and next_agent == "chro" and framework_loop.get("is_repeated"):
        sentiment[next_agent] = "skeptical"

    logger.debug("Emotion update | next_agent=%s sentiment=%s", next_agent, sentiment)
    return sentiment


def _format_coworker_memory(coworker_memory: dict | None) -> str:
    coworker_memory = coworker_memory or {}
    latest_stances = coworker_memory.get("latest_stances") or {}
    if not latest_stances:
        return "No prior coworker positions recorded yet."

    lines = []
    for agent_name in ["ceo", "chro", "regional"]:
        stance = latest_stances.get(agent_name)
        if stance:
            lines.append(f"- {agent_name.upper()}: {stance}")

    if not lines:
        return "No prior coworker positions recorded yet."
    return "\n".join(lines)


def _build_long_term_memory_context(
    last_user_text: str,
    simulation_id: str | None,
    thread_id: str | None,
    current_module: int | None,
) -> str:
    if not last_user_text:
        return "No long-term memory retrieved yet."

    recalls = query_memory(
        last_user_text,
        simulation_id=simulation_id,
        thread_id=thread_id,
        module=current_module,
        n_results=2,
    )
    if not recalls:
        return "No long-term memory retrieved yet."

    lines = []
    for content, metadata in recalls:
        metadata = metadata or {}
        kind = metadata.get("kind", "memory")
        agent_name = metadata.get("agent_name", "unknown")
        stage = metadata.get("stage")
        stage_suffix = f" | stage={stage}" if stage else ""
        lines.append(f"- [{kind}] {agent_name}{stage_suffix}: {content}")

    return "\n".join(lines)


def _record_supervisor_memory(
    *,
    state: SimulationState,
    next_agent: str,
    reason: str,
    current_stage: str,
    progress: int,
    completed_deliverables: set[str],
):
    summary = (
        f"stage={current_stage}; next_agent={next_agent}; progress={progress}; "
        f"completed={','.join(sorted(completed_deliverables)) or 'none'}; reason={reason or 'none'}"
    )
    add_memory_entry(
        summary,
        kind="decision",
        simulation_id=state.get("simulation_id"),
        thread_id=state.get("thread_id"),
        module=state.get("current_module"),
        agent_name="supervisor",
        metadata={
            "stage": current_stage,
            "next_agent": next_agent,
            "progress": progress,
        },
    )


def _extract_numbers(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?", text)]


def _extract_named_number(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _parse_kpi_args(text: str) -> tuple[dict | None, list[str]]:
    baseline = _extract_named_number(text, [r"baseline\s*[:=]?\s*(\d+(?:\.\d+)?)", r"base\s*[:=]?\s*(\d+(?:\.\d+)?)"])
    target = _extract_named_number(text, [r"target\s*[:=]?\s*(\d+(?:\.\d+)?)"])
    timeframe = _extract_named_number(text, [r"timeframe\s*[:=]?\s*(\d+)", r"in\s+(\d+)\s+months?", r"(\d+)\s+months?", r"(\d+)\s+thang", r"(\d+)\s+tháng"])
    audience = _extract_named_number(text, [r"audience\s*[:=]?\s*(\d+)", r"size\s*[:=]?\s*(\d+)", r"participants\s*[:=]?\s*(\d+)", r"people\s*[:=]?\s*(\d+)", r"\bn\s*[:=]?\s*(\d+)"])

    numbers = _extract_numbers(text)
    if baseline is None and len(numbers) >= 1:
        baseline = numbers[0]
    if target is None and len(numbers) >= 2:
        target = numbers[1]
    if timeframe is None and len(numbers) >= 3:
        timeframe = numbers[2]
    if audience is None and len(numbers) >= 4:
        audience = numbers[3]

    missing = []
    if baseline is None:
        missing.append("baseline")
    if target is None:
        missing.append("target")
    if timeframe is None:
        missing.append("timeframe_months")

    if missing:
        return None, missing

    args = {
        "baseline": float(baseline),
        "target": float(target),
        "timeframe_months": int(round(float(timeframe))),
    }
    if audience is not None:
        args["audience_size"] = int(round(float(audience)))
    return args, []


def _parse_ab_args(text: str) -> tuple[dict | None, list[str]]:
    variant_a = _extract_named_number(text, [r"variant\s*a\s*[:=]?\s*(\d+(?:\.\d+)?)", r"a\s*rate\s*[:=]?\s*(\d+(?:\.\d+)?)", r"\ba\s*[:=]\s*(\d+(?:\.\d+)?)"])
    variant_b = _extract_named_number(text, [r"variant\s*b\s*[:=]?\s*(\d+(?:\.\d+)?)", r"b\s*rate\s*[:=]?\s*(\d+(?:\.\d+)?)", r"\bb\s*[:=]\s*(\d+(?:\.\d+)?)"])
    sample = _extract_named_number(text, [r"sample\s*size\s*[:=]?\s*(\d+)", r"samples?\s*[:=]?\s*(\d+)", r"\bn\s*[:=]?\s*(\d+)"])

    numbers = _extract_numbers(text)
    if variant_a is None and len(numbers) >= 1:
        variant_a = numbers[0]
    if variant_b is None and len(numbers) >= 2:
        variant_b = numbers[1]
    if sample is None and len(numbers) >= 3:
        sample = numbers[2]

    missing = []
    if variant_a is None:
        missing.append("variant_a_rate")
    if variant_b is None:
        missing.append("variant_b_rate")
    if sample is None:
        missing.append("sample_size")

    if missing:
        return None, missing

    return {
        "variant_a_rate": float(variant_a),
        "variant_b_rate": float(variant_b),
        "sample_size": int(round(float(sample))),
    }, []


def _extract_labeled_block(text: str, label: str, next_labels: str) -> str | None:
    pattern = rf"{label}\s*:\s*(.+?)(?=\s*(?:{next_labels})\s*:|$)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _collect_stage_context(simulation_id: str | None) -> dict:
    config = load_simulation_config(simulation_id)
    stages = config.get("stages", [])
    deliverables = config.get("deliverables", [])

    stage_by_name = {stage.get("name"): stage for stage in stages}
    deliverable_keywords = {
        item.get("id"): [kw.lower() for kw in item.get("keywords", [])]
        for item in deliverables
        if item.get("id")
    }

    return {
        "config": config,
        "stages": stages,
        "stage_by_name": stage_by_name,
        "deliverable_keywords": deliverable_keywords,
    }


def _has_structure_signal(text: str) -> bool:
    if "\n" in text and any(marker in text for marker in [":", "-", "1.", "2.", "3."]):
        return True
    if text.count(",") >= 2:
        return True
    return False


def _has_detail_signal(text: str) -> bool:
    token_count = len(_tokenize(text))
    if token_count >= 20:
        return True
    if any(marker in text.lower() for marker in ["for example", "e.g.", "including", "such as", "bao gồm", "ví dụ"]):
        return True
    return False


def _has_intent_signal(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _DELIVERABLE_INTENT_PATTERNS)


def _deliverable_confidence(text: str, keywords: list[str], is_required_now: bool) -> tuple[float, dict]:
    lowered = text.lower()
    
    # IMPROVED: More flexible keyword matching
    # For each keyword, check if it appears as a complete word or phrase
    keyword_hits = 0
    for keyword in keywords:
        if not keyword:
            continue
        # Check for exact phrase match first
        if keyword.lower() in lowered:
            keyword_hits += 1
            continue
        # For multi-word phrases, check if all main words are present
        key_words = keyword.lower().split()
        if len(key_words) > 1:
            if all(word in lowered for word in key_words):
                keyword_hits += 1
                continue
        # For single words, check with word boundaries (more flexible)
        if re.search(rf"\b{re.escape(keyword.lower())}\b", lowered):
            keyword_hits += 1
    
    if keyword_hits == 0:
        return 0.0, {
            "keyword_hits": 0,
            "intent": False,
            "structure": False,
            "detail": False,
            "threshold": 0.75 if is_required_now else 0.90,
        }

    intent = _has_intent_signal(text)
    structure = _has_structure_signal(text)
    detail = _has_detail_signal(text)

    # IMPROVED: Lower threshold when required and keywords already found
    keyword_score = min(keyword_hits / max(len(keywords), 1), 1.0)
    score = (
        (0.55 * keyword_score)
        + (0.20 if intent else 0.0)
        + (0.15 if structure else 0.0)
        + (0.10 if detail else 0.0)
    )

    # IMPROVED: Lower threshold for required deliverables since they are critical
    threshold = 0.60 if is_required_now else 0.85
    return score, {
        "keyword_hits": keyword_hits,
        "intent": intent,
        "structure": structure,
        "detail": detail,
        "threshold": threshold,
    }


def _detect_deliverables(
    messages,
    deliverable_keywords: dict[str, list[str]],
    required_deliverables: set[str] | None = None,
) -> set[str]:
    text = "\n".join(_extract_user_messages(messages))
    found = set()
    if not text:
        return found

    required_deliverables = required_deliverables or set()

    for deliverable_id, keywords in deliverable_keywords.items():
        is_required_now = deliverable_id in required_deliverables
        score, signals = _deliverable_confidence(text, keywords, is_required_now)
        if score >= signals["threshold"]:
            found.add(deliverable_id)
            logger.debug(
                "Deliverable detected | id=%s score=%.2f threshold=%.2f signals=%s",
                deliverable_id,
                score,
                signals["threshold"],
                signals,
            )
    return found


def _parse_portfolio_args(text: str) -> tuple[dict | None, list[str]]:
    plan = _extract_labeled_block(text, "plan", "posts?|exec(?:utive)?|update")
    posts = _extract_labeled_block(text, "posts?", "plan|exec(?:utive)?|update")
    exec_update = _extract_labeled_block(text, "exec(?:utive)?|update", "plan|posts?")

    missing = []
    if not plan:
        missing.append("plan")
    if not posts:
        missing.append("posts")
    if not exec_update:
        missing.append("exec_update")

    if missing:
        return None, missing

    return {
        "plan": plan,
        "posts": posts,
        "exec_update": exec_update,
    }, []


def _tool_enabled(tool_name: str, allowed_tools: set[str]) -> bool:
    if tool_name in allowed_tools:
        return True
    logger.debug("Tool disabled | name=%s", tool_name)
    return False


def _detect_tool_request(text: str, current_module: int | None, allowed_tools: set[str]) -> dict | None:
    if not text:
        return None
    lowered = text.lower()

    if any(token in lowered for token in ["doc", "docs", "document", "tai lieu", "tài liệu", "source", "nguon", "nguồn", "context"]):
        if not _tool_enabled("retrieve_simulation_docs", allowed_tools):
            return None
        return {"action": "call", "tool_name": "retrieve_simulation_docs", "tool_args": {"query": text, "module": current_module}}

    if any(token in lowered for token in ["objective", "objectives", "muc tieu", "mục tiêu"]):
        if not _tool_enabled("get_module_objectives", allowed_tools):
            return None
        return {"action": "call", "tool_name": "get_module_objectives", "tool_args": {"module": current_module}}

    if "headline" in lowered or "headlines" in lowered:
        if not _tool_enabled("prompt_library", allowed_tools):
            return None
        return {"action": "call", "tool_name": "prompt_library", "tool_args": {"prompt_type": "headline"}}

    if "disclaimer" in lowered or "disclaimers" in lowered:
        if not _tool_enabled("prompt_library", allowed_tools):
            return None
        return {"action": "call", "tool_name": "prompt_library", "tool_args": {"prompt_type": "disclaimer"}}

    if "prompt" in lowered:
        if not _tool_enabled("prompt_library", allowed_tools):
            return None
        return {"action": "call", "tool_name": "prompt_library", "tool_args": {"prompt_type": "headline"}}

    if "kpi" in lowered:
        if not _tool_enabled("kpi_calculator", allowed_tools):
            return None
        args, missing = _parse_kpi_args(text)
        if missing:
            return {
                "action": "ask",
                "message": "To use KPI calculator, provide baseline, target, and timeframe_months. Example: baseline=0.2 target=0.3 timeframe=6 months audience=1000.",
            }
        return {"action": "call", "tool_name": "kpi_calculator", "tool_args": args}

    if re.search(r"\b(a/b|ab test|ab)\b", lowered) or "variant a" in lowered or "variant b" in lowered:
        if not _tool_enabled("ab_simulator", allowed_tools):
            return None
        args, missing = _parse_ab_args(text)
        if missing:
            return {
                "action": "ask",
                "message": "To run A/B simulator, provide variant_a_rate, variant_b_rate, and sample_size. Example: A=0.12 B=0.15 sample=1200.",
            }
        return {"action": "call", "tool_name": "ab_simulator", "tool_args": args}

    if "portfolio" in lowered or "portfolio pack" in lowered or "export" in lowered:
        if not _tool_enabled("export_portfolio_pack", allowed_tools):
            return None
        args, missing = _parse_portfolio_args(text)
        if missing:
            return {
                "action": "ask",
                "message": "To export a portfolio pack, provide: plan: ..., posts: ..., exec_update: ...",
            }
        return {"action": "call", "tool_name": "export_portfolio_pack", "tool_args": args}

    return None
       

def supervisor_node(state: SimulationState):
    llm = get_llm(model_type="local", temperature=0, model_name="qwen2.5:3b")

    logger.debug(
        "Supervisor start | current_module=%s enabled=%s user_progress=%s",
        state.get("current_module"),
        state.get("enabled_coworkers"),
        state.get("user_progress"),
    )

    user_messages = _extract_user_messages(state.get("messages"))
    last_user = user_messages[-1] if user_messages else ""
    logger.debug(
        "Supervisor input | message_count=%s user_count=%s last_user=%s",
        len(state.get("messages") or []),
        len(user_messages),
        last_user[:160],
    )

    prompt = ChatPromptTemplate.from_template("""
    You are the invisible Simulation Director for Edtronaut's Gucci Leadership Simulation.

    Current Module: {current_module}
    Simulation Stage: {simulation_stage}
    Stage Description: {stage_description}
    Stage Preferred Agents: {stage_preferred_agents}
    Stage Guidance Weights: {stage_guidance_weights}
    Coworker Memory:
    {coworker_memory_snapshot}
    Emotional State:
    {co_worker_sentiment_snapshot}
    Long-term Memory:
    {long_term_memory_snapshot}
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
    - Treat stage preferred agents as soft guidance, not a hard override
    - Never replace an enabled valid choice only because another agent is preferred by stage

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
    co_worker_sentiment = state.get("co_worker_sentiment") or {}
    coworker_memory = state.get("coworker_memory") or {}
    user_progress = state.get("user_progress") or {}
    thread_id = state.get("thread_id")
    stuck_info = _detect_stuck(state.get("messages"), user_progress)

    stage_context = _collect_stage_context(state.get("simulation_id"))
    stages = stage_context["stages"]
    stage_by_name = stage_context["stage_by_name"]
    deliverable_keywords = stage_context["deliverable_keywords"]

    current_stage = state.get("simulation_stage") or (stages[0].get("name") if stages else "discovery")
    stage = stage_by_name.get(current_stage, {})
    required = set(stage.get("required_deliverables", []))
    framework_loop = _detect_framework_loop(state.get("messages"))
    long_term_context = _build_long_term_memory_context(
        last_user,
        state.get("simulation_id"),
        thread_id,
        state.get("current_module"),
    )

    completed_deliverables = set(state.get("completed_deliverables") or [])
    completed_deliverables.update(
        _detect_deliverables(
            state.get("messages"),
            deliverable_keywords,
            required_deliverables=required,
        )
    )

    stage_preferred_agents = stage.get("preferred_agents", [])
    stage_guidance_weights = _build_preferred_agent_weights(stage_preferred_agents)
    missing = sorted(required - completed_deliverables)
    progress = int(round(100 * (1 - (len(missing) / len(required))))) if required else 0
    stage_complete = not missing and bool(required)

    next_stage = None
    transition_hint = stage.get("next_stage_hint") if stage else None
    if stage_complete and stages:
        for index, item in enumerate(stages):
            if item.get("name") == current_stage and index + 1 < len(stages):
                next_stage = stages[index + 1].get("name")
                current_stage = next_stage
                stage = stage_by_name.get(current_stage, {})
                required = set(stage.get("required_deliverables", []))
                missing = sorted(required - completed_deliverables)
                progress = int(round(100 * (1 - (len(missing) / len(required))))) if required else 0
                stage_complete = not missing and bool(required)
                break

    logger.debug(
        "Stuck check | is_stuck=%s reason=%s",
        stuck_info.get("is_stuck"),
        stuck_info.get("reason"),
    )

    simulation_id = state.get("simulation_id")
    allowed_tools = get_allowed_tools(simulation_id)
    logger.debug("Allowed tools | simulation_id=%s tools=%s", simulation_id, sorted(allowed_tools))

    director_event = _build_director_event(current_stage, framework_loop, stuck_info)
    if director_event:
        logger.debug(
            "Director event | stage=%s repeat_count=%s event=%s",
            current_stage,
            framework_loop.get("repeat_count"),
            director_event,
        )

    updated_sentiment = dict(co_worker_sentiment)

    tool_request = _detect_tool_request(last_user, state.get("current_module"), allowed_tools)
    if tool_request:
        stuck_count = int(user_progress.get("stuck_count", 0))
        if stuck_info["is_stuck"]:
            stuck_count += 1
        else:
            stuck_count = max(stuck_count - 1, 0)

        updated_progress = {
            **user_progress,
            "turn_count": len(user_messages),
            "last_user_message": last_user,
            "stuck_count": stuck_count,
            "stuck_reason": stuck_info["reason"],
        }

        if tool_request.get("action") == "ask":
            _record_supervisor_memory(
                state=state,
                next_agent="end",
                reason="tool clarification needed",
                current_stage=current_stage,
                progress=progress,
                completed_deliverables=completed_deliverables,
            )
            return {
                "messages": [AIMessage(content=tool_request.get("message", "Please provide more details."))],
                "next_agent": "end",
                "recommended_next_agent": "end",
                "director_notes": "Tool clarification needed",
                "director_event": director_event,
                "coworker_memory": coworker_memory,
                "co_worker_sentiment": _evolve_co_worker_sentiment(
                    co_worker_sentiment,
                    state.get("next_agent", "chro"),
                    current_stage,
                    stuck_info,
                    framework_loop,
                    director_event,
                ),
                "user_progress": updated_progress,
                "simulation_stage": current_stage,
                "stage_progress": {current_stage: progress},
                "completed_deliverables": sorted(completed_deliverables),
                "required_next_actions": missing,
            }

        tool_name = tool_request.get("tool_name")
        tool_args = tool_request.get("tool_args") or {}
        call_id = f"call_{uuid4().hex}"
        logger.debug("Supervisor tool request | name=%s args=%s", tool_name, tool_args)

        _record_supervisor_memory(
            state=state,
            next_agent="tools",
            reason=f"tool request: {tool_name}",
            current_stage=current_stage,
            progress=progress,
            completed_deliverables=completed_deliverables,
        )

        return {
            "messages": [AIMessage(content="", tool_calls=[tool_call(name=tool_name, args=tool_args, id=call_id)])],
            "next_agent": "tools",
            "recommended_next_agent": "tools",
            "director_notes": f"Tool request: {tool_name}",
            "director_event": director_event,
            "coworker_memory": coworker_memory,
            "co_worker_sentiment": _evolve_co_worker_sentiment(
                co_worker_sentiment,
                state.get("next_agent", "chro"),
                current_stage,
                stuck_info,
                framework_loop,
                director_event,
            ),
            "user_progress": updated_progress,
            "simulation_stage": current_stage,
            "stage_progress": {current_stage: progress},
            "completed_deliverables": sorted(completed_deliverables),
            "required_next_actions": missing,
        }

    response = llm.invoke(
        prompt.format_messages(
            **{
                **state,
                "simulation_stage": current_stage,
                "stage_description": stage.get("description", ""),
                "stage_preferred_agents": stage_preferred_agents,
                "stage_guidance_weights": stage_guidance_weights,
                "coworker_memory_snapshot": _format_coworker_memory(coworker_memory),
                "co_worker_sentiment_snapshot": _format_sentiment_snapshot(co_worker_sentiment),
                "long_term_memory_snapshot": long_term_context,
                "enabled_coworkers": enabled_coworkers,
                "stuck_signal": stuck_info["is_stuck"],
                "stuck_reason": stuck_info["reason"],
            }
        )
    )

    response_text = getattr(response, "content", "") or ""
    logger.debug(
        "Director raw response | chars=%s snippet=%s",
        len(response_text),
        response_text.replace("\n", " ")[:200],
    )
    
    decision = _parse_director_json(response.content)
    next_agent = str(decision.get("next_agent", "chro")).lower().strip()
    if next_agent not in _ALLOWED_AGENTS:
        next_agent = "chro"

    # MEDIUM: Route Regional for voice diversity if last agent was CHRO
    last_agent = (coworker_memory or {}).get("last_agent", "")
    if next_agent == "chro" and last_agent == "chro" and enabled_coworkers.get("regional", False):
        next_agent = "regional"
        logger.debug(
            "Routing preference | last_agent=%s switching_to=%s reason=voice_diversity",
            last_agent,
            next_agent,
        )

    stage_preferred = None
    enabled_fallback = None

    if enabled_coworkers:
        if next_agent not in enabled_coworkers or not enabled_coworkers.get(next_agent, False):
            stage_preferred = _pick_preferred_agent(stage.get("preferred_agents", []), enabled_coworkers)
            if stage_preferred:
                next_agent = stage_preferred
            else:
                enabled_fallback = _pick_enabled_agent(next_agent, enabled_coworkers)
                next_agent = enabled_fallback

    next_agent = _pick_stage_guarded_agent(stage, enabled_coworkers, current_stage, next_agent)

    logger.debug(
        "Routing decision | raw_next_agent=%s stage_preferred=%s enabled_fallback=%s final_next_agent=%s stage_weights=%s raw_decision=%s",
        str(decision.get("next_agent", "chro")).lower().strip(),
        stage_preferred,
        enabled_fallback,
        next_agent,
        stage_guidance_weights,
        decision,
    )

    updated_sentiment = _evolve_co_worker_sentiment(
        co_worker_sentiment,
        next_agent,
        current_stage,
        stuck_info,
        framework_loop,
        director_event,
    )

    reason = str(decision.get("reason", "")).strip()
    hint = str(decision.get("hint", "")).strip()
    if stuck_info["is_stuck"] and not hint:
        hint = stuck_info["hint"]
    if transition_hint:
        reason = f"{reason} Next: {transition_hint}" if reason else f"Next: {transition_hint}"
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

    logger.debug(
        "Progress update | turn_count=%s stuck_count=%s last_user_message=%s",
        updated_progress.get("turn_count"),
        updated_progress.get("stuck_count"),
        updated_progress.get("last_user_message"),
    )

    _record_supervisor_memory(
        state=state,
        next_agent=next_agent,
        reason=reason,
        current_stage=current_stage,
        progress=progress,
        completed_deliverables=completed_deliverables,
    )

    return {
        "next_agent": next_agent,
        "recommended_next_agent": next_agent,
        "director_notes": reason or "Default to CHRO",
        "director_event": director_event,
        "coworker_memory": coworker_memory,
        "co_worker_sentiment": updated_sentiment,
        "user_progress": updated_progress,
        "simulation_stage": current_stage,
        "stage_progress": {current_stage: progress},
        "completed_deliverables": sorted(completed_deliverables),
        "required_next_actions": missing,
    }


def supervisor_post_check(state: SimulationState):
    """Post-check after agent response, before returning to user."""
    user_messages = _extract_user_messages(state.get("messages"))
    last_user = user_messages[-1] if user_messages else ""
    stuck_info = _detect_stuck(state.get("messages"), state.get("user_progress") or {})

    logger.debug(
        "Post-check | last_user=%s is_stuck=%s reason=%s",
        last_user[:160],
        stuck_info.get("is_stuck"),
        stuck_info.get("reason"),
    )

    director_notes = state.get("director_notes") or ""
    if stuck_info.get("is_stuck") and stuck_info.get("hint"):
        if "Hint:" not in director_notes:
            director_notes = f"{director_notes} Hint: {stuck_info['hint']}".strip()

    current_stage = state.get("simulation_stage") or ""
    required_next = state.get("required_next_actions") or []
    if current_stage == "wrap_up" and not required_next:
        director_notes = f"{director_notes} Ask the user to confirm closure and portfolio export.".strip()

    messages = state.get("messages") or []
    last_msg = messages[-1] if messages else None
    if isinstance(last_msg, ToolMessage):
        llm = get_llm(model_type="local", temperature=0, model_name="qwen2.5:3b")
        summary_prompt = ChatPromptTemplate.from_template("""
        You are the Simulation Director. Provide a concise, helpful response to the user.
        Do not mention tools, internal errors, or tool calls.

        User request: {last_user}
        Tool output: {tool_output}
        """)
        response = llm.invoke(
            summary_prompt.format_messages(
                last_user=last_user,
                tool_output=last_msg.content,
            )
        )
        return {
            "messages": [AIMessage(content=getattr(response, "content", ""))],
            "next_agent": "end",
            "recommended_next_agent": state.get("recommended_next_agent") or state.get("next_agent") or "end",
            "director_notes": director_notes,
            "director_event": state.get("director_event"),
            "coworker_memory": state.get("coworker_memory") or {},
            "user_progress": state.get("user_progress") or {},
            "co_worker_sentiment": state.get("co_worker_sentiment") or {},
        }

    return {
        "next_agent": "end",
        "recommended_next_agent": state.get("recommended_next_agent") or state.get("next_agent") or "end",
        "director_notes": director_notes,
        "director_event": state.get("director_event"),
        "coworker_memory": state.get("coworker_memory") or {},
        "user_progress": state.get("user_progress") or {},
        "co_worker_sentiment": state.get("co_worker_sentiment") or {},
    }