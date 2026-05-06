# app/agents/ceo_agent.py
from app.agents.base_agent import BaseNPCAgent
from app.core.prompts import CEO_PERSONA

def create_ceo_agent(model_type: str = "local", model_name: str = None):
    base = BaseNPCAgent(
        persona=CEO_PERSONA,
        name="Gucci Group CEO",
        temperature=0.35,           # Quyết đoán, ít sáng tạo hơn
        model_type=model_type,
        model_name=model_name
    )
    return base.create_agent()