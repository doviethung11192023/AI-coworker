
from typing import TypedDict, Annotated, List, Dict, Optional
from langgraph.graph.message import add_messages

class SimulationState(TypedDict):
    messages: Annotated[List, add_messages]
    simulation_id: str
    thread_id: Optional[str]
    current_module: int
    user_progress: Dict
    co_worker_sentiment: Dict[str, str]      # ví dụ: {"ceo": "neutral"}
    enabled_coworkers: Dict[str, bool]
    next_agent: str
    recommended_next_agent: Optional[str]
    director_notes: Optional[str]
    director_event: Optional[Dict]
    coworker_memory: Optional[Dict]
    simulation_stage: Optional[str]
    stage_progress: Dict[str, int]
    completed_deliverables: List[str]
    required_next_actions: List[str]