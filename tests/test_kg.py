"""
知识图谱 (KG) 端到端测试

特点：
- in-memory 实现，零外部依赖
- /kg/init 跑全量 pipeline → 标记为 slow（默认跳过）
- 默认 pytest 只跑快测试

跑全部：`pytest -m "" tests/test_kg.py`
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ============================================================
# 状态 + Schema（快）
# ============================================================

def test_kg_status_has_in_memory_mode(client):
    r = client.get("/api/v1/kg/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["mode"] == "in_memory"
    assert "person_count" in body
    assert "relation_count" in body
    assert isinstance(body["person_count"], int)
    assert isinstance(body["relation_count"], int)


def test_list_persons_works_with_existing_state(client):
    """读已持久化的 KG（如果 kg_state.json 存在）"""
    r = client.get("/api/v1/kg/persons", params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "persons" in body
    assert "count" in body
    # 如果已有数据，count > 0；否则 0 也 OK
    assert body["count"] >= 0


def test_graph_returns_echarts_shape(client):
    """graph 端点必须返回 ECharts 兼容的 {nodes, links} 结构"""
    r = client.get("/api/v1/kg/graph", params={"limit": 50})
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body
    assert "links" in body
    assert "total_persons" in body
    assert "total_links" in body

    for node in body["nodes"]:
        assert "id" in node
        assert "name" in node

    for link in body["links"]:
        assert "source" in link
        assert "target" in link
        assert "name" in link or "relation" in link


# ============================================================
# 初始化流程（@pytest.mark.slow：跑 pipeline + LLM 抽取）
# ============================================================

@pytest.mark.slow
@pytest.mark.integration
def test_init_from_default_corpus_extracts_persons(client):
    """
    用默认语料初始化 KG（clear=true 确保从空开始），应能抽到人。
    需要 data/raw/1998/第二十一编人物.txt 存在。
    """
    default_corpus = project_root / "data" / "raw" / "1998" / "第二十一编人物.txt"
    if not default_corpus.exists():
        pytest.skip(f"默认语料不存在: {default_corpus}")

    r = client.post(
        "/api/v1/kg/init",
        params={"clear": "true", "background": "false"},
        timeout=300,
    )
    assert r.status_code == 200
    body = r.json()
    assert "persons_stored" in body
    assert "total_persons" in body
    assert body["total_persons"] >= 1, "应至少抽到 1 个人物"


@pytest.mark.slow
def test_get_specific_person_after_init(client):
    """初始化后取具体人物，验证有 relations 字段"""
    persons = client.get("/api/v1/kg/persons", params={"limit": 5}).json()
    if persons["count"] == 0:
        pytest.skip("KG 暂无人物，跳过详情测试")
    name = persons["persons"][0]["name"]

    r = client.get(f"/api/v1/kg/persons/{name}")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == name
    assert "relations" in body
    assert "related_persons" in body


# ============================================================
# OCR 联动预览（不依赖真实 LLM，但走 KGPipeline）
# ============================================================

def test_extract_entities_returns_shape(client):
    """OCR 联动：传入一段短文本，验证响应含 entities + relations 字段"""
    import urllib.request, urllib.error
    # ollama 未运行时 KGPipeline 仍能用规则抽取；这里只测响应结构
    payload = {
        "text": "康熙年间，苏轼任杭州通判，与王安石同朝。苏轼字子瞻，眉山人。",
        "title": "测试文本",
        "source": "unit_test",
    }
    r = client.post("/api/v1/kg/entity/extract", json=payload, timeout=60)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert "entities" in body
    assert "relations" in body
    assert "stats" in body
    # 即使 LLM 不可用也应返回结构（可能是空列表），不能 500
    assert isinstance(body["entities"], list)
    assert isinstance(body["relations"], list)


def test_extract_entities_empty_text_returns_shape(client):
    r = client.post(
        "/api/v1/kg/entity/extract",
        json={"text": "", "title": "空", "source": "unit_test"},
        timeout=60,
    )
    # Pydantic min_length 校验可能 422，或业务层正常返回空 list
    assert r.status_code in (200, 422)

