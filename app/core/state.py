
from typing import TypedDict, Annotated, List, Dict, Optional
from langgraph.graph.message import add_messages

class SimulationState(TypedDict):
    messages: Annotated[List, add_messages]
    simulation_id: str
    current_module: int
    user_progress: Dict
    co_worker_sentiment: Dict[str, str]      # ví dụ: {"ceo": "neutral"}
    enabled_coworkers: Dict[str, bool]
    next_agent: str
    director_notes: Optional[str]