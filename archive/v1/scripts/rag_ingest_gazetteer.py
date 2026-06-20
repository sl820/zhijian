"""
RAG 知识库灌入脚本 - 将固安县志数据灌入向量数据库

用法:
    python scripts/rag_ingest_gazetteer.py [--data-dir DATA_DIR] [--collection NAME] [--rebuild]
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# 跳过的文件（无意义内容）
SKIP_FILES = {"图片.txt", "封面.txt", "目录 (2).txt"}


def load_text_files(data_dir: Path) -> list:
    """加载所有文本文件"""
    texts = []
    for txt_file in sorted(data_dir.glob("*.txt")):
        if txt_file.name in SKIP_FILES:
            continue
        try:
            with open(txt_file, encoding="utf-8") as f:
                content = f.read().strip()
            if len(content) < 50:  # 跳过太短的内容
                logger.warning(f"跳过太短的文件: {txt_file.name} ({len(content)} chars)")
                continue
            texts.append({
                "title": txt_file.name.replace(".txt", ""),
                "content": content,
                "path": str(txt_file)
            })
            logger.info(f"加载: {txt_file.name} ({len(content)} chars)")
        except Exception as e:
            logger.error(f"加载失败 {txt_file.name}: {e}")
    return texts


def ingest_gazetteer(
    data_dir: str = None,
    collection_name: str = "gazetteer_chunks",
    rebuild: bool = False,
    device: str = None
):
    """
    将固安县志数据灌入 RAG 知识库

    Args:
        data_dir: 数据目录路径
        collection_name: ChromaDB collection 名称
        rebuild: 是否重建 collection
        device: embedder 设备 (cuda/cpu)
    """
    if data_dir is None:
        data_dir = project_root / "data" / "raw" / "1998"
    else:
        data_dir = Path(data_dir)

    logger.info(f"开始灌入数据: {data_dir}")
    logger.info(f"Collection: {collection_name}, Rebuild: {rebuild}")

    # Step 1: 加载文本
    texts = load_text_files(data_dir)
    if not texts:
        logger.error("没有找到文本文件")
        return

    total_chars = sum(len(t["content"]) for t in texts)
    logger.info(f"共加载 {len(texts)} 个文本文件, {total_chars} 字符")

    # Step 2: 初始化 RAG 组件
    from app.rag.chunker import TextChunker
    from app.rag.embedder import Embedder
    from app.database.chroma_client import ChromaVectorClient

    chunker = TextChunker(max_tokens=400, overlap_tokens=50)
    embedder = Embedder(device=device)
    embedder.load_model()
    chroma_client = ChromaVectorClient(persist_directory="./chroma_zhijian")

    # Step 3: 重建或创建 collection
    if rebuild:
        if chroma_client.has_collection(collection_name):
            chroma_client.drop_collection(collection_name)
            logger.info(f"已删除旧 collection: {collection_name}")
        chroma_client.create_collection(collection_name, dimension=embedder.embedding_dim)
        logger.info(f"创建新 collection: {collection_name}")
    elif not chroma_client.has_collection(collection_name):
        chroma_client.create_collection(collection_name, dimension=embedder.embedding_dim)
        logger.info(f"创建 collection: {collection_name}")

    # Step 4: 分块并灌入
    all_chunks = []
    all_metadatas = []

    for doc in texts:
        title = doc["title"]
        content = doc["content"]

        # 使用 max_tokens 策略分块
        chunks = chunker.chunk(content, strategy="by_max_tokens", chapter_title=title)
        logger.info(f"  {title}: {len(chunks)} chunks")

        for chunk in chunks:
            all_chunks.append(chunk["text"])
            all_metadatas.append({
                "title": title,
                "chapter_title": chunk.get("chapter_title", title),
                "chunk_index": chunk.get("chunk_index", 0),
                "source": doc["path"]
            })

    logger.info(f"共 {len(all_chunks)} 个 chunks，开始向量化...")

    # 批量向量化
    batch_size = 32
    all_vectors = []
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        vectors = embedder.encode(batch)
        all_vectors.extend(vectors)
        logger.info(f"  向量化进度: {min(i + batch_size, len(all_chunks))}/{len(all_chunks)}")

    logger.info("开始存入 ChromaDB...")

    # 存入 ChromaDB（分批）
    insert_batch = 500
    for i in range(0, len(all_chunks), insert_batch):
        batch_end = min(i + insert_batch, len(all_chunks))
        chroma_client.insert_vectors(
            collection_name=collection_name,
            vectors=all_vectors[i:batch_end],
            texts=all_chunks[i:batch_end],
            metadata=all_metadatas[i:batch_end]
        )
        logger.info(f"  存入进度: {batch_end}/{len(all_chunks)}")

    logger.info(f"灌入完成！共 {len(all_chunks)} chunks, collection: {collection_name}")

    # 同时为 BM25 准备数据
    from app.rag.retriever import Retriever
    retriever = Retriever(chroma_client=chroma_client)
    retriever.index_collection_for_bm25(
        collection=collection_name,
        texts=all_chunks,
        metadata=all_metadatas
    )
    logger.info("BM25 索引构建完成")

    return {
        "total_chunks": len(all_chunks),
        "total_docs": len(texts),
        "total_chars": total_chars,
        "collection": collection_name
    }


def main():
    parser = argparse.ArgumentParser(description="RAG 知识库灌入脚本")
    parser.add_argument("--data-dir", type=str, default=None, help="数据目录")
    parser.add_argument("--collection", type=str, default="gazetteer_chunks", help="Collection 名称")
    parser.add_argument("--rebuild", action="store_true", help="重建 collection")
    parser.add_argument("--device", type=str, default=None, help="设备 (cuda/cpu)")
    args = parser.parse_args()

    result = ingest_gazetteer(
        data_dir=args.data_dir,
        collection_name=args.collection,
        rebuild=args.rebuild,
        device=args.device
    )

    if result:
        print(f"\n✅ 灌入完成:")
        print(f"   文档数: {result['total_docs']}")
        print(f"   chunks: {result['total_chunks']}")
        print(f"   总字符: {result['total_chars']:,}")
        print(f"   Collection: {result['collection']}")


if __name__ == "__main__":
    main()
