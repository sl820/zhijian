"""
LLM Generator for RAG-based 古籍问答 (Ancient Text QA)
"""

import logging
import os
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Lazy-initialized global generator instance
_generator_instance = None

# Default configuration
DEFAULT_CONFIG = {
    "provider": "ollama",  # openai, deepseek, kimi, ollama
    "model": None,  # None means use provider default
    "temperature": 0.3,
    "max_tokens": 2048,
    "timeout": 120,
}

# Provider model mappings
PROVIDER_MODELS = {
    "openai": "gpt-4",
    "deepseek": "deepseek-chat",
    "kimi": "moonshot-v1-8k",
    "ollama": "qwen2.5:3b",  # 阿里通义千问，中文支持优秀
}

# API endpoints
API_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "kimi": "https://api.moonshot.cn/v1/chat/completions",
}

# System prompt for 古籍问答
SYSTEM_PROMPT = """你是一位专业的古籍方志研究助手，熟悉中国古代地方志的体例与内容，擅长从《方志》文本中提取信息回答问题。

回答要求：
1. **优先基于所给的上下文（context）进行回答**。如果上下文中包含与问题相关的信息，即使表述不完全一致，也应尝试从已有信息中提取、组织、概括出答案。
2. 仅当上下文中**完全没有**相关信息时，才回答"根据提供的资料无法回答此问题"。
3. 回答应简洁、准确，必要时直接引用原文片段（用引号标出）。
4. 涉及人物、地名、年代、事件等问题时，应给出具体信息（人名、地名、朝代、年号等）。
5. 保持回答的学术性和准确性，但不要过度推演；只回答上下文能直接支持的内容。

上下文信息：
"""


def get_generator(config: Optional[Dict] = None):
    """Get or create the lazy-initialized Generator instance."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = Generator(config)
    return _generator_instance


def reset_generator():
    """Reset the generator instance (useful for testing or config changes)."""
    global _generator_instance
    _generator_instance = None


class Generator:
    """
    LLM-based answer generator for RAG.

    Supports multiple LLM backends:
    - OpenAI (GPT-4)
    - DeepSeek (deepseek-chat)
    - Kimi (moonshot-v1-8k)
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the Generator with configuration.

        Args:
            config: Optional configuration dict. If not provided, uses environment
                   variables or defaults. Config keys:
                   - provider: LLM provider ("openai", "deepseek", "kimi")
                   - model: Model name (uses provider default if not specified)
                   - temperature: Sampling temperature (default: 0.3)
                   - max_tokens: Maximum tokens to generate (default: 2048)
                   - timeout: API request timeout in seconds (default: 120)
                   - api_key: API key (can also be set via env var)
        """
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self._provider = self.config.get("provider", "deepseek")
        self._model = self.config.get("model") or PROVIDER_MODELS.get(self._provider)
        self._temperature = float(self.config.get("temperature", 0.3))
        self._max_tokens = int(self.config.get("max_tokens", 2048))
        self._timeout = int(self.config.get("timeout", 120))
        self._api_key = self._get_api_key()
        self._ollama = None  # 本地 Ollama 客户端

        logger.info(f"Generator initialized with provider={self._provider}, model={self._model}")

        # 初始化 Ollama 本地模型
        if self._provider == "ollama":
            try:
                from ..llm.ollama_client import OllamaClient
                self._ollama = OllamaClient(self.config)
                logger.info("Ollama 本地模型初始化成功")
            except ConnectionError as e:
                logger.warning(f"Ollama 服务未运行: {e}")
                logger.warning("将使用云端API作为备选")
            except Exception as e:
                logger.warning(f"Ollama 初始化失败: {e}")
                logger.warning("将使用云端API作为备选")

    def _get_api_key(self) -> str:
        """Get API key from config or environment variables."""
        # Ollama doesn't need an API key
        if self._provider == "ollama":
            return ""

        # Check config first
        api_key = self.config.get("api_key")
        if api_key:
            return api_key

        # Check environment variables based on provider
        env_var_map = {
            "openai": "OPENAI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "kimi": "KIMI_API_KEY",
        }
        env_var = env_var_map.get(self._provider, "OPENAI_API_KEY")
        api_key = os.environ.get(env_var)
        if api_key:
            return api_key

        # For OpenAI, also check generic OPENAI_API_KEY
        if self._provider == "openai":
            return os.environ.get("OPENAI_API_KEY", "")

        logger.warning(f"No API key found for provider {self._provider}")
        return ""

    def _build_messages(self, question: str, context: List[Dict]) -> List[Dict]:
        """
        Build the messages list for the LLM API.

        Args:
            question: The user's question
            context: List of context dicts with 'text' and optionally 'source', 'score'

        Returns:
            List of message dicts for the API
        """
        # Format context into a readable string
        context_parts = []
        for i, ctx in enumerate(context, 1):
            text = ctx.get("text", "")
            source = ctx.get("source", "未知来源")
            context_parts.append(f"[{i}] 来源：{source}\n{text}")

        context_text = "\n\n".join(context_parts)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"问题：{question}\n\n请根据以下上下文回答：\n{context_text}"}
        ]

        return messages

    def _call_openai_compatible_api(self, messages: List[Dict]) -> str:
        """
        Call the LLM API (OpenAI-compatible format).

        Args:
            messages: List of message dicts

        Returns:
            Generated answer string

        Raises:
            RuntimeError: If API call fails
        """
        import json
        import urllib.request
        import urllib.error

        endpoint = API_ENDPOINTS.get(self._provider, API_ENDPOINTS["openai"])

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            logger.error(f"API HTTP error {e.code}: {error_body}")
            raise RuntimeError(f"LLM API error: HTTP {e.code} - {error_body}")

        except urllib.error.URLError as e:
            logger.error(f"API URL error: {e.reason}")
            raise RuntimeError(f"LLM API connection error: {e.reason}")

        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"API response parsing error: {e}")
            raise RuntimeError(f"Failed to parse LLM API response: {e}")

        except Exception as e:
            logger.error(f"Unexpected API error: {e}")
            raise RuntimeError(f"LLM API unexpected error: {e}")

    def generate(self, question: str, context: List[Dict]) -> str:
        """
        Generate an answer based on the question and retrieved context.

        Args:
            question: The user's question about ancient texts
            context: List of context dicts, each containing:
                     - text: The context text content
                     - source: (optional) Source document or reference
                     - score: (optional) Relevance score

        Returns:
            Generated answer string

        Raises:
            RuntimeError: If generation fails
        """
        if not question:
            raise ValueError("Question cannot be empty")

        # 优先使用本地 Ollama 模型
        if self._provider == "ollama" and self._ollama is not None:
            return self._generate_with_ollama(question, context)

        # 云端 API 需要 API key
        if not self._api_key:
            logger.error("No API key available for LLM generation")
            raise RuntimeError("LLM API key not configured. Please set DEEPSEEK_API_KEY, KIMI_API_KEY, or OPENAI_API_KEY")

        if not context:
            logger.warning("Empty context provided, returning fallback response")
            return "抱歉，没有找到与您问题相关的上下文信息，无法生成回答。"

        try:
            logger.info(f"Generating answer for question: {question[:50]}...")
            messages = self._build_messages(question, context)
            answer = self._call_openai_compatible_api(messages)
            logger.info(f"Successfully generated answer ({len(answer)} chars)")
            return answer

        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in generate: {e}")
            raise RuntimeError(f"Failed to generate answer: {e}")

    def _generate_with_ollama(self, question: str, context: List[Dict]) -> str:
        """
        使用本地 Ollama 模型生成回答

        Args:
            question: 用户问题
            context: 检索到的上下文

        Returns:
            生成的答案
        """
        if not context:
            logger.warning("Empty context provided, returning fallback response")
            return "抱歉，没有找到与您问题相关的上下文信息，无法生成回答。"

        try:
            logger.info(f"Generating answer with Ollama for question: {question[:50]}...")

            # 构建消息
            context_parts = []
            for i, ctx in enumerate(context, 1):
                text = ctx.get("text", "")
                source = ctx.get("source", "未知来源")
                context_parts.append(f"[{i}] 来源：{source}\n{text}")

            context_text = "\n\n".join(context_parts)

            # 构建消息列表
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"上下文信息：\n{context_text}\n\n问题：{question}\n\n请根据以上上下文回答："}
            ]

            answer = self._ollama.chat(
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )

            logger.info(f"Successfully generated answer with Ollama ({len(answer)} chars)")
            return answer

        except Exception as e:
            logger.error(f"Error in Ollama generation: {e}")
            raise RuntimeError(f"Failed to generate answer with Ollama: {e}")

    def generate_with_fallback(self, question: str, context: List[Dict]) -> str:
        """
        Generate answer with fallback to simpler response on error.

        Args:
            question: The user's question
            context: List of context dicts

        Returns:
            Generated answer or fallback message
        """
        try:
            return self.generate(question, context)
        except Exception as e:
            logger.warning(f"Generation failed, returning fallback: {e}")
            # Provide a graceful fallback with available context
            if context:
                sources = [ctx.get("source", "未知来源") for ctx in context[:3]]
                return f"抱歉，生成回答时遇到问题。请参考以下相关来源：\n" + "\n".join(f"- {s}" for s in sources)
            return "抱歉，暂时无法生成回答，请稍后重试。"
