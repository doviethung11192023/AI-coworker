import json
import os
from functools import lru_cache
from typing import Dict, Any


@lru_cache(maxsize=32)
def load_simulation_config(simulation_id: str | None) -> Dict[str, Any]:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if simulation_id:
        config_path = os.path.join(base_dir, "simulations", simulation_id, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as handle:
                return json.load(handle)

    return {
        "simulation_id": simulation_id or "default",
        "stages": [
            {
                "name": "discovery",
                "description": "Initial discovery",
                "required_deliverables": [],
                "preferred_agents": ["chro"],
                "focus": "problem_framing",
            }
        ],
        "deliverables": [],
    }
