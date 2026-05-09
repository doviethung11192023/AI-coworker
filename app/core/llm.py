
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
# from langchain_anthropic import ChatAnthropic
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def get_llm(
    model_type: str = "local", 
    temperature: float = 0.4,
    model_name: Optional[str] = None
):
    """
    Unified LLM provider supporting local and cloud models.
    """
    if model_type == "local":
        model = model_name or "qwen2.5:3b"
        num_ctx = 2048
        timeout_s = 120.0
        logger.debug(
            "Init ChatOllama | model=%s num_ctx=%s timeout=%s",
            model,
            num_ctx,
            timeout_s,
        )
        return ChatOllama(
            model=model,
            temperature=temperature,
            num_ctx=num_ctx,           # Context window
            num_predict=512,
            keep_alive="5m",
            client_kwargs={"timeout": timeout_s},
            verbose=False,
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