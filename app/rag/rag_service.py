"""
RAG问答服务 - 检索增强生成整合模块

整合检索器(Retriever)、嵌入器(Embedder)、生成器(Generator)
实现古籍知识库的智能问答功能
"""

import logging
from typing import List, Dict, Optional

from .chunker import TextChunker
from .embedder import Embedder
from .retriever import Retriever
from .generator import Generator

logger = logging.getLogger(__name__)


class RAGService:
    """
    RAG问答服务

    整合检索和生成流程：
    1. 将古籍文档分块(Chunker)
    2. 向量化存入Milvus(Embedder + Retriever)
    3. 检索相关片段(Retriever)
    4. 生成答案(Generator)
    """

    def __init__(self, config: dict = None):
        self.config = config or {}

        # 初始化各组件（延迟加载）
        self.chunker = TextChunker()
        self.embedder = None  # 延迟加载
        self.retriever = None  # 延迟加载
        self.generator = None  # 延迟加载

        # 配置参数
        self.collection_name = self.config.get("collection_name", "gazetteer_chunks")
        self.embedding_dim = self.config.get("embedding_dim", 768)
        self.default_top_k = self.config.get("default_top_k", 5)

        logger.info("RAGService初始化完成")

    def _get_embedder(self) -> Embedder:
        """延迟加载嵌入器"""
        if self.embedder is None:
            logger.info("正在加载嵌入模型...")
            self.embedder = Embedder()
            self.embedder.load_model()
        return self.embedder

    def _get_retriever(self) -> Retriever:
        """延迟加载检索器"""
        if self.retriever is None:
            logger.info("正在初始化检索器...")
            from app.database.chroma_client import ChromaVectorClient
            from .. import config as app_config
            vector_client = ChromaVectorClient(persist_directory=str(app_config.CHROMA_PERSIST_DIR))
            self.retriever = Retriever(vector_client=vector_client)
        return self.retriever

    def _get_generator(self) -> Generator:
        """延迟加载生成器"""
        if self.generator is None:
            logger.info("正在初始化生成器...")
            llm_config = self.config.get("llm_config", {})
            # 默认使用本地 ollama，如果未指定 provider
            if not llm_config.get("provider"):
                llm_config["provider"] = "ollama"
                logger.info("使用本地 Ollama Qwen2.5-3B 模型（默认）")
            self.generator = Generator(llm_config)
        return self.generator

    def ingest_document(self, text: str, title: str = "未知文档",
                        chapter_title: str = None,
                        metadata: dict = None) -> Dict:
        """
        摄入单个文档到向量数据库

        Args:
            text: 文档文本
            title: 文档标题
            chapter_title: 章节标题（可选）
            metadata: 额外元数据

        Returns:
            摄入结果统计
        """
        logger.info(f"开始摄入文档: {title}")

        # Step 1: 文本分块
        if chapter_title:
            chunks = self.chunker.chunk(text, chapter_title=chapter_title)
        else:
            chunks = self.chunker.chunk(text)

        logger.info(f"文档分块完成: 共 {len(chunks)} 个块")

        # Step 2: 向量化
        embedder = self._get_embedder()
        retriever = self._get_retriever()
        chunk_texts = [c["text"] for c in chunks]

        logger.info("开始计算嵌入向量...")
        vectors = embedder.encode(chunk_texts)

        # Step 3: 构建BM25索引
        retriever.index_collection_for_bm25(
            collection=self.collection_name,
            texts=chunk_texts,
            metadata=[{
                "title": title,
                "chapter_title": c.get("chapter_title", ""),
                "chunk_index": c.get("chunk_index", 0),
                **(metadata or {})
            } for c in chunks]
        )

        # Step 4: 存入Milvus
        milvus_client = retriever.vector_client

        # 创建或使用已有collection
        if not milvus_client.has_collection(self.collection_name):
            milvus_client.create_collection(
                self.collection_name,
                dimension=self.embedding_dim
            )

        milvus_client.insert_vectors(
            collection_name=self.collection_name,
            vectors=vectors,
            texts=chunk_texts,
            metadata=[{
                "title": title,
                "chapter_title": c.get("chapter_title", ""),
                "chunk_index": c.get("chunk_index", 0),
                **(c.get("metadata", {}))
            } for c in chunks]
        )

        logger.info(f"文档摄入完成: {title}, {len(chunks)} 个块")

        return {
            "title": title,
            "chunk_count": len(chunks),
            "status": "success"
        }

    def ingest_documents(self, documents: List[Dict]) -> List[Dict]:
        """
        批量摄入多个文档

        Args:
            documents: 文档列表，每项包含 text, title, metadata

        Returns:
            每篇文档的摄入结果
        """
        if not documents:
            return []

        # Step 1: Chunk all documents
        all_chunks = []
        chunk_results = []  # (doc_idx, chunk_idx, chunk, doc_title, metadata)
        for doc_idx, doc in enumerate(documents):
            title = doc.get("title", "未知文档")
            try:
                chunks = self.chunker.chunk(doc["text"])
            except Exception as e:
                logger.warning(f"分块失败 {title}: {e}")
                chunks = []
            for chunk_idx, c in enumerate(chunks):
                all_chunks.append(c["text"])
                chunk_results.append((doc_idx, chunk_idx, c, title, doc.get("metadata")))
            logger.info(f"文档分块完成: {title}, 共 {len(chunks)} 个块")

        if not all_chunks:
            return [{
                "title": doc.get("title", "未知文档"),
                "status": "failed",
                "error": "No chunks created"
            } for doc in documents]

        # Step 2: Batch encode all chunks together (ensures consistent TF-IDF dimensions)
        embedder = self._get_embedder()
        logger.info(f"开始批量计算嵌入向量: {len(all_chunks)} 个块...")
        all_vectors = embedder.encode(all_chunks)

        # Step 3: Prepare metadata and insert
        retriever = self._get_retriever()
        milvus_client = retriever.vector_client

        # Create collection if needed
        if not milvus_client.has_collection(self.collection_name):
            dim = len(all_vectors[0]) if all_vectors else self.embedding_dim
            milvus_client.create_collection(self.collection_name, dimension=dim)

        # Prepare per-chunk metadata
        chunk_metas = []
        for doc_idx, chunk_idx, c, doc_title, metadata in chunk_results:
            chunk_metas.append({
                "title": doc_title,
                "chapter_title": c.get("chapter_title", ""),
                "chunk_index": chunk_idx,
                "doc_chunk_index": c.get("chunk_index", 0),
                "text": c["text"][:200],  # Store first 200 chars as text field
                **(metadata or {})
            })

        milvus_client.insert_vectors(
            collection_name=self.collection_name,
            vectors=all_vectors,
            texts=[c["text"] for _, _, c, _, _ in chunk_results],
            metadata=chunk_metas
        )
        logger.info(f"批量摄入完成: {len(all_chunks)} 个块")

        # Step 4: Build BM25 index
        retriever.index_collection_for_bm25(
            collection=self.collection_name,
            texts=all_chunks,
            metadata=chunk_metas
        )

        # Step 5: Return per-document results
        results = []
        doc_chunk_counts = {}
        for doc_idx, _, _, title, _ in chunk_results:
            doc_chunk_counts[doc_idx] = doc_chunk_counts.get(doc_idx, 0) + 1

        for doc_idx, doc in enumerate(documents):
            results.append({
                "title": doc.get("title", "未知文档"),
                "chunk_count": doc_chunk_counts.get(doc_idx, 0),
                "status": "success"
            })

        return results

    def ask(self, question: str, top_k: int = None,
            collection: str = None,
            return_sources: bool = True) -> Dict:
        """
        问答查询

        Args:
            question: 用户问题
            top_k: 检索的Top-K结果数
            collection: 使用的collection名称
            return_sources: 是否返回来源片段

        Returns:
            {
                "answer": "生成的答案",
                "sources": [...]  # 检索到的片段
            }
        """
        top_k = top_k or self.default_top_k
        collection = collection or self.collection_name

        logger.info(f"处理问答: {question[:50]}...")

        # Step 1: 向量化问题
        embedder = self._get_embedder()
        query_vector = embedder.encode_query(question)

        # Step 2: 检索相关片段
        retriever = self._get_retriever()
        retrieved = retriever.retrieve(
            query=question,
            query_vector=query_vector,
            top_k=top_k,
            collection=collection
        )

        logger.info(f"检索到 {len(retrieved)} 个相关片段")

        # Step 3: 生成答案（带离线降级，M9）
        generator = self._get_generator()
        llm_unavailable = False
        try:
            # 预检测：Ollama 不可用直接走 fallback（避免每次失败重试 ~30s）
            gen = self.generator
            if gen is not None and hasattr(gen, "_ollama") and gen._ollama is not None:
                if not gen._ollama.is_available():
                    llm_unavailable = True
                    logger.warning("Ollama 不可用，直接走 fallback 模板")
                    answer = gen.generate_with_fallback(question, retrieved)
                else:
                    answer = gen.generate(question, retrieved)
            else:
                answer = gen.generate(question, retrieved)
        except Exception as e:
            logger.error(f"LLM 生成失败: {e}")
            llm_unavailable = True
            answer = gen.generate_with_fallback(question, retrieved) if gen else "LLM 暂不可用"

        result = {
            "answer": answer,
            "sources": [
                {
                    "text": r.get("text", ""),
                    "source": r.get("chapter_title", ""),
                    "score": r.get("distance", 0),
                }
                for r in retrieved
            ] if return_sources else [],
            "llm_unavailable": llm_unavailable,
        }

        return result

    def ask_by_source(self, question: str, source: str,
                      top_k: int = None) -> Dict:
        """按数据源查询（M8）。

        Args:
            question: 用户问题
            source: 数据源名（"jiapu" / "memory" / "all"）
                - "all" 或 None：跨所有 collection 检索
                - 其它：仅在 `zhijian_{source}` collection 检索
            top_k: Top-K 结果数

        Returns:
            ask() 的返回结构
        """
        retriever = self._get_retriever()
        vector_client = retriever.vector_client

        # 列出可用 collection
        all_collections = [
            name for name in ["zhijian_jiapu", "zhijian_memory", "zhijian_base",
                             "zhijian_gufang", "zhijian_dimingzhi", "zhijian_gmwx",
                             "zhijian_wkl", self.collection_name]
            if vector_client.has_collection(name)
        ]

        if not all_collections:
            logger.warning("没有任何 collection，返回空结果")

        # 选定 collection
        if not source or source == "all":
            collections = all_collections
        else:
            target = f"zhijian_{source}"
            if target in all_collections:
                collections = [target]
            else:
                logger.warning(f"源 {source} 无 collection，返回空结果")
                collections = []

        # 跨 collection 检索：合并 top_k 结果
        embedder = self._get_embedder()
        query_vector = embedder.encode_query(question)
        merged = []
        per_coll = max(1, (top_k or self.default_top_k) // max(len(collections), 1) + 1)

        for coll in collections:
            try:
                retrieved = retriever.retrieve(
                    query=question,
                    query_vector=query_vector,
                    top_k=per_coll,
                    collection=coll,
                )
                for r in retrieved:
                    r["_collection"] = coll
                merged.extend(retrieved)
            except Exception as e:
                logger.error(f"检索 {coll} 失败: {e}")

        # 按距离排序取 top_k
        merged.sort(key=lambda r: r.get("distance", 999))
        top_k_final = top_k or self.default_top_k
        top_results = merged[:top_k_final]

        # 生成答案（带离线降级）
        generator = self._get_generator()
        llm_unavailable = False
        try:
            gen = self.generator
            if gen is not None and hasattr(gen, "_ollama") and gen._ollama is not None:
                if not gen._ollama.is_available():
                    llm_unavailable = True
                    logger.warning("Ollama 不可用，走 fallback 模板")
                    answer = gen.generate_with_fallback(question, top_results)
                else:
                    answer = gen.generate(question, top_results)
            else:
                answer = gen.generate(question, top_results)
        except Exception as e:
            logger.error(f"LLM 生成失败: {e}")
            llm_unavailable = True
            answer = gen.generate_with_fallback(question, top_results) if gen else f"[LLM 暂不可用] 检索到 {len(top_results)} 条相关片段"

        return {
            "answer": answer,
            "sources": [
                {
                    "text": r.get("text", ""),
                    "source": r.get("chapter_title", ""),
                    "collection": r.get("_collection", ""),
                    "score": r.get("distance", 0),
                }
                for r in top_results
            ],
            "queried_collections": collections,
            "llm_unavailable": llm_unavailable,
        }

    def list_collections(self) -> List[Dict]:
        """列出所有 zhijian_* collections + chunk 数。"""
        retriever = self._get_retriever()
        vector_client = retriever.vector_client
        results = []
        for name in ["zhijian_jiapu", "zhijian_memory", "zhijian_base",
                    "zhijian_gufang", "zhijian_dimingzhi", "zhijian_gmwx",
                    "zhijian_wkl", self.collection_name]:
            if vector_client.has_collection(name):
                try:
                    col = vector_client.get_collection(name)
                    results.append({"name": name, "count": col.count()})
                except Exception:
                    results.append({"name": name, "count": "unknown"})
        return results

    def create_collection(self, collection_name: str = None,
                          drop_existing: bool = False) -> str:
        """
        创建向量collection

        Args:
            collection_name: collection名称
            drop_existing: 是否删除已存在的collection

        Returns:
            collection名称
        """
        name = collection_name or self.collection_name
        retriever = self._get_retriever()
        milvus_client = retriever.vector_client

        if drop_existing and milvus_client.has_collection(name):
            milvus_client.drop_collection(name)
            logger.info(f"已删除已存在的collection: {name}")

        if not milvus_client.has_collection(name):
            # Use embedder's actual dimension (important for TF-IDF fallback)
            embedder = self._get_embedder()
            dim = embedder.embedding_dim
            milvus_client.create_collection(name, dimension=dim)
            logger.info(f"创建collection: {name}, dimension={dim}")

        return name


# 全局单例
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """获取RAG服务单例"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
