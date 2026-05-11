"""
Ollama 本地模型客户端

通过 REST API 调用本地 Ollama 服务
支持 Gemma4, Llama 等开源模型
"""

import logging
import json
import urllib.request
import urllib.error
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Lazy-initialized global instance
_llm_instance: Optional["OllamaClient"] = None

# Default configuration
DEFAULT_CONFIG = {
    "base_url": "http://localhost:11434",
    "model": "qwen2.5:3b",  # 阿里通义千问，中文支持优秀
    "temperature": 0.3,
    "max_tokens": 2048,
    "timeout": 120,
}


class OllamaClient:
    """
    Ollama 本地模型推理客户端

    通过 REST API 调用本地 Ollama 服务
    支持多轮对话和单轮生成
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}

        self._base_url = self.config.get("base_url", "http://localhost:11434")
        self._model = self.config.get("model") or DEFAULT_CONFIG.get("model", "qwen2.5:3b")
        self._temperature = float(self.config.get("temperature", 0.3))
        self._max_tokens = int(self.config.get("max_tokens", 2048))
        self._timeout = int(self.config.get("timeout", 120))

        # 验证服务可用性
        if not self._check_connection():
            raise ConnectionError(
                f"Ollama 服务未运行或无法连接: {self._base_url}\n"
                f"请先安装并启动 Ollama: https://ollama.com/download\n"
                f"启动命令: ollama serve"
            )

        logger.info(f"OllamaClient 初始化完成: model={self._model}, url={self._base_url}")

    def _check_connection(self) -> bool:
        """检查 Ollama 服务是否可用"""
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except Exception:
            return False

    def _post(self, endpoint: str, payload: dict) -> dict:
        """发送 POST 请求到 Ollama API"""
        url = f"{self._base_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
        }

        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            logger.error(f"Ollama API HTTP error {e.code}: {error_body}")
            raise RuntimeError(f"Ollama API error: HTTP {e.code} - {error_body}")
        except urllib.error.URLError as e:
            logger.error(f"Ollama connection error: {e.reason}")
            raise RuntimeError(f"Ollama 连接失败: {e.reason}")
        except Exception as e:
            logger.error(f"Ollama unexpected error: {e}")
            raise RuntimeError(f"Ollama 错误: {e}")

    def generate(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """
        单轮生成

        Args:
            prompt: 用户输入
            system: 系统提示（可选）
            **kwargs: temperature, max_tokens 等参数覆盖

        Returns:
            生成的文本
        """
        temperature = kwargs.get("temperature", self._temperature)
        max_tokens = kwargs.get("max_tokens", self._max_tokens)

        # 构建消息
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        result = self._post("/api/chat", payload)
        return result["message"]["content"]

    def chat(self, messages: List[Dict], **kwargs) -> str:
        """
        多轮对话

        Args:
            messages: 消息列表，每条包含 role 和 content
            **kwargs: temperature, max_tokens 等参数

        Returns:
            生成的文本
        """
        temperature = kwargs.get("temperature", self._temperature)
        max_tokens = kwargs.get("max_tokens", self._max_tokens)

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        result = self._post("/api/chat", payload)
        return result["message"]["content"]


def get_llm(config: Optional[Dict] = None) -> OllamaClient:
    """
    获取或创建全局 LLM 实例（单例模式）

    Args:
        config: 可选的配置字典

    Returns:
        OllamaClient 实例
    """
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = OllamaClient(config)
    return _llm_instance


def reset_llm():
    """重置 LLM 实例（用于测试或配置更改）"""
    global _llm_instance
    _llm_instance = None
    logger.info("LLM 实例已重置")
