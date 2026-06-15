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
