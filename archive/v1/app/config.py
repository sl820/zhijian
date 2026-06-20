"""
志鉴项目配置

从环境变量读取配置，所有项都有合理默认值。
改部署时只需设置环境变量，不需改代码。
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _env(name: str, default: str) -> str:
    val = os.environ.get(name)
    return val if val is not None and val != "" else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_path(name: str, default: Path) -> Path:
    return Path(_env(name, str(default)))


def _env_bool(name: str, default: bool) -> bool:
    val = _env(name, "true" if default else "false").lower()
    return val in ("1", "true", "yes", "on")


# ============================================================
# LLM (Ollama 本地部署)
# ============================================================
OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = _env("LLM_MODEL", "qwen2.5:3b")
LLM_TEMPERATURE = _env_float("LLM_TEMPERATURE", 0.3)
LLM_MAX_TOKENS = _env_int("LLM_MAX_TOKENS", 2048)
LLM_TIMEOUT = _env_int("LLM_TIMEOUT", 120)


# ============================================================
# Embedder
# ============================================================
EMBEDDING_MODEL = _env("EMBEDDING_MODEL", "BAAI/bge-base-chinese-v1.5")
EMBEDDING_DEVICE = _env("EMBEDDING_DEVICE", "cpu")
OLLAMA_EMBEDDING_MODEL = _env("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")


# ============================================================
# Vector store (ChromaDB)
# ============================================================
CHROMA_PERSIST_DIR = _env_path(
    "CHROMA_PERSIST_DIR", PROJECT_ROOT / "chroma_zhijian"
)
RAG_COLLECTION = _env("RAG_COLLECTION", "gazetteer_chunks")


# ============================================================
# KG (in-memory 持久化)
# ============================================================
KG_PERSIST_PATH = _env_path(
    "KG_PERSIST_PATH", PROJECT_ROOT / "data" / "processed" / "kg_state.json"
)


# ============================================================
# Data
# ============================================================
DEFAULT_CORPUS_DIR = PROJECT_ROOT / "data" / "raw" / "1998"
DEFAULT_CORPUS_FILE = DEFAULT_CORPUS_DIR / "第二十一编人物.txt"


# ============================================================
# Module toggles
# ============================================================
# OCR 默认关：保留代码但产品中禁用，未来如需扫描录入功能可通过
# ZHIJIAN_OCR_ENABLED=true 启用
OCR_ENABLED = _env_bool("ZHIJIAN_OCR_ENABLED", False)

# ============================================================
# 竞赛交付模式（DEMO_MODE）
# ============================================================
# 开启后：
#   1. 限制节点上限（默认 5000）防止 33k 节点卡死浏览器
#   2. 隐藏 OCR / 未完工模块入口
#   3. 启用裁剪 / LOD / dim 节流
#   4. 系统健康检查 FAIL 时进入 SAFE MODE（最小可演示）
# 设置：ZHIJIAN_DEMO_MODE=true
DEMO_MODE = _env_bool("ZHIJIAN_DEMO_MODE", False)
DEMO_NODE_LIMIT = _env_int("ZHIJIAN_DEMO_NODE_LIMIT", 5000)

# ============================================================
# R9 研究叙事模式（NARRATIVE_MODE）
# ============================================================
# 开启后 /narrative 路由展示 4-step 故事流：研究问题 / 数据基础 / 方法 / 核心发现
# 默认开（demo 阶段叙事模式是核心演示路径）
# 设置：ZHIJIAN_NARRATIVE_MODE=false 关闭
NARRATIVE_MODE = _env_bool("ZHIJIAN_NARRATIVE_MODE", True)


# ============================================================
# KG init: 朝代与年号词典
# ============================================================
DYNASTY_MARKERS = [
    "西汉", "东汉", "三国", "晋", "南北朝", "南朝", "北朝",
    "隋", "唐", "五代", "宋", "辽", "金", "元", "明", "清",
]
ERA_NAMES = {
    "天监", "永乐", "正统", "景泰", "成化", "弘治", "正德", "嘉靖",
    "隆庆", "万历", "泰昌", "天启", "崇祯", "康熙", "雍正", "乾隆",
    "嘉庆", "道光", "咸丰", "光绪", "宣统", "建元", "永元", "中元",
}
