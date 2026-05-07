
import uvicorn
from fastapi import FastAPI, HTTPException
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


# ========================== ENDPOINTS ==========================
@app.post("/chat", response_model=ChatResponse)
async def chat_with_co_worker(request: ChatRequest):
    """
    Main endpoint: User gửi tin nhắn → Nhận phản hồi từ AI Co-worker
    """
    try:
        # Tạo thread_id nếu chưa có (dùng để lưu conversation state)
        thread_id = request.thread_id or str(uuid.uuid4())
        simulation_id = request.simulation_id or "gucci-leadership-08"

        # Input cho LangGraph
        inputs: SimulationState = {
            "messages": [("user", request.message)],
            "simulation_id": simulation_id,
            "current_module": request.current_module,
            "user_progress": {},
            "co_worker_sentiment": {},
            "enabled_coworkers": {
                "ceo": request.enable_ceo,
                "chro": request.enable_chro,
                "regional": request.enable_regional,
            },
            "next_agent": "chro",           # Default
            "director_notes": None
        }

        # Config cho LangGraph (persistent memory)
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        # Chạy graph
        output = simulation_graph.invoke(inputs, config)

        # Lấy tin nhắn cuối cùng
        last_message = output["messages"][-1]
        
        content = getattr(last_message, "content", str(last_message))

        # Xác định AI Co-worker đang trả lời
        co_worker = "Unknown"
        if "ceo" in str(last_message).lower():
            co_worker = "CEO"
        elif "chro" in str(last_message).lower():
            co_worker = "CHRO"
        elif "regional" in str(last_message).lower():
            co_worker = "Regional Manager"

        safety_flags = build_safety_flags(content)

        return ChatResponse(
            response=content,
            co_worker=co_worker,
            next_suggested_agent=output.get("next_agent", "chro"),
            director_notes=output.get("director_notes"),
            thread_id=thread_id,
            safety_flags=safety_flags,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


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