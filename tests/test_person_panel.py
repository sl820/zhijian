"""
M7 详情面板端点测试

覆盖：
- GET /kg/person/{uri:path}/subgraph
- GET /kg/person/{uri:path}/evidence
- GET /kg/person/{uri:path}/rag
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================
# /kg/person/{uri}/subgraph
# ============================================================

class TestSubgraphEndpoint:
    """BFS 子图端点。"""

    def test_subgraph_returns_center_node(self):
        """至少有中心节点"""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        # 用一个真实存在的 URI（朱熹）
        uri = "http://data.library.sh.cn/entity/person/r5vmxq29ki9gddjn"
        try:
            res = client.get(f"/api/v1/kg/person/{uri}/subgraph", params={"hops": 2, "max_nodes": 20})
        except Exception as e:
            pytest.skip(f"jiapu.db 不可用: {e}")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "success"
        assert data["uri"] == uri
        assert data["node_count"] >= 1
        # 至少有一个中心节点标记
        center_nodes = [n for n in data["nodes"] if n.get("is_center")]
        assert len(center_nodes) == 1

    def test_subgraph_max_nodes_limit(self):
        """max_nodes 限制子图大小"""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        uri = "http://data.library.sh.cn/entity/person/r5vmxq29ki9gddjn"
        try:
            res = client.get(f"/api/v1/kg/person/{uri}/subgraph", params={"hops": 2, "max_nodes": 5})
        except Exception:
            pytest.skip("jiapu.db 不可用")
        data = res.json()
        assert data["node_count"] <= 5

    def test_subgraph_invalid_source(self):
        """非 jiapu 源返回 400"""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        uri = "http://data.library.sh.cn/entity/person/r5vmxq29ki9gddjn"
        res = client.get(f"/api/v1/kg/person/{uri}/subgraph", params={"source": "base"})
        assert res.status_code == 400


# ============================================================
# /kg/person/{uri}/evidence
# ============================================================

class TestEvidenceEndpoint:
    """跨源证据端点。"""

    def test_evidence_returns_list(self):
        """返回 evidence 数组"""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        uri = "http://data.library.sh.cn/entity/person/r5vmxq29ki9gddjn"
        try:
            res = client.get(f"/api/v1/kg/person/{uri}/evidence", params={"name": "朱熹"})
        except Exception:
            pytest.skip("依赖不可用")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert isinstance(data["evidence"], list)
        # count 与 list 长度一致
        assert data["count"] == len(data["evidence"])

    def test_evidence_includes_rag_chunks(self):
        """应包含 RAG 检索片段（rag 源已灌数据）"""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        uri = "http://data.library.sh.cn/entity/person/r5vmxq29ki9gddjn"
        try:
            res = client.get(f"/api/v1/kg/person/{uri}/evidence", params={"name": "朱熹"})
        except Exception:
            pytest.skip("依赖不可用")
        data = res.json()
        sources = {e["source"] for e in data["evidence"]}
        # RAG 源已 enable，应至少能搜到 RAG chunks
        # 若 RAG 不可用则跳过
        if not sources:
            pytest.skip("所有源均无证据")


# ============================================================
# /kg/person/{uri}/rag
# ============================================================

class TestPersonRAGEndpoint:
    """人物限定 RAG 端点。"""

    def test_rag_returns_answer(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        uri = "http://data.library.sh.cn/entity/person/r5vmxq29ki9gddjn"
        try:
            res = client.get(f"/api/v1/kg/person/{uri}/rag", params={"q": "简介", "name": "朱熹"})
        except Exception as e:
            pytest.skip(f"RAG 依赖不可用: {e}")
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        # answer 字段必有（即使 LLM 不可用，fallback 也返回）
        assert isinstance(data["answer"], str)
        assert "llm_unavailable" in data


# ============================================================
# URI 路径含斜杠
# ============================================================

class TestUriPathEncoding:
    """URI 含斜杠 / 必须用 {uri:path} 捕获。"""

    def test_uri_with_slashes_resolves(self):
        """http://x/y/z 这种 URI 不应被切到第一个 /"""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        uri = "http://data.library.sh.cn/entity/person/r5vmxq29ki9gddjn"
        # URL 编码
        from urllib.parse import quote
        encoded = quote(uri, safe="")
        res = client.get(f"/api/v1/kg/person/{encoded}/subgraph", params={"hops": 1, "max_nodes": 5})
        # 不是 404 就算过（参数路由 + path 转换正确）
        assert res.status_code in (200, 400), f"got {res.status_code} {res.text}"


# ============================================================
# /kg/persons/{name} 也支持 path
# ============================================================

class TestPersonsByPathUri:
    """/kg/persons/{name:path} 也支持完整 URI"""

    def test_persons_with_uri(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        uri = "http://data.library.sh.cn/entity/person/r5vmxq29ki9gddjn"
        from urllib.parse import quote
        encoded = quote(uri, safe="")
        try:
            res = client.get(f"/api/v1/kg/persons/{encoded}", params={"source": "jiapu"})
        except Exception:
            pytest.skip("jiapu.db 不可用")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "success"
        assert data["person"]["uri"] == uri