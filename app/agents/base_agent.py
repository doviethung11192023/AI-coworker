# app/agents/base_agent.py
from langgraph.prebuilt import create_react_agent
from app.core.llm import get_llm
from app.agents.tools import tools
from langchain_core.prompts import ChatPromptTemplate

class BaseNPCAgent:
    def __init__(
        self, 
        persona: str, 
        name: str, 
        temperature: float = 0.4,
        model_type: str = "local",      # "local", "openai", "claude"
        model_name: str = None
    ):
        self.name = name
        self.model_type = model_type
        self.llm = get_llm(
            model_type=model_type, 
            temperature=temperature,
            model_name=model_name
        )
        self.persona = persona

    def create_agent(self):
        system_prompt = f"""{self.persona}

You are {self.name}, a Co-worker inside Edtronaut's Job Simulation Platform.
Current role: Helping the user (Group Global OD Director) design Gucci Group's Leadership System.
Stay strictly in character at all times. Never mention you are an AI or break role.
Be professional, realistic, and consistent with your personality and constraints.

Safety guardrails:
- Provide draft suggestions only; ask the user to verify sources and confirm before finalizing.
- Use neutral, responsible phrasing; avoid wagering language or guaranteed outcomes.
- If the user goes off-topic or requests unsafe content, refuse briefly and redirect to the task."""
        prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}")# 🔥 bắt buộc cho ReAct agent
    ])
        agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=prompt
        )
        return agent
    
