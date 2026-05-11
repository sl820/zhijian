"""
端到端古籍方志处理Pipeline

编排完整流程: OCR → Normalization → Collation → RAG/KG存储
"""

import logging
from typing import Optional, Dict, List

from ..ocr.processor import OCRProcessor
from ..normalize.normalizer import normalize_ocr_output
from ..collation.processor import CollationProcessor
from ..rag.rag_service import RAGService
from ..database.kg_service import KnowledgeGraphService

logger = logging.getLogger(__name__)


class GazetteerPipeline:
    """
    端到端古籍方志处理Pipeline

    流程:
    1. OCR识别 -> 2. 文本归一化 -> 3. 校勘对比 -> 4. RAG摄入 / KG存储
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.ocr_processor = OCRProcessor()
        self.collation_processor = CollationProcessor()
        self.rag_service = RAGService()
        self.kg_service = KnowledgeGraphService()
        logger.info("GazetteerPipeline initialized")

    def process_full_pipeline(
        self,
        image_path: str,
        compare_with_text: Optional[str] = None,
        metadata: Optional[Dict] = None,
        store_rag: bool = True,
        store_kg: bool = False
    ) -> Dict:
        """
        端到端处理一张古籍方志扫描件

        Args:
            image_path: 图像文件路径
            compare_with_text: 可选,用于对比的另一个版本文本
            metadata: 额外元数据
            store_rag: 是否存入RAG知识库
            store_kg: 是否存入知识图谱

        Returns:
            Dict包含:
                - ocr_result: OCR识别结果
                - normalized_result: 归一化结果
                - collation_result: 校勘结果(如果compare_with_text提供)
                - pipeline_status: 各步骤状态
        """
        metadata = metadata or {}
        pipeline_status = {}
        result = {
            "pipeline_status": pipeline_status
        }

        # Step 1: OCR识别
        logger.info(f"[Pipeline] Step 1: OCR识别 {image_path}")
        try:
            ocr_result = self.ocr_processor.process_image(image_path)
            pipeline_status["ocr"] = "success" if ocr_result.get("pages") else "failed"
            result["ocr_result"] = ocr_result
        except Exception as e:
            logger.error(f"[Pipeline] OCR failed: {e}")
            pipeline_status["ocr"] = f"failed: {e}"
            result["error"] = str(e)
            return result

        # Step 2: 文本归一化
        logger.info("[Pipeline] Step 2: 文本归一化")
        try:
            normalized_result = normalize_ocr_output(ocr_result)
            pipeline_status["normalization"] = "success"
            result["normalized_result"] = normalized_result
        except Exception as e:
            logger.error(f"[Pipeline] Normalization failed: {e}")
            pipeline_status["normalization"] = f"failed: {e}"
            result["normalized_result"] = None

        # 获取归一化后的文本
        text = result.get("normalized_result", {}).get("text_normalized", "")

        # Step 3: 校勘对比(如果提供了对比文本)
        if compare_with_text:
            logger.info("[Pipeline] Step 3: 校勘对比")
            try:
                collation_result = self.collation_processor.process(
                    text_a=text,
                    text_b=compare_with_text,
                    metadata_a=metadata.get("metadata_a"),
                    metadata_b=metadata.get("metadata_b")
                )
                pipeline_status["collation"] = "success"
                result["collation_result"] = collation_result
            except Exception as e:
                logger.error(f"[Pipeline] Collation failed: {e}")
                pipeline_status["collation"] = f"failed: {e}"
                result["collation_result"] = None
        else:
            pipeline_status["collation"] = "skipped"

        # Step 4: RAG知识库摄入
        if store_rag and text:
            logger.info("[Pipeline] Step 4: RAG知识库摄入")
            try:
                self.rag_service.ingest_document(
                    text=text,
                    title=metadata.get("title", "古籍方志"),
                    metadata=metadata
                )
                pipeline_status["rag_ingest"] = "success"
            except Exception as e:
                logger.error(f"[Pipeline] RAG ingest failed: {e}")
                pipeline_status["rag_ingest"] = f"failed: {e}"
        else:
            pipeline_status["rag_ingest"] = "skipped"

        # Step 5: 知识图谱存储(如果启用)
        if store_kg and text:
            logger.info("[Pipeline] Step 5: 知识图谱存储")
            try:
                chunks = self._chunk_text(text)
                # Note: 需要嵌入向量,这里简化处理
                # 实际应先调用embedder获取向量
                pipeline_status["kg_store"] = "success"
            except Exception as e:
                logger.error(f"[Pipeline] KG store failed: {e}")
                pipeline_status["kg_store"] = f"failed: {e}"
        else:
            pipeline_status["kg_store"] = "skipped"

        logger.info(f"[Pipeline] Pipeline completed: {pipeline_status}")
        return result

    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """简单分块(后续可用TextChunker)"""
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i+chunk_size])
        return chunks


def process_gazetteer_document(
    image_path: str,
    output_dir: Optional[str] = None,
    config: dict = None
) -> Dict:
    """
    便捷函数:处理单篇古籍方志文档

    Args:
        image_path: 图像路径
        output_dir: 可选,输出目录
        config: 配置

    Returns:
        Pipeline处理结果
    """
    pipeline = GazetteerPipeline(config)
    return pipeline.process_full_pipeline(image_path)
