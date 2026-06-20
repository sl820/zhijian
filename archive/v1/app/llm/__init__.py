"""
LLM 模块 - 本地大模型推理支持

支持:
- Ollama (REST API，本地部署推荐)
- llama.cpp (GGUF 格式，需要编译)
"""

from .ollama_client import OllamaClient, get_llm, reset_llm
from .llama_cpp_client import LlamaCPPClient

__all__ = ["OllamaClient", "LlamaCPPClient", "get_llm", "reset_llm"]
