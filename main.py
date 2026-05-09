
import asyncio
import uvicorn
import logging
import os
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
import uuid

from app.graph import simulation_graph
from app.core.state import SimulationState
from app.utils.safe import build_safety_flags

# ========================== FASTAPI APP ==========================
app = FastAPI(
    title="Edtronaut AI Co-Worker Engine",
    description="AI NPC Engine powering realistic job simulations",
    version="1.0.0"
)

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
logger = logging.getLogger(__name__)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong production nên giới hạn
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================== REQUEST MODELS ==========================
class ChatRequest(BaseModel):
    message: str
    simulation_id: Optional[str] = None
    thread_id: Optional[str] = None
    current_module: int = 1
    model_type: str = "local"   # "local", "openai", "claude"
    enable_ceo: bool = True
    enable_chro: bool = True
    enable_regional: bool = True


class ChatResponse(BaseModel):
    response: str
    co_worker: str
    next_suggested_agent: str
    director_notes: Optional[str] = None
    thread_id: str
    safety_flags: Optional[Dict[str, bool]] = None
    simulation_stage: Optional[str] = None
    stage_progress: Optional[Dict[str, int]] = None
    completed_deliverables: Optional[list[str]] = None
    required_next_actions: Optional[list[str]] = None


def _apply_guardrails(text: str) -> str:
    flags = build_safety_flags(text)
    additions = []
    if not flags.get("draft_language_present"):
        additions.append("This is a draft for internal discussion only.")
    if not flags.get("source_confirmation_present"):
        additions.append("Please confirm sources before final use.")
    if additions:
        suffix = "\n".join(additions)
        if text.endswith("\n"):
            return f"{text}\n{suffix}"
        return f"{text}\n\n{suffix}"
    return text


def _co_worker_from_state(output: dict) -> str:
    coworker_memory = output.get("coworker_memory") or {}
    last_agent = str(coworker_memory.get("last_agent", "")).lower().strip()
    if last_agent == "ceo":
        return "CEO"
    if last_agent == "chro":
        return "CHRO"
    if last_agent == "regional":
        return "Regional Manager"
    return "Unknown"


def _build_chat_context(request: ChatRequest):
    thread_id = request.thread_id or str(uuid.uuid4())
    simulation_id = request.simulation_id or "gucci-leadership-08"
    config = {"configurable": {"thread_id": thread_id}}
    previous_state = {}
    try:
        snapshot = simulation_graph.get_state(config)
        previous_state = snapshot.values if snapshot and snapshot.values else {}
    except Exception:
        previous_state = {}

    logger.debug(
        "Chat memory load | thread_id=%s has_previous_state=%s prev_user_progress=%s prev_stage=%s prev_sentiment=%s",
        thread_id,
        bool(previous_state),
        previous_state.get("user_progress", {}),
        previous_state.get("simulation_stage"),
        previous_state.get("co_worker_sentiment", {}),
    )

    inputs: SimulationState = {
        "messages": [("user", request.message)],
        "simulation_id": simulation_id,
        "thread_id": thread_id,
        "current_module": request.current_module,
        "user_progress": previous_state.get("user_progress", {}),
        "co_worker_sentiment": previous_state.get("co_worker_sentiment", {}),
        "simulation_stage": previous_state.get("simulation_stage"),
        "stage_progress": previous_state.get("stage_progress", {}),
        "completed_deliverables": previous_state.get("completed_deliverables", []),
        "required_next_actions": previous_state.get("required_next_actions", []),
        "director_event": previous_state.get("director_event"),
        "coworker_memory": previous_state.get("coworker_memory", {}),
        "enabled_coworkers": {
            "ceo": request.enable_ceo,
            "chro": request.enable_chro,
            "regional": request.enable_regional,
        },
        "next_agent": previous_state.get("next_agent", "chro"),
        "director_notes": previous_state.get("director_notes"),
    }

    return thread_id, simulation_id, config, inputs


def _build_chat_response(output: dict, thread_id: str, simulation_id: str) -> ChatResponse:
    last_message = output["messages"][-1]
    content = _apply_guardrails(getattr(last_message, "content", str(last_message)))
    co_worker = _co_worker_from_state(output)
    safety_flags = build_safety_flags(content)
    recommended_next_agent = output.get("recommended_next_agent") or output.get("next_agent", "chro")

    response = ChatResponse(
        response=content,
        co_worker=co_worker,
        next_suggested_agent=recommended_next_agent,
        director_notes=output.get("director_notes"),
        thread_id=thread_id,
        safety_flags=safety_flags,
        simulation_stage=output.get("simulation_stage"),
        stage_progress=output.get("stage_progress"),
        completed_deliverables=output.get("completed_deliverables"),
        required_next_actions=output.get("required_next_actions"),
    )

    raw = {
        "thread_id": thread_id,
        "simulation_id": simulation_id,
        "output": output,
        "content": content,
        "co_worker": co_worker,
        "safety_flags": safety_flags,
    }
    return response, raw


def _chunk_text(text: str, chunk_size: int = 24) -> list[str]:
    text = text or ""
    if not text:
        return []
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


# ========================== ENDPOINTS ==========================
@app.post("/chat", response_model=ChatResponse)
async def chat_with_co_worker(request: ChatRequest):
    """
    Main endpoint: User gửi tin nhắn → Nhận phản hồi từ AI Co-worker
    """
    try:
        thread_id, simulation_id, config, inputs = _build_chat_context(request)
        output = simulation_graph.invoke(inputs, config)
        logger.debug(
            "Chat memory output | thread_id=%s next_agent=%s user_progress=%s stage=%s stage_progress=%s completed=%s required_next=%s sentiment=%s coworker_memory=%s director_event=%s",
            thread_id,
            output.get("next_agent"),
            output.get("user_progress", {}),
            output.get("simulation_stage"),
            output.get("stage_progress", {}),
            output.get("completed_deliverables", []),
            output.get("required_next_actions", []),
            output.get("co_worker_sentiment", {}),
            output.get("coworker_memory", {}),
            output.get("director_event"),
        )
        response, _ = _build_chat_response(output, thread_id, simulation_id)
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            request = ChatRequest(**payload)
            thread_id, simulation_id, config, inputs = _build_chat_context(request)

            await websocket.send_json({
                "type": "started",
                "thread_id": thread_id,
                "simulation_id": simulation_id,
            })

            await websocket.send_json({"type": "status", "message": "Thinking..."})

            streamed_text = []
            stream = simulation_graph.astream_events(inputs, config, version="v2")
            async for event in stream:
                if event.get("event") != "on_chat_model_stream":
                    continue

                metadata = event.get("metadata") or {}
                node_name = metadata.get("langgraph_node")
                if node_name not in {"agent", "ceo", "chro", "regional", "supervisor_post"}:
                    continue

                chunk = (event.get("data") or {}).get("chunk")
                token = getattr(chunk, "content", "") if chunk is not None else ""
                if not token:
                    continue

                streamed_text.append(token)
                await websocket.send_json({"type": "chunk", "content": token, "node": node_name})

            snapshot = simulation_graph.get_state(config)
            output = snapshot.values if snapshot and snapshot.values else {}
            logger.debug(
                "Chat memory output | thread_id=%s next_agent=%s user_progress=%s stage=%s stage_progress=%s completed=%s required_next=%s sentiment=%s coworker_memory=%s director_event=%s",
                thread_id,
                output.get("next_agent"),
                output.get("user_progress", {}),
                output.get("simulation_stage"),
                output.get("stage_progress", {}),
                output.get("completed_deliverables", []),
                output.get("required_next_actions", []),
                output.get("co_worker_sentiment", {}),
                output.get("coworker_memory", {}),
                output.get("director_event"),
            )
            response, raw = _build_chat_response(output, thread_id, simulation_id)

            await websocket.send_json({
                "type": "meta",
                "thread_id": raw["thread_id"],
                "simulation_id": raw["simulation_id"],
                "co_worker": raw["co_worker"],
                "next_suggested_agent": response.next_suggested_agent,
                "director_notes": response.director_notes,
                "simulation_stage": response.simulation_stage,
                "stage_progress": response.stage_progress,
                "completed_deliverables": response.completed_deliverables,
                "required_next_actions": response.required_next_actions,
                "safety_flags": response.safety_flags,
            })

            await websocket.send_json({
                "type": "done",
                "response": response.response,
                "thread_id": response.thread_id,
            })
    except WebSocketDisconnect:
        return


@app.get("/health")
async def health_check():
    return {"status": "healthy", "engine": "Edtronaut AI Co-Worker Engine"}


@app.get("/simulations/{simulation_id}/threads/{thread_id}")
async def get_conversation_history(simulation_id: str, thread_id: str):
    """Lấy lịch sử cuộc trò chuyện (debug & portfolio)"""
    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = simulation_graph.get_state(config)
        return {
            "simulation_id": simulation_id,
            "thread_id": thread_id,
            "messages": state.values.get("messages", [])
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail="Conversation not found")


# ========================== RUN APP ==========================
if __name__ == "__main__":
    print("🚀 Starting Edtronaut AI Co-Worker Engine...")
    print("📍 Local: http://localhost:8000")
    print("📚 Docs: http://localhost:8000/docs")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )