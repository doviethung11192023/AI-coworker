
from langchain_community.chat_models import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
# from langchain_anthropic import ChatAnthropic

def get_llm(model_type: str = "local", temperature: float = 0.4):
    """
    model_type: "local", "openai", "claude"
    """
    if model_type == "local":
        return ChatOllama(
            model="qwen2.5:3b",   # hoặc llama3.1:70b
            temperature=temperature,
            # num_ctx=8192,
            num_ctx=2048,
            # base_url="http://localhost:11434"
        )
    
    elif model_type == "claude":
        return ChatAnthropic(
            model="claude-3-5-sonnet-20240620",
            temperature=temperature
        )
    
    else:  # openai
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=temperature
        )