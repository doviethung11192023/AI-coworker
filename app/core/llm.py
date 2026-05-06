# app/core/llm.py
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
# from langchain_anthropic import ChatAnthropic
from typing import Optional

def get_llm(
    model_type: str = "local", 
    temperature: float = 0.4,
    model_name: Optional[str] = None
):
    """
    Unified LLM provider supporting local and cloud models.
    """
    if model_type == "local":
        return ChatOllama(
            model=model_name or "llama3.1:8b",
            temperature=temperature,
            num_ctx=8192,           # Context window
            verbose=False
        )
    
    elif model_type == "claude":
        return ChatAnthropic(
            model=model_name or "claude-3-5-sonnet-20240620",
            temperature=temperature
        )
    
    else:  # openai (default fallback)
        return ChatOpenAI(
            model=model_name or "gpt-4o-mini",
            temperature=temperature
        )