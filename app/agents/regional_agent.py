
from app.agents.base_agent import BaseNPCAgent
from app.core.prompts import REGIONAL_MANAGER_PERSONA

def create_regional_agent(model_type: str = "local", model_name: str = None):
    base = BaseNPCAgent(
        persona=REGIONAL_MANAGER_PERSONA,
        name="Regional Employer Branding Manager",
        temperature=0.5,            # Thực tế, đôi khi blunt
        model_type=model_type,
        model_name=model_name
    )
    return base.create_agent()