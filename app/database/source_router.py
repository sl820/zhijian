"""
数据源路由：按 source 标识把请求路由到对应的 SQLite / 资源。

设计原则：
- 配置驱动：所有数据源在 SOURCES dict 里注册
- 路径可被环境变量覆盖（便于测试 / 部署）
- 单一文件、单例懒加载

Why：M5 数据接入。zhijian 系统从单一 in-memory KG 扩到多 SQLite 数据源。
How to apply：需要新数据源时，在 SOURCES 加一行 + 在 jiapu_query.py 同源写一份查询函数。
"""
import os
from pathlib import Path
from typing import Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_path(name: str, default: Path) -> Path:
    val = os.environ.get(name)
    return Path(val) if val else default


# ============================================================
# 数据源注册
# ============================================================
# 注：上图书目数据存放于 D:/上海图书馆开放数据/data/，独立于 zhijian 仓库

SOURCES: Dict[str, Dict] = {
    "jiapu": {
        # 上海图书馆 2016 年家谱元数据，2,029,035 persons
        "path": _env_path(
            "ZHIJIAN_SOURCE_JIAPU",
            Path("D:/上海图书馆开放数据/data/shlib_jiapu.db"),
        ),
        "label": "上海图书馆家谱元数据",
        "tables": {
            "persons": "persons",
            "relations": "person_relations",
            "works": "works",
            "places": "places",
            "titles": "titles",
        },
        "enabled": True,
    },
    "base": {
        # 基础知识库（CBDB / Wikidata 类），3.2 MB
        "path": _env_path(
            "ZHIJIAN_SOURCE_BASE",
            Path("D:/上海图书馆开放数据/data/shlib_base.db"),
        ),
        "label": "基础知识库",
        "tables": {},
        "enabled": False,  # TODO M5+
    },
    "dimingzhi": {
        # 2020 上海地名志
        "path": _env_path(
            "ZHIJIAN_SOURCE_DIMINGZHI",
            Path("D:/上海图书馆开放数据/data/shlib_didian2020.db"),
        ),
        "label": "2020 上海地名志",
        "tables": {},
        "enabled": False,
    },
    "gmwx": {
        # 革命文献
        "path": _env_path(
            "ZHIJIAN_SOURCE_GMWX",
            Path("D:/上海图书馆开放数据/data/shlib_gmwx.db"),
        ),
        "label": "革命文献",
        "tables": {},
        "enabled": False,
    },
    "wkl": {
        # 武康路
        "path": _env_path(
            "ZHIJIAN_SOURCE_WKL",
            Path("D:/上海图书馆开放数据/data/shlib_wkl.db"),
        ),
        "label": "武康路",
        "tables": {},
        "enabled": False,
    },
}


# ============================================================
# 公开 API
# ============================================================

def list_sources(enabled_only: bool = False) -> Dict[str, Dict]:
    """列出所有数据源（默认含未启用的）。"""
    if enabled_only:
        return {k: v for k, v in SOURCES.items() if v.get("enabled")}
    return dict(SOURCES)


def get_source(name: str) -> Optional[Dict]:
    """按名称取数据源配置。不存在返回 None。"""
    return SOURCES.get(name)


def get_source_path(name: str) -> Optional[Path]:
    src = get_source(name)
    return src["path"] if src else None


def is_enabled(name: str) -> bool:
    src = get_source(name)
    return bool(src and src.get("enabled"))


def assert_enabled(name: str) -> Dict:
    """断言数据源已启用且路径存在。返回配置。"""
    src = get_source(name)
    if not src:
        raise ValueError(f"未知数据源: {name}（已知: {list(SOURCES.keys())}）")
    if not src.get("enabled"):
        raise ValueError(f"数据源未启用: {name}")
    if not src["path"].exists():
        raise FileNotFoundError(f"数据源文件不存在: {src['path']}")
    return src
