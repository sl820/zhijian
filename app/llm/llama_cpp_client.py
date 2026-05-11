"""
LlamaCPP 本地模型客户端

支持 llama.cpp 推理的 GGUF 格式模型
用于志鉴系统的本地 LLM 推理（替代云端 API）
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Lazy-initialized global instance
_llm_instance: Optional["LlamaCPPClient"] = None

# Default configuration
DEFAULT_CONFIG = {
    "model_path": None,  # 设置为 zhijian/models/gemma4-2b-it-q4_k_m.gguf
    "model_name": "gemma:2b",
    "n_ctx": 8192,  # 上下文长度
    "n_gpu_layers": 99,  # 全部GPU加速
    "temperature": 0.3,
    "max_tokens": 2048,
    "verbose": False,
}


class LlamaCPPClient:
    """
    LlamaCPP 本地模型推理客户端

    使用 llama-cpp-python 调用本地 GGUF 模型
    支持 Gemma4-2B 等开源模型
    """

    def __init__(self, config: Optional[Dict] = None):
        from llama_cpp import Llama

        self.config = {**DEFAULT_CONFIG, **(config or {})}

        model_path = self.config.get("model_path")
        if not model_path:
            # 查找默认模型路径
            default_path = Path(__file__).parent.parent.parent / "models" / "gemma4-2b-it-q4_k_m.gguf"
            if default_path.exists():
                model_path = str(default_path)

        if not model_path or not os.path.exists(model_path):
            raise FileNotFoundError(
                f"模型文件未找到: {model_path}\n"
                f"请下载 Gemma4-2B GGUF 模型到 zhijian/models/ 目录\n"
                f"下载地址: https://huggingface.co/lm-community/Gemma4-2B-IT-GGUF"
            )

        logger.info(f"正在加载 LlamaCPP 模型: {model_path}")

        self._llm = Llama(
            model_path=model_path,
            n_ctx=self.config.get("n_ctx", 8192),
            n_gpu_layers=self.config.get("n_gpu_layers", 99),
            verbose=self.config.get("verbose", False),
        )
        self._n_ctx = self.config.get("n_ctx", 8192)
        self._temperature = float(self.config.get("temperature", 0.3))
        self._max_tokens = int(self.config.get("max_tokens", 2048))

        logger.info("LlamaCPP 模型加载完成")

    def generate(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """
        生成回答（单轮）

        Args:
            prompt: 用户输入
            system: 系统提示（可选）
            **kwargs: temperature, max_tokens 等参数

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

        # 调用模型
        output = self._llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return output["choices"][0]["message"]["content"]

    def chat(self, messages: List[Dict], **kwargs) -> str:
        """
        对话模式（多轮）

        Args:
            messages: 消息列表，每条包含 role 和 content
            **kwargs: temperature, max_tokens 等参数

        Returns:
            生成的文本
        """
        temperature = kwargs.get("temperature", self._temperature)
        max_tokens = kwargs.get("max_tokens", self._max_tokens)

        output = self._llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return output["choices"][0]["message"]["content"]


def get_llm(config: Optional[Dict] = None) -> LlamaCPPClient:
    """
    获取或创建全局 LLM 实例（单例模式）

    Args:
        config: 可选的配置字典

    Returns:
        LlamaCPPClient 实例
    """
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LlamaCPPClient(config)
    return _llm_instance


def reset_llm():
    """重置 LLM 实例（用于测试或配置更改）"""
    global _llm_instance
    _llm_instance = None
    logger.info("LLM 实例已重置")
