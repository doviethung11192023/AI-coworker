# app/agents/chro_agent.py
from app.agents.base_agent import BaseNPCAgent
from app.core.prompts import CHRO_PERSONA

def create_chro_agent(model_type: str = "local", model_name: str = None):
    base = BaseNPCAgent(
        persona=CHRO_PERSONA,
        name="Gucci Group CHRO",
        temperature=0.4,
        model_type=model_type,
        model_name=model_name
    )
    return base.create_agent()