#!/usr/bin/env python3
"""
Qwen2.5 + Ollama 本地部署脚本

此脚本帮助用户在 Windows 上快速部署阿里通义千问 Qwen2.5-3B 模型

使用方法:
    python scripts/setup_gemma_ollama.py

前置要求:
    1. 安装 Ollama: https://ollama.com/download
    2. 确保 Ollama 服务已启动: ollama serve
"""

import os
import sys
import subprocess
import urllib.request
import urllib.error
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "qwen2.5:3b"  # 阿里通义千问2.5，中文支持优秀


def check_ollama_installed():
    """检查 Ollama 是否已安装"""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info(f"Ollama 已安装: {result.stdout.strip()}")
            return True
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        logger.warning(f"Ollama 未安装或无法运行: {e}")
    return False


def check_ollama_service():
    """检查 Ollama 服务是否运行"""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/tags",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                logger.info("Ollama 服务正在运行")
                return True
    except Exception as e:
        logger.warning(f"Ollama 服务未运行: {e}")
    return False


def start_ollama_service():
    """尝试启动 Ollama 服务"""
    try:
        # 尝试启动 ollama serve
        logger.info("正在启动 Ollama 服务...")
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        # 等待服务启动
        import time
        for _ in range(10):
            time.sleep(2)
            if check_ollama_service():
                logger.info("Ollama 服务启动成功")
                return True
        logger.warning("Ollama 服务启动超时，请手动运行: ollama serve")
    except Exception as e:
        logger.warning(f"无法自动启动 Ollama 服务: {e}")
    return False


def check_model_downloaded():
    """检查 Gemma 模型是否已下载"""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if MODEL_NAME in result.stdout:
            logger.info(f"模型 {MODEL_NAME} 已下载")
            return True
        else:
            logger.info(f"模型 {MODEL_NAME} 未下载")
    except Exception as e:
        logger.warning(f"检查模型时出错: {e}")
    return False


def download_model():
    """下载 Gemma 模型"""
    try:
        logger.info(f"正在下载模型 {MODEL_NAME}，这可能需要几分钟...")
        logger.info("提示: 模型大小约 1.6GB")

        process = subprocess.Popen(
            ["ollama", "pull", MODEL_NAME],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        for line in process.stdout:
            line = line.strip()
            if line:
                logger.info(f"  {line}")

        process.wait()
        if process.returncode == 0:
            logger.info(f"模型 {MODEL_NAME} (阿里通义千问) 下载完成!")
            return True
        else:
            logger.error(f"模型下载失败，返回码: {process.returncode}")
    except Exception as e:
        logger.error(f"下载模型时出错: {e}")
    return False


def test_model():
    """测试模型是否正常工作"""
    try:
        logger.info("测试模型推理...")
        result = subprocess.run(
            ["ollama", "run", MODEL_NAME, "Hello, how are you?"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            logger.info("模型测试成功!")
            logger.info(f"模型输出: {result.stdout[:200]}...")
            return True
        else:
            logger.warning(f"模型测试返回: {result.stderr[:200] if result.stderr else result.stdout[:200]}")
    except subprocess.TimeoutExpired:
        logger.warning("模型测试超时")
    except Exception as e:
        logger.warning(f"测试模型时出错: {e}")
    return False


def main():
    logger.info("=" * 60)
    logger.info("阿里通义千问 Qwen2.5-3B + Ollama 本地部署脚本")
    logger.info("=" * 60)

    # Step 1: 检查 Ollama 是否安装
    if not check_ollama_installed():
        logger.error("请先安装 Ollama:")
        logger.error("  1. 访问 https://ollama.com/download")
        logger.error("  2. 下载并安装 Windows 版本")
        logger.error("  3. 重新运行此脚本")
        sys.exit(1)

    # Step 2: 检查/启动 Ollama 服务
    if not check_ollama_service():
        logger.info("尝试启动 Ollama 服务...")
        if not start_ollama_service():
            logger.error("无法启动 Ollama 服务，请手动运行: ollama serve")
            sys.exit(1)

    # Step 3: 检查/下载模型
    if not check_model_downloaded():
        if not download_model():
            logger.error("无法下载模型")
            sys.exit(1)

    # Step 4: 测试模型
    if not test_model():
        logger.warning("模型测试未完全通过，但可能仍在下载中")

    logger.info("=" * 60)
    logger.info("部署完成!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("下一步:")
    logger.info("  1. 启动志鉴后端: cd zhijian && python -m uvicorn app.main:app --reload")
    logger.info("  2. 测试 RAG 问答: curl -X POST http://localhost:8000/api/v1/rag/ask -d '{\"question\": \"固安县在哪个省份？\"}'")
    logger.info("")
    logger.info("如需停止 Ollama 服务: ollama stop")


if __name__ == "__main__":
    main()
