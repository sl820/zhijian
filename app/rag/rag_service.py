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
            chroma_client = ChromaVectorClient()
            self.retriever = Retriever(chroma_client)
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
        milvus_client = retriever.milvus_client

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
        milvus_client = retriever.milvus_client

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

        # Step 3: 生成答案
        generator = self._get_generator()
        answer = generator.generate(question, retrieved)

        result = {
            "answer": answer,
            "sources": [
                {
                    "text": r.get("text", ""),
                    "source": r.get("chapter_title", ""),
                    "score": r.get("distance", 0),
                }
                for r in retrieved
            ] if return_sources else []
        }

        return result

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
        milvus_client = retriever.milvus_client

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
