"""
Pytest configuration for zhijian project.

Markers:
- @pytest.mark.slow: 跳过——会调用真实 LLM / 完整 pipeline（>10 秒）
- @pytest.mark.gpu: 跳过——需要 CUDA torch
- @pytest.mark.integration: 端到端测试，需要 uvicorn + Ollama + Chroma 运行中

默认 pytest 只跑快速单元测试。
跑全部（含 slow）：`pytest -m ""` 或 `pytest -m slow`
跑 slow+integration：`pytest -m "slow or integration"`
"""
import sys
from pathlib import Path

# 把项目根加入 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def pytest_configure(config):
    """注册自定义 marker"""
    config.addinivalue_line(
        "markers", "slow: 跑全量 pipeline / LLM extraction，可能 >10 秒"
    )
    config.addinivalue_line(
        "markers", "gpu: 需要 CUDA 加速"
    )
    config.addinivalue_line(
        "markers", "integration: 端到端测试，需 Ollama + Chroma 联机"
    )
