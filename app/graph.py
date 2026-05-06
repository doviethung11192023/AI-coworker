#langGraph workflow
from typing import Literal, Annotated, Dict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from app.core.state import SimulationState
from app.agents.supervisor import supervisor_node
from app.agents.ceo_agent import create_ceo_agent
from app.agents.chro_agent import create_chro_agent
from app.agents.regional_agent import create_regional_agent
from app.agents.tools import tools


# ========================== ROUTING LOGIC ==========================
def route_from_supervisor(state: SimulationState) -> Literal["ceo", "chro", "regional", "tools", END]:
    """Supervisor decides next agent or end"""
    next_agent = state.get("next_agent", "chro")  # Default là CHRO
    enabled = state.get("enabled_coworkers", {})

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

    # Tạo StateGraph
    workflow = StateGraph(SimulationState)

    # ====================== ADD NODES ======================
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("ceo", ceo_agent)
    workflow.add_node("chro", chro_agent)
    workflow.add_node("regional", regional_agent)
    workflow.add_node("tools", tool_node)

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

    # Từ các agent → quay lại Supervisor
    workflow.add_edge("ceo", "supervisor")
    workflow.add_edge("chro", "supervisor")
    workflow.add_edge("regional", "supervisor")
    workflow.add_edge("tools", "supervisor")

    # ====================== COMPILE ======================
    memory = MemorySaver()  # Persistent memory
    
    graph = workflow.compile(
        checkpointer=memory,
        interrupt_before=[]  # Có thể thêm human-in-the-loop sau
    )
    
    return graph


# ========================== GLOBAL INSTANCE ==========================
simulation_graph = build_simulation_graph(model_type="local")  # Mặc định dùng Local Llama-3