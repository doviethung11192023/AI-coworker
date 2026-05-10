
from typing import Literal, Annotated, Dict
import re
import logging
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, SystemMessage
from app.core.state import SimulationState
from app.agents.supervisor import supervisor_node, supervisor_post_check
from app.agents.ceo_agent import create_ceo_agent
from app.agents.chro_agent import create_chro_agent
from app.agents.regional_agent import create_regional_agent
from app.agents.tools import tools
from app.memory.vector_store import add_memory_entry, query_memory

logger = logging.getLogger(__name__)


def _message_summary(messages, limit: int = 3, max_chars: int = 120):
    if not messages:
        return []
    items = []
    for msg in messages[-limit:]:
        if isinstance(msg, (list, tuple)) and len(msg) >= 2:
            role, content = msg[0], msg[1]
        else:
            role = getattr(msg, "type", None) or getattr(msg, "role", None) or "unknown"
            content = getattr(msg, "content", None)
            if content is None and isinstance(msg, dict):
                content = msg.get("content")
        if not isinstance(content, str):
            content = "" if content is None else str(content)
        items.append({
            "role": role,
            "content": content.replace("\n", " ")[:max_chars],
        })
    return items


def _summarize_text(text: str, max_chars: int = 240) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    summary = " ".join(sentences[:2]).strip() or text
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3].rstrip() + "..."
    return summary


def _build_peer_context(coworker_memory: dict | None, current_agent: str) -> str:
    coworker_memory = coworker_memory or {}
    latest_stances = coworker_memory.get("latest_stances") or {}
    if not latest_stances:
        return ""

    lines = []
    for peer_name in ["ceo", "chro", "regional"]:
        if peer_name == current_agent:
            continue
        stance = latest_stances.get(peer_name)
        if stance:
            lines.append(f"- {peer_name.upper()}: {stance}")

    if not lines:
        return ""

    return (
        "Shared coworker memory from previous agents:\n"
        + "\n".join(lines)
        + "\nUse this to react to what the other coworkers already established."
    )


def _build_long_term_memory_context(
    last_user_text: str,
    simulation_id: str | None,
    thread_id: str | None,
    current_module: int | None,
) -> str:
    if not last_user_text:
        return ""

    recalls = query_memory(
        last_user_text,
        simulation_id=simulation_id,
        thread_id=thread_id,
        module=current_module,
        n_results=2,
    )
    if not recalls:
        return ""

    lines = []
    for content, metadata in recalls:
        kind = (metadata or {}).get("kind", "memory")
        agent_name = (metadata or {}).get("agent_name", "unknown")
        lines.append(f"- [{kind}] {agent_name}: {content}")

    return (
        "Relevant long-term memory from prior turns:\n"
        + "\n".join(lines)
        + "\nUse this memory only when it is clearly relevant to the current request."
    )


def _emotion_effect_text(emotion: str) -> str:
    emotion = (emotion or "collaborative").lower().strip()
    # CRITICAL: These behavioral cues directly affect output length, tone, and directness
    mapping = {
        "collaborative": (
            "MODE: PROBLEM-SOLVING PARTNER\n"
            "- Be warm, constructive, and solution-focused\n"
            "- Share rich context and examples to build understanding\n"
            "- Stay open to tradeoffs and creative combinations\n"
            "- Response length: 2-3 paragraphs, thorough\n"
            "- Tone: Supportive, encouraging, team-oriented"
        ),
        "skeptical": (
            "MODE: CRITICAL EVALUATOR\n"
            "- Challenge weak assumptions and oversimplifications\n"
            "- Demand evidence before agreeing; point out political/organizational risks\n"
            "- Keep responses SHORT: 1-2 focused points maximum\n"
            "- Tone: Direct, questioning, focused on risks\n"
            "- Response length: 1-2 concise paragraphs only"
        ),
        "defensive": (
            "MODE: CONSTRAINT PROTECTOR\n"
            "- Firmly protect brand identity, regulatory constraints, and operational limits\n"
            "- Resist concessions that compromise core values\n"
            "- Keep responses very short, defensive, non-negotiable\n"
            "- Tone: Resistant, firm, unyielding on core issues\n"
            "- Response length: 1 paragraph maximum, bullet points if needed"
        ),
        "impatient": (
            "MODE: EXECUTIVE DECISION-MAKER\n"
            "- Skip context; focus ONLY on the decision point\n"
            "- Ask one sharp, probing question instead of long responses\n"
            "- Be terse, businesslike, no small talk\n"
            "- Response length: 1-2 sentences or one hard question\n"
            "- Tone: Brisk, no-nonsense, results-oriented"
        ),
        "neutral": (
            "MODE: BALANCED EXECUTIVE\n"
            "- Weigh pros and cons fairly\n"
            "- Give clear executive recommendation\n"
            "- Response length: 1-2 paragraphs with balanced view\n"
            "- Tone: Professional, measured, fair"
        ),
    }
    return mapping.get(emotion, mapping["collaborative"])


def _build_emotion_context(agent_name: str, co_worker_sentiment: dict | None) -> str:
    co_worker_sentiment = co_worker_sentiment or {}
    emotion = co_worker_sentiment.get(agent_name, "collaborative")
    peer_emotions = []
    for peer_name in ["ceo", "chro", "regional"]:
        if peer_name == agent_name:
            continue
        peer_emotion = co_worker_sentiment.get(peer_name)
        if peer_emotion:
            peer_emotions.append(f"- {peer_name.upper()}: {peer_emotion}")

    peer_text = "\n".join(peer_emotions) if peer_emotions else "None"
    return (
        f"=== EMOTIONAL STATE (STRICT COMPLIANCE REQUIRED) ===\n"
        f"Your current mood: {emotion.upper()}\n"
        f"{_emotion_effect_text(emotion)}\n\n"
        f"Other coworkers' current moods:\n{peer_text}\n\n"
        f"CRITICAL: Your emotional state MUST affect output length and directness.\n"
        f"If SKEPTICAL: Keep under 200 words, challenge the idea, point to risks.\n"
        f"If DEFENSIVE: Keep under 150 words, protect constraints firmly.\n"
        f"If IMPATIENT: Keep to 1-2 sentences, ask one hard question only.\n"
        f"If COLLABORATIVE: Up to 300 words, be thorough and supportive."
    )


def _infer_emotion_from_text(text: str, default_emotion: str = "collaborative") -> str:
    lowered = (text or "").lower()
    if any(token in lowered for token in ["cannot", "won't", "won’t", "not compromise", "we need to", "must", "risk"]):
        if any(token in lowered for token in ["but", "however", "yet"]):
            return "skeptical"
        return "defensive"
    if any(token in lowered for token in ["need to decide", "one question", "answer directly", "focus", "priority"]):
        return "impatient"
    if any(token in lowered for token in ["agree", "we can", "let's", "recommend", "support"]):
        return "collaborative"
    return default_emotion


# ========================== ROUTING LOGIC ==========================
def route_from_supervisor(state: SimulationState) -> Literal["ceo", "chro", "regional", "tools"] | str:
    """Supervisor decides next agent or end"""
    next_agent = state.get("next_agent", "chro")  # Default là CHRO
    enabled = state.get("enabled_coworkers", {})

    logger.debug("Route from supervisor | next_agent=%s enabled=%s", next_agent, enabled)

    if enabled and next_agent in ["ceo", "chro", "regional"]:
        if not enabled.get(next_agent, False):
            for candidate in ["chro", "ceo", "regional"]:
                if enabled.get(candidate, False):
                    return candidate
            return END
    
    if next_agent in ["ceo", "chro", "regional"]:
        return next_agent
    if next_agent == "tools":
        return "tools"
    return END


def route_after_agent(state: SimulationState) -> Literal["supervisor"]:
    """Sau khi Co-worker trả lời → quay lại Supervisor kiểm tra"""
    return "supervisor"


# ========================== BUILD GRAPH ==========================
def build_simulation_graph(model_type: str = "local"):
    
    # Khởi tạo các agents
    ceo_agent = create_ceo_agent(model_type=model_type)
    chro_agent = create_chro_agent(model_type=model_type)
    regional_agent = create_regional_agent(model_type=model_type)

    # Tool node
    tool_node = ToolNode(tools=tools)

    def _wrap_agent(name: str, agent):
        def _node(state: SimulationState):
            # FIX #1: Log the actual co_worker_sentiment received by agent to debug lag
            sentiment_state = state.get("co_worker_sentiment", {})
            agent_emotion = sentiment_state.get(name, "collaborative")
            logger.debug(
                "Agent start | name=%s sentiment_received=%s agent_emotion=%s messages=%s",
                name,
                sentiment_state,
                agent_emotion,
                _message_summary(state.get("messages"))
            )
            agent_state = dict(state)
            user_messages = [msg for msg in (state.get("messages") or []) if getattr(msg, "type", None) in {"human", "user"} or (isinstance(msg, (list, tuple)) and msg and msg[0] in {"human", "user"})]
            last_user_text = ""
            if user_messages:
                last_user = user_messages[-1]
                if isinstance(last_user, (list, tuple)) and len(last_user) >= 2:
                    last_user_text = str(last_user[1])
                else:
                    last_user_text = str(getattr(last_user, "content", ""))
            
            # INJECT STAGE CONTEXT for stage gate enforcement
            current_stage = state.get("simulation_stage", "discovery")
            required_actions = state.get("required_next_actions", [])
            stage_context_msg = (
                f"[STAGE CONTEXT FOR {name.upper()}] Current stage: {current_stage} | "
                f"Required next actions: {', '.join(required_actions) if required_actions else 'None yet'}"
            )
            agent_state["messages"] = [SystemMessage(content=stage_context_msg)] + list(agent_state.get("messages") or [])
            
            emotion_context = _build_emotion_context(name, state.get("co_worker_sentiment"))
            if emotion_context:
                agent_state["messages"] = [SystemMessage(content=emotion_context)] + list(agent_state.get("messages") or [])
            peer_context = _build_peer_context(state.get("coworker_memory"), name)
            if peer_context:
                agent_state["messages"] = [SystemMessage(content=peer_context)] + list(agent_state.get("messages") or [])
            long_term_context = _build_long_term_memory_context(
                last_user_text,
                state.get("simulation_id"),
                state.get("thread_id"),
                state.get("current_module"),
            )
            if long_term_context:
                agent_state["messages"] = [SystemMessage(content=long_term_context)] + list(agent_state.get("messages") or [])
            director_event = state.get("director_event") or {}
            if director_event:
                director_message = director_event.get("message")
                if director_message:
                    event_speaker = director_event.get("speaker", "director")
                    hidden_objective = director_event.get("hidden_objective")
                    event_text = f"Director intervention [{event_speaker}]: {director_message}"
                    if hidden_objective:
                        event_text = f"{event_text} Hidden objective: {hidden_objective}"
                    agent_state["messages"] = list(agent_state.get("messages") or []) + [AIMessage(content=event_text, name="director")]
                    logger.debug("Agent director event | name=%s event=%s", name, director_event)
            result = agent.invoke(agent_state)
            result_messages = result.get("messages") if isinstance(result, dict) else None
            logger.debug("Agent end | name=%s messages=%s", name, _message_summary(result_messages))
            updated_memory = dict(state.get("coworker_memory") or {})
            latest_stances = dict(updated_memory.get("latest_stances") or {})
            updated_sentiment = dict(state.get("co_worker_sentiment") or {})
            agent_output_text = ""
            if result_messages:
                last_message = result_messages[-1]
                agent_output_text = getattr(last_message, "content", str(last_message))
            summary = _summarize_text(agent_output_text)
            current_emotion = updated_sentiment.get(name, "collaborative")
            next_emotion = _infer_emotion_from_text(agent_output_text, current_emotion)
            updated_sentiment[name] = next_emotion
            if summary:
                latest_stances[name] = summary
                updated_memory["latest_stances"] = latest_stances
                updated_memory["last_agent"] = name
                updated_memory["last_summary"] = summary
                logger.debug("Coworker memory update | name=%s summary=%s", name, summary)
                add_memory_entry(
                    summary,
                    kind="coworker_stance",
                    simulation_id=state.get("simulation_id"),
                    thread_id=state.get("thread_id"),
                    module=state.get("current_module"),
                    agent_name=name,
                    metadata={
                        "emotion": next_emotion,
                        "stage": state.get("simulation_stage"),
                    },
                )
            logger.debug("Emotion memory update | name=%s before=%s after=%s", name, current_emotion, next_emotion)

            if isinstance(result, dict):
                result["coworker_memory"] = updated_memory
                result["co_worker_sentiment"] = updated_sentiment
                return result

            return {
                "messages": result_messages or [],
                "coworker_memory": updated_memory,
                "co_worker_sentiment": updated_sentiment,
            }
        return _node

    def _tools_node(state: SimulationState):
        logger.debug("Tools start | messages=%s", _message_summary(state.get("messages")))
        result = tool_node.invoke(state)
        result_messages = result.get("messages") if isinstance(result, dict) else None
        logger.debug("Tools end | messages=%s", _message_summary(result_messages))
        return result

    # Tạo StateGraph
    workflow = StateGraph(SimulationState)

    # ====================== ADD NODES ======================
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("supervisor_post", supervisor_post_check)
    workflow.add_node("ceo", _wrap_agent("ceo", ceo_agent))  # Supervisor sẽ gọi CEO agent
    workflow.add_node("chro", _wrap_agent("chro", chro_agent))  # Supervisor sẽ gọi CHRO agent
    workflow.add_node("regional", _wrap_agent("regional", regional_agent))  # Supervisor sẽ gọi Regional agent
    workflow.add_node("tools", _tools_node)

    # ====================== ADD EDGES ======================
    workflow.add_edge(START, "supervisor")

    # Từ Supervisor → các agent
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "ceo": "ceo",
            "chro": "chro",
            "regional": "regional",
            "tools": "tools",
            END: END,
        }
    )

    # Từ các agent → supervisor post-check → kết thúc
    workflow.add_edge("ceo", "supervisor_post")
    workflow.add_edge("chro", "supervisor_post")
    workflow.add_edge("regional", "supervisor_post")
    workflow.add_edge("tools", "supervisor_post")

    workflow.add_edge("supervisor_post", END)

    # ====================== COMPILE ======================
    memory = MemorySaver()  # Persistent memory
    
    graph = workflow.compile(
        checkpointer=memory,
        interrupt_before=[]  # Có thể thêm human-in-the-loop sau
    )
    
    return graph


# ========================== GLOBAL INSTANCE ==========================
simulation_graph = build_simulation_graph(model_type="local")  # Mặc định dùng Local Llama-3