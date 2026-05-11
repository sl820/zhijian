import logging
import os
import tempfile
from typing import Optional, List, Dict, Tuple
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Lazy-initialized global processor instances
_ocr_processor = None
_normalization_processor = None
_collation_processor = None
_rag_service = None


def get_rag_service():
    global _rag_service
    if _rag_service is None:
        from ..rag.rag_service import RAGService
        _rag_service = RAGService()
    return _rag_service


def get_ocr_processor(provider: str = "easyocr"):
    """获取 OCR processor 实例，支持选择 provider"""
    from ..ocr.processor import OCRProcessor
    return OCRProcessor(provider=provider)


def get_normalization_processor():
    global _normalization_processor
    if _normalization_processor is None:
        from ..normalize.normalizer import NormalizationProcessor
        _normalization_processor = NormalizationProcessor()
    return _normalization_processor


def get_collation_processor():
    global _collation_processor
    if _collation_processor is None:
        from ..collation.processor import CollationProcessor
        _collation_processor = CollationProcessor()
    return _collation_processor


# Request/Response models using pydantic
class OCRRequest(BaseModel):
    image_path: Optional[str] = None
    detect_variants: bool = True
    detect_taboo: bool = True
    dynasty: str = "qing"
    provider: str = "easyocr"  # easyocr, aliyun, paddleocr


class OCRResponse(BaseModel):
    doc_id: str
    pages: List[Dict]
    ocr_confidence: float
    variant_count: int
    taboo_count: int


class NormalizeRequest(BaseModel):
    text: str
    target_form: str = "simplified"
    detect_entities: bool = True


class NormalizeResponse(BaseModel):
    text_original: str
    text_normalized: str
    entities: List[Dict]


class CollationRequest(BaseModel):
    text_a: str
    text_b: str
    metadata_a: Optional[Dict] = None
    metadata_b: Optional[Dict] = None


class CollationResponse(BaseModel):
    alignment_score: float
    diffs: List[Dict]
    summary: Dict


class RAGRequest(BaseModel):
    question: str
    top_k: int = 5


class RAGResponse(BaseModel):
    answer: str
    sources: List[Dict]


# ==================== Map Extraction Request/Response ====================

class MapExtractRequest(BaseModel):
    image_path: Optional[str] = None
    perform_ocr: bool = True
    georeference: bool = False
    reference_points: List[List[float]] = []  # [[px, py, lon, lat], ...]


class MapExtractResponse(BaseModel):
    image_path: str
    elements: Dict
    text_labels: List[Dict]
    statistics: Dict
    geojson: Optional[Dict] = None


# ==================== Compilation Request/Response ====================

class CompilationSourceRequest(BaseModel):
    type: str  # SourceType value
    url: str
    filters: Optional[Dict] = None


class CompilationRequest(BaseModel):
    sources: List[CompilationSourceRequest]
    deduplicate: bool = True
    merge_strategy: str = "prefer_complete"


class CompilationResponse(BaseModel):
    merged_text: str
    merge_info: Dict
    unique_source_count: int
    total_source_count: int
    duplicate_group_count: int


# ==================== Annotation Extraction Request/Response ====================

class AnnotationExtractRequest(BaseModel):
    image_path: str
    text_blocks: Optional[List[Dict]] = None
    perform_ocr: bool = True


class AnnotationExtractResponse(BaseModel):
    image_path: str
    annotations: List[Dict]
    statistics: Dict


# ==================== KG Store Request/Response ====================

class KGCollationStoreRequest(BaseModel):
    source_a: str
    source_b: str
    alignment_score: float = 0.0
    diffs: List[Dict] = []
    metadata: Optional[Dict] = None


class KGCollationStoreResponse(BaseModel):
    status: str
    source_a: str
    source_b: str
    alignment_score: float
    variation_count: int


router = APIRouter(prefix="/api/v1")


@router.post("/ocr/recognize")
async def recognize_ocr(file: UploadFile = File(...), provider: str = "easyocr"):
    try:
        logger.info(f"OCR recognition request for file: {file.filename}, provider={provider}")
        processor = get_ocr_processor(provider=provider)

        # Save uploaded file to temp
        suffix = Path(file.filename).suffix if file.filename else '.png'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            result = processor.process_image(tmp_path)
            return OCRResponse(
                doc_id=result.get('doc_id', ''),
                pages=result.get('pages', []),
                ocr_confidence=result.get('ocr_confidence', 0.0),
                variant_count=result.get('variant_count', 0),
                taboo_count=result.get('taboo_count', 0)
            )
        finally:
            # Clean up temp file (operate directly, handle if already gone)
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass

    except Exception as e:
        logger.error(f"Error in OCR recognition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/normalize", response_model=NormalizeResponse)
async def normalize_text(request: NormalizeRequest):
    try:
        logger.info(f"Normalization request for text length: {len(request.text)}")
        processor = get_normalization_processor()

        result = processor.process(
            request.text,
            detect_entities=request.detect_entities
        )

        return NormalizeResponse(
            text_original=result.get('text_original', request.text),
            text_normalized=result.get('text_normalized', ''),
            entities=result.get('entities', [])
        )

    except Exception as e:
        logger.error(f"Error in normalization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collation/compare", response_model=CollationResponse)
async def compare_collation(request: CollationRequest):
    try:
        logger.info("Collation comparison request")
        processor = get_collation_processor()

        result = processor.process(
            text_a=request.text_a,
            text_b=request.text_b,
            metadata_a=request.metadata_a,
            metadata_b=request.metadata_b
        )

        return CollationResponse(
            alignment_score=result.get('alignment_score', 0.0),
            diffs=result.get('diffs', []),
            summary=result.get('summary', {})
        )

    except Exception as e:
        logger.error(f"Error in collation comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 版本管理端点 ====================

class VersionUploadResponse(BaseModel):
    id: str
    name: str
    type: str  # "text" or "image"
    char_count: int
    ocr_confidence: float
    text_content: str
    created_at: str


class VersionListResponse(BaseModel):
    versions: List[Dict]
    total: int


class VersionDetailResponse(BaseModel):
    id: str
    name: str
    type: str
    text_content: str
    image_file: Optional[str]
    char_count: int
    ocr_confidence: float
    metadata: Dict
    created_at: str


class MultiVersionCompareRequest(BaseModel):
    version_ids: Optional[List[str]] = None
    texts: Optional[List[str]] = None
    metadata: Optional[List[Dict]] = None


class MultiVersionCompareResponse(BaseModel):
    alignment_matrix: List[List[float]]
    diffs: List[Dict]
    summary: Dict
    version_count: int


def get_version_manager():
    from ..collation.version_manager import get_version_manager
    return get_version_manager()


@router.post("/collation/versions/upload", response_model=VersionUploadResponse)
async def upload_version(
    file: UploadFile = File(...),
    name: str = Form(...),
    metadata: str = Form("{}")
):
    """
    上传版本文件（图片或文本）
    - 图片文件会自动进行 OCR 识别
    - 文本文件直接保存内容
    """
    try:
        import json as json_parser
        parsed_metadata = json_parser.loads(metadata) if metadata else {}

        suffix = Path(file.filename).suffix.lower() if file.filename else ''
        is_image = suffix in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']

        vm = get_version_manager()

        # 保存上传的文件到临时位置
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            if is_image:
                # 图片：OCR 识别
                processor = get_ocr_processor(provider="easyocr")
                ocr_result = processor.process_image(tmp_path)
                text_content = '\n'.join(p.get('text', '') for p in ocr_result.get('pages', []))
                ocr_confidence = ocr_result.get('ocr_confidence', 0.0)

                version_info = vm.save_image_version(
                    name=name,
                    image_path=tmp_path,
                    text_content=text_content,
                    ocr_confidence=ocr_confidence,
                    metadata=parsed_metadata
                )
            else:
                # 文本文件：直接读取内容
                with open(tmp_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()

                version_info = vm.save_text_version(
                    name=name,
                    text_content=text_content,
                    metadata=parsed_metadata
                )
                ocr_confidence = 0.0

            return VersionUploadResponse(
                id=version_info['id'],
                name=version_info['name'],
                type=version_info['type'],
                char_count=version_info.get('char_count', 0),
                ocr_confidence=ocr_confidence,
                text_content=text_content,
                created_at=version_info.get('created_at', '')
            )
        finally:
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass

    except Exception as e:
        logger.error(f"Error uploading version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collation/versions", response_model=VersionListResponse)
async def list_versions():
    """列出所有已保存的版本"""
    try:
        vm = get_version_manager()
        versions = vm.list_versions()
        return VersionListResponse(
            versions=versions,
            total=len(versions)
        )
    except Exception as e:
        logger.error(f"Error listing versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collation/versions/{version_id}", response_model=VersionDetailResponse)
async def get_version(version_id: str):
    """获取指定版本的内容"""
    try:
        vm = get_version_manager()
        version = vm.get_version(version_id)
        if not version:
            raise HTTPException(status_code=404, detail=f"版本 {version_id} 不存在")
        return VersionDetailResponse(**version)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting version {version_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collation/versions/{version_id}")
async def delete_version(version_id: str):
    """删除指定版本"""
    try:
        vm = get_version_manager()
        success = vm.delete_version(version_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"版本 {version_id} 不存在")
        return {"status": "success", "message": f"版本 {version_id} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting version {version_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collation/versions/{version_id}/ocr")
async def reocr_version(version_id: str):
    """对图片版本重新进行 OCR 识别"""
    try:
        vm = get_version_manager()
        version = vm.get_version(version_id)
        if not version:
            raise HTTPException(status_code=404, detail=f"版本 {version_id} 不存在")

        if version['type'] != 'image':
            raise HTTPException(status_code=400, detail="只有图片版本需要 OCR")

        image_file = version.get('image_file')
        if not image_file or not os.path.exists(image_file):
            raise HTTPException(status_code=400, detail="图片文件不存在")

        processor = get_ocr_processor(provider="easyocr")
        ocr_result = processor.process_image(image_file)
        text_content = '\n'.join(p.get('text', '') for p in ocr_result.get('pages', []))
        ocr_confidence = ocr_result.get('ocr_confidence', 0.0)

        vm.update_version_text(version_id, text_content)

        return {
            "status": "success",
            "text_content": text_content,
            "ocr_confidence": ocr_confidence
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error re-ocr version {version_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collation/compare-multi", response_model=MultiVersionCompareResponse)
async def compare_multi_collation(request: MultiVersionCompareRequest):
    """
    多版本比较接口（2-4个版本）
    支持从已保存版本加载或直接传入文本
    """
    try:
        vm = get_version_manager()
        processor = get_collation_processor()

        # 收集版本文本
        texts = []
        metadata_list = []
        version_names = []

        if request.version_ids:
            # 从已保存版本加载
            versions = vm.get_all_texts(request.version_ids)
            for v in versions:
                texts.append(v['text_content'])
                metadata_list.append(v.get('metadata', {}))
                version_names.append(v['name'])
        elif request.texts:
            texts = request.texts
            metadata_list = request.metadata or [{}] * len(texts)
            version_names = [f"版本{i+1}" for i in range(len(texts))]
        else:
            raise HTTPException(status_code=400, detail="需要提供 version_ids 或 texts")

        if len(texts) < 2:
            raise HTTPException(status_code=400, detail="至少需要2个版本")
        if len(texts) > 4:
            raise HTTPException(status_code=400, detail="最多支持4个版本")

        logger.info(f"Multi-version collation: {len(texts)} versions")

        # 多版本两两比较，计算对齐分数矩阵
        alignment_matrix = []
        for i, text_i in enumerate(texts):
            row = []
            for j, text_j in enumerate(texts):
                if i == j:
                    row.append(1.0)
                elif j < i:
                    row.append(alignment_matrix[j][i])
                else:
                    result = processor.process(
                        text_a=text_i,
                        text_b=text_j,
                        metadata_a=metadata_list[i],
                        metadata_b=metadata_list[j]
                    )
                    row.append(result.get('alignment_score', 0.0))
            alignment_matrix.append(row)

        # 以第一个版本为基准，与其他所有版本比较
        base_text = texts[0]
        all_diffs = []
        for i in range(1, len(texts)):
            result = processor.process(
                text_a=base_text,
                text_b=texts[i],
                metadata_a=metadata_list[0],
                metadata_b=metadata_list[i]
            )
            diffs = result.get('diffs', [])
            # 标记差异涉及哪个版本对比
            for d in diffs:
                d['compare_with'] = version_names[i]
            all_diffs.extend(diffs)

        # 汇总统计
        summary = {
            'total_diffs': len(all_diffs),
            'by_type': {},
            'alignment_matrix': alignment_matrix,
            'version_names': version_names
        }
        for d in all_diffs:
            t = d.get('type', 'unknown')
            summary['by_type'][t] = summary['by_type'].get(t, 0) + 1

        return MultiVersionCompareResponse(
            alignment_matrix=alignment_matrix,
            diffs=all_diffs,
            summary=summary,
            version_count=len(texts)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in multi-version collation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "zhijian-api"}


@router.post("/rag/ask", response_model=RAGResponse)
async def rag_ask(request: RAGRequest):
    """RAG智能问答接口"""
    try:
        logger.info(f"RAG question: {request.question}")

        rag_service = get_rag_service()
        result = rag_service.ask(
            question=request.question,
            top_k=request.top_k
        )

        return RAGResponse(
            answer=result.get("answer", ""),
            sources=result.get("sources", [])
        )
    except Exception as e:
        logger.error(f"Error in RAG ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/ingest")
async def rag_ingest(text: str, title: str = "未知文档"):
    """摄入文档到RAG知识库"""
    try:
        logger.info(f"RAG ingest: {title}")

        rag_service = get_rag_service()
        result = rag_service.ingest_document(text=text, title=title)

        return result
    except Exception as e:
        logger.error(f"Error in RAG ingest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/seed")
async def rag_seed(data_dir: str = "data/raw/1998", collection: str = "gazetteer_chunks", rebuild: bool = True):
    """从文本目录灌入数据到RAG知识库"""
    try:
        from pathlib import Path

        # 解析数据目录
        project_root = Path(__file__).parent.parent.parent
        full_data_dir = project_root / data_dir
        if not full_data_dir.exists():
            raise HTTPException(status_code=400, detail=f"数据目录不存在: {full_data_dir}")

        # 加载文本文件
        SKIP_FILES = {"图片.txt", "封面.txt", "目录 (2).txt"}
        texts = []
        for txt_file in sorted(full_data_dir.glob("*.txt")):
            if txt_file.name in SKIP_FILES:
                continue
            try:
                with open(txt_file, encoding="utf-8") as f:
                    content = f.read().strip()
                if len(content) < 50:
                    continue
                texts.append({
                    "title": txt_file.name.replace(".txt", ""),
                    "text": content,
                    "metadata": {"source": str(txt_file)}
                })
            except Exception as e:
                logger.warning(f"加载失败 {txt_file.name}: {e}")

        if not texts:
            raise HTTPException(status_code=400, detail="没有找到有效的文本文件")

        logger.info(f"开始灌入 {len(texts)} 个文件")

        # 配置并使用 RAGService
        rag_service = get_rag_service()
        original_collection = rag_service.collection_name
        try:
            rag_service.collection_name = collection
            retriever = rag_service._get_retriever()
            chroma_client = retriever.milvus_client

            # 重建 collection
            if rebuild and chroma_client.has_collection(collection):
                chroma_client.drop_collection(collection)
                logger.info(f"已删除旧 collection: {collection}")
            if not chroma_client.has_collection(collection):
                # Use embedder's actual dimension (important for TF-IDF fallback)
                embedder = rag_service._get_embedder()
                chroma_client.create_collection(collection, dimension=embedder.embedding_dim)

            # 批量灌入文档（使用 RAGService 自身逻辑）
            total_chunks = 0
            results = rag_service.ingest_documents(texts)
            total_chunks = sum(r.get("chunk_count", 0) for r in results if r.get("status") == "success")

            return {
                "status": "success",
                "collection": collection,
                "total_docs": len(texts),
                "total_chunks": total_chunks,
                "data_dir": str(full_data_dir)
            }
        finally:
            rag_service.collection_name = original_collection

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in RAG seed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rag/status")
async def rag_status():
    """获取 RAG 系统状态"""
    try:
        rag_service = get_rag_service()
        chroma_client = rag_service._get_retriever().milvus_client

        collections = []
        for name in ["gazetteer_chunks"]:
            if chroma_client.has_collection(name):
                try:
                    col = chroma_client.get_collection(name)
                    count = col.count()
                    collections.append({"name": name, "count": count, "exists": True})
                except:
                    collections.append({"name": name, "exists": True, "count": "unknown"})
            else:
                collections.append({"name": name, "exists": False, "count": 0})

        # 检查 embedder
        try:
            embedder = rag_service._get_embedder()
            if embedder._loaded:
                embedder_status = {
                    "model": embedder.model_name,
                    "device": embedder.device,
                    "dimension": embedder.embedding_dim,
                    "status": "loaded" if embedder.model else "tfidf_fallback"
                }
            else:
                embedder_status = {"status": "未加载"}
        except Exception as e:
            embedder_status = {"status": "加载失败", "error": str(e)}

        return {
            "status": "operational",
            "collections": collections,
            "embedder": embedder_status,
            "llm_provider": rag_service.generator.__class__.__name__ if rag_service.generator else "未初始化",
            "embedding_dimension": rag_service.embedding_dim
        }

    except Exception as e:
        logger.error(f"Error in RAG status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "collections": [],
            "embedder": "unknown"
        }


# ==================== Map Extraction Endpoints ====================

_map_service = None


def get_map_service():
    global _map_service
    if _map_service is None:
        from ..map_extraction.map_service import MapExtractionService
        # Use trained U-Net model if available
        model_path = str(Path(__file__).parent.parent.parent / 'models' / 'map_unet_best.pth')
        if not Path(model_path).exists():
            model_path = None  # Fall back to placeholder output
        _map_service = MapExtractionService(model_path=model_path)
    return _map_service


@router.post("/map/extract", response_model=MapExtractResponse)
async def extract_map(
    file: UploadFile = File(None),
    image_path: str = Form(None),
    perform_ocr: bool = Form(True),
    georeference: bool = Form(False),
    reference_points: str = Form("[]")
):
    """舆图信息提取接口（支持文件上传或image_path）"""
    try:
        # Handle file upload
        temp_path = None
        if file:
            suffix = Path(file.filename).suffix if file.filename else '.png'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                temp_path = tmp.name
            effective_path = temp_path
            logger.info(f"Map extraction with uploaded file: {file.filename}")
        else:
            effective_path = image_path or ""

        # Parse reference_points from JSON string
        import json as _json
        try:
            ref_points_list = _json.loads(reference_points) if reference_points else []
            ref_points = [tuple(pt) for pt in ref_points_list] if ref_points_list else None
        except Exception:
            ref_points = None

        logger.info(f"Map extraction request: {effective_path}, georeference={georeference}, points={len(ref_points) if ref_points else 0}")

        service = get_map_service()
        result = service.process(
            image_path=effective_path,
            perform_ocr=perform_ocr,
            georeference=georeference,
            reference_points=ref_points
        )

        # Clean up temp file
        if temp_path:
            try:
                os.remove(temp_path)
            except FileNotFoundError:
                pass

        return MapExtractResponse(
            image_path=result.get("image_path", file.filename if file else image_path or ""),
            elements=result.get("elements", {}),
            text_labels=result.get("text_labels", []),
            statistics=result.get("statistics", {}),
            geojson=result.get("geojson")
        )
    except Exception as e:
        logger.error(f"Error in map extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Compilation Endpoints ====================

_compilation_service = None


def get_compilation_service():
    global _compilation_service
    if _compilation_service is None:
        from ..compilation.compilation_service import CompilationService
        _compilation_service = CompilationService()
    return _compilation_service


@router.post("/compilation/compile", response_model=CompilationResponse)
async def compile_sources(request: CompilationRequest):
    """多源辑佚编译接口"""
    try:
        logger.info(f"Compilation request: {len(request.sources)} sources")

        service = get_compilation_service()

        # Convert request to source configs
        source_configs = [
            {
                "type": src.type,
                "url": src.url,
                "filters": src.filters or {}
            }
            for src in request.sources
        ]

        result = service.compile(
            source_configs=source_configs,
            deduplicate=request.deduplicate,
            merge_strategy=request.merge_strategy
        )

        return CompilationResponse(
            merged_text=result.get("merged_text", ""),
            merge_info=result.get("merge_info", {}),
            unique_source_count=result.get("unique_source_count", 0),
            total_source_count=result.get("total_source_count", 0),
            duplicate_group_count=result.get("duplicate_group_count", 0)
        )
    except Exception as e:
        logger.error(f"Error in compilation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compilation/parse-pdf")
async def parse_pdf(file: UploadFile = File(...)):
    """
    解析 PDF 文件，提取文本内容
    支持上传 PDF 文件并返回提取的文本
    """
    try:
        import pdfplumber

        suffix = Path(file.filename).suffix.lower() if file.filename else '.pdf'
        if suffix != '.pdf':
            raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

        # 保存上传文件到临时位置
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # 使用 pdfplumber 提取文本
            texts = []
            with pdfplumber.open(tmp_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        texts.append(f"--- 第 {i+1} 页 ---\n{page_text}")

            full_text = '\n\n'.join(texts)

            # 统计信息
            char_count = len(full_text)
            page_count = len(pdf.pages) if texts else 0

            logger.info(f"PDF 解析完成: {file.filename}, {page_count} 页, {char_count} 字符")

            return {
                "status": "success",
                "filename": file.filename,
                "text": full_text,
                "char_count": char_count,
                "page_count": page_count
            }
        finally:
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class DeduplicateRequest(BaseModel):
    sources: List[CompilationSourceRequest]
    threshold: float = 0.85
    method: str = "minhash"


class DeduplicateResponse(BaseModel):
    unique_sources: List[Dict]
    duplicate_groups: List[List[int]]
    duplicate_pairs: List[Tuple[int, int, float]]


@router.post("/compilation/deduplicate", response_model=DeduplicateResponse)
async def deduplicate_sources(request: DeduplicateRequest):
    """只做去重，返回重复组信息"""
    try:
        logger.info(f"Deduplication request: {len(request.sources)} sources")

        service = get_compilation_service()

        # Collect sources
        source_configs = [
            {
                "type": src.type,
                "url": src.url,
                "filters": src.filters or {}
            }
            for src in request.sources
        ]
        sources = service.collect_sources(source_configs)

        # Configure deduplicator
        service.deduplicator.threshold = request.threshold
        service.deduplicator.method = request.method

        # Perform deduplication
        result = service.deduplicate(sources, remove_duplicates=False)

        return DeduplicateResponse(
            unique_sources=[
                {
                    "source_name": s.source_name,
                    "text_content": s.text_content[:500],  # Truncate for response
                    "quality_score": s.quality_score
                }
                for s in result["unique_sources"]
            ],
            duplicate_groups=result["duplicate_groups"],
            duplicate_pairs=result["duplicate_pairs"]
        )
    except Exception as e:
        logger.error(f"Error in deduplication: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class MergeRequest(BaseModel):
    texts: List[str]
    metadata: List[Dict]
    strategy: str = "prefer_complete"


class MergeResponse(BaseModel):
    merged_text: str
    merge_info: Dict


@router.post("/compilation/merge", response_model=MergeResponse)
async def merge_texts(request: MergeRequest):
    """只做融合，返回融合后的文本"""
    try:
        logger.info(f"Merge request: {len(request.texts)} texts")

        service = get_compilation_service()

        # Create temporary TextSource objects
        from ..compilation.scraper import TextSource, SourceType
        sources = [
            TextSource(
                source_type=SourceType.CUSTOM_URL,
                source_name=f"source_{i}",
                url="",
                text_content=text,
                metadata=meta,
                quality_score=meta.get("quality_score", 0.5) if meta else 0.5
            )
            for i, (text, meta) in enumerate(zip(request.texts, request.metadata or [{}] * len(request.texts)))
        ]

        # Perform merge
        merged_text, merge_info = service.merge_versions(sources, strategy=request.strategy)

        return MergeResponse(
            merged_text=merged_text,
            merge_info=merge_info
        )
    except Exception as e:
        logger.error(f"Error in merge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Annotation Extraction Endpoints ====================

_annotation_service = None


def get_annotation_service():
    global _annotation_service
    if _annotation_service is None:
        from ..annotation_extract.annotation_service import AnnotationExtractionService
        _annotation_service = AnnotationExtractionService()
    return _annotation_service


@router.post("/annotation/extract", response_model=AnnotationExtractResponse)
async def extract_annotations(
    file: UploadFile = File(None),
    image_path: str = Form(None),
    text_blocks: str = Form("[]"),
    perform_ocr: bool = Form(True)
):
    """批校痕迹提取接口（支持文件上传或image_path）"""
    try:
        # Handle file upload
        temp_path = None
        if file:
            suffix = Path(file.filename).suffix if file.filename else '.png'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                temp_path = tmp.name
            effective_path = temp_path
            logger.info(f"Annotation extraction with uploaded file: {file.filename}")
        else:
            effective_path = image_path or ""

        import json as _json
        try:
            parsed_text_blocks = _json.loads(text_blocks) if text_blocks else []
        except Exception:
            parsed_text_blocks = []

        service = get_annotation_service()
        result = service.process(
            image_path=effective_path,
            text_blocks=parsed_text_blocks,
            perform_ocr=perform_ocr
        )

        # Clean up temp file
        if temp_path:
            try:
                os.remove(temp_path)
            except FileNotFoundError:
                pass

        return AnnotationExtractResponse(
            image_path=result.get("image_path", file.filename if file else image_path or ""),
            annotations=result.get("annotations", []),
            statistics=result.get("statistics", {})
        )
    except Exception as e:
        logger.error(f"Error in annotation extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


_kg_service = None

# KG init background task state
_kg_init_state = {
    "running": False,
    "completed": False,
    "error": None,
    "result": None,
    "started_at": None
}


def get_kg_service():
    global _kg_service
    if _kg_service is None:
        from ..database.kg_service import KnowledgeGraphService
        _kg_service = KnowledgeGraphService()
    return _kg_service


@router.post("/kg/collation-result", response_model=KGCollationStoreResponse)
async def store_collation_result(request: KGCollationStoreRequest):
    """存储校勘结果到知识图谱"""
    try:
        logger.info(f"Storing collation result: {request.source_a} vs {request.source_b}")

        service = get_kg_service()
        result = service.store_collation_result(
            source_a=request.source_a,
            source_b=request.source_b,
            diffs=request.diffs,
            alignment_score=request.alignment_score,
            metadata=request.metadata
        )

        return KGCollationStoreResponse(
            status=result.get("status", "success"),
            source_a=result.get("source_a", ""),
            source_b=result.get("source_b", ""),
            alignment_score=result.get("alignment_score", 0.0),
            variation_count=result.get("variation_count", 0)
        )
    except Exception as e:
        logger.error(f"Error storing collation result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kg/status")
async def kg_status():
    """获取知识图谱系统状态"""
    try:
        service = get_kg_service()
        status = service.get_kg_status()
        return status
    except Exception as e:
        logger.error(f"Error getting KG status: {e}")
        return {"status": "error", "error": str(e)}


@router.get("/kg/persons")
async def kg_list_persons(limit: int = 200):
    """获取所有人物列表"""
    try:
        service = get_kg_service()
        persons = service.get_all_persons()
        return {"status": "success", "persons": persons, "count": len(persons)}
    except Exception as e:
        logger.error(f"Error listing persons: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kg/persons/{name}")
async def kg_get_person(name: str, depth: int = 1):
    """获取单个人物详情（含关系）"""
    try:
        service = get_kg_service()
        person = service.get_person_with_relations(name, depth=depth)
        if not person:
            raise HTTPException(status_code=404, detail=f"人物 '{name}' 未找到")
        return {"status": "success", "person": person}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting person {name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kg/graph")
async def kg_get_graph(limit: int = 200):
    """获取图谱可视化数据"""
    try:
        service = get_kg_service()
        data = service.get_graph_data(limit=limit)
        return {
            "status": "success",
            "nodes": data.get("nodes", []),
            "links": data.get("links", [])
        }
    except Exception as e:
        logger.error(f"Error getting graph data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== KG Build Pipeline ====================

class KGEntityExtractRequest(BaseModel):
    text: str
    source: Optional[str] = ""
    title: Optional[str] = ""


class KGEntityResponse(BaseModel):
    entities: List[Dict]
    stats: Dict


class KGPipelineRequest(BaseModel):
    text: str
    source: str = "unknown"
    title: str = ""
    store: bool = True  # 是否存储到 Neo4j


class KGPipelineResponse(BaseModel):
    status: str
    entities: List[Dict]
    relations: List[Dict]
    stats: Dict


class KGEntityStoreRequest(BaseModel):
    name: str
    entity_type: str = "PER"
    biography: Optional[str] = ""
    dynasty: Optional[str] = ""
    years: Optional[str] = ""
    birthplace: Optional[str] = ""
    title: Optional[str] = ""
    person_type: int = 2  # 0: 苏氏家族, 1: 妻妾, 2: 其他人物
    source: Optional[str] = ""


class KGRelationRequest(BaseModel):
    from_name: str
    to_name: str
    relation_type: str  # FATHER, MOTHER, SON, WIFE, OFFICIAL, etc.
    properties: Optional[Dict] = None


@router.post("/kg/entity/extract")
async def kg_extract_entities(request: KGEntityExtractRequest):
    """从文本中提取实体（不存储）"""
    try:
        from ..kg import KGPipeline

        pipeline = KGPipeline()
        result = pipeline.build_kg_from_text(
            text=request.text,
            source=request.source,
            title=request.title
        )

        return {
            "status": "success",
            "entities": result["entities"],
            "stats": result["stats"],
        }
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kg/build")
async def kg_build_pipeline(request: KGPipelineRequest):
    """从文本构建知识图谱（可选择存储到 Neo4j）"""
    try:
        from ..kg import KGPipeline

        pipeline = KGPipeline()
        result = pipeline.build_kg_from_text(
            text=request.text,
            source=request.source,
            title=request.title
        )

        # 存储到 Neo4j 或 in-memory fallback
        stored_count = 0
        relation_count = 0
        if request.store:
            service = get_kg_service()
            service._ensure_backend()

            # 存储人物实体（兼容 Neo4j 和 in-memory 回退）
            for entity in result["entities"]:
                if entity.get("type") == "PER":
                    name = entity.get("name", "")
                    if not name:
                        continue
                    try:
                        props = {
                            "biography": entity.get("biography", ""),
                            "dynasty": entity.get("dynasty", ""),
                            "years": entity.get("years", ""),
                            "birthplace": entity.get("location", ""),
                            "person_type": entity.get("person_type", 2),
                            "source": entity.get("source", request.source),
                        }
                        if service._use_in_memory:
                            service.in_memory_kg.add_node("Person", name, **props)
                        else:
                            service.neo4j_client.create_person(name=name, **props)
                        stored_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to store person {name}: {e}")

            # 存储关系（兼容 Neo4j 和 in-memory 回退）
            for rel in result["relations"]:
                from_name = rel.get("source", "")
                to_name = rel.get("target", "")
                if not from_name or not to_name:
                    continue
                try:
                    if service._use_in_memory:
                        service.in_memory_kg.add_relationship(
                            from_name, to_name, rel.get("relation", "RELATED"),
                            confidence=rel.get("confidence", 0.5),
                        )
                    else:
                        service.neo4j_client.create_relation(
                            from_name=from_name,
                            to_name=to_name,
                            relation_type=rel.get("relation", "RELATED"),
                            confidence=rel.get("confidence", 0.5),
                        )
                    relation_count += 1
                except Exception as e:
                    logger.warning(f"Failed to store relation {from_name}->{to_name}: {e}")

            result["stats"]["stored_entities"] = stored_count
            result["stats"]["stored_relations"] = relation_count

        return {
            "status": "success",
            "entities": result["entities"],
            "relations": result["relations"],
            "stats": result["stats"],
        }
    except Exception as e:
        logger.error(f"Error building KG: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kg/entity")
async def kg_add_entity(request: KGEntityStoreRequest):
    """添加单个实体到知识图谱"""
    try:
        service = get_kg_service()
        service._ensure_backend()

        name = request.name
        if not name:
            raise HTTPException(status_code=400, detail="name is required")

        props = {
            "biography": request.biography or "",
            "dynasty": request.dynasty or "",
            "years": request.years or "",
            "birthplace": request.birthplace or "",
            "person_type": request.person_type or 2,
            "title": request.title or "",
            "source": request.source or "",
        }

        if service._use_in_memory:
            existing = service.in_memory_kg.get_node(name)
            if existing:
                return {"status": "already_exists", "person": existing}
            node = service.in_memory_kg.add_node("Person", name, **props)
            logger.info(f"Added person to in-memory KG: {name}")
            return {"status": "success", "person": node}
        else:
            person = service.neo4j_client.create_person(name=name, **props)
            if not person:
                raise HTTPException(status_code=500, detail=f"Failed to create person: {name}")
            logger.info(f"Added person to Neo4j: {name}")
            return {"status": "success", "person": person}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kg/relate")
async def kg_add_relation(request: KGRelationRequest):
    """添加关系到知识图谱"""
    try:
        service = get_kg_service()
        service._ensure_backend()

        from_name = request.from_name
        to_name = request.to_name
        rel_type = request.relation_type
        properties = request.properties or {}

        if not from_name or not to_name:
            raise HTTPException(status_code=400, detail="from_name and to_name are required")
        if not to_name:
            to_name = from_name

        if service._use_in_memory:
            # Ensure nodes exist
            for node_name in [from_name, to_name]:
                if not service.in_memory_kg.get_node(node_name):
                    service.in_memory_kg.add_node("Entity", node_name)
            rel = service.in_memory_kg.add_relationship(from_name, to_name, rel_type, **properties)
            logger.info(f"Added relation to in-memory KG: {from_name} -[{rel_type}]-> {to_name}")
            return {"status": "success", "relation": rel}
        else:
            relation = service.neo4j_client.create_relation(
                from_name=from_name,
                to_name=to_name,
                relation_type=rel_type,
                **properties
            )
            if not relation:
                raise HTTPException(status_code=500, detail="Failed to create relation")
            logger.info(f"Added relation to Neo4j: {from_name} -[{rel_type}]-> {to_name}")
            return {"status": "success", "relation": relation}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding relation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== KG 初始化 ====================

class KGInitResponse(BaseModel):
    status: str
    persons_stored: int
    relations_stored: int
    total_persons: int
    total_relations: int
    sample_persons: List[str]


class KGInitStatusResponse(BaseModel):
    running: bool
    completed: bool
    error: Optional[str]
    result: Optional[KGInitResponse]


@router.get("/kg/init/status", response_model=KGInitStatusResponse)
async def kg_init_status():
    """检查 KG 初始化状态"""
    return KGInitStatusResponse(
        running=_kg_init_state["running"],
        completed=_kg_init_state["completed"],
        error=_kg_init_state["error"],
        result=_kg_init_state["result"]
    )


def _run_kg_init_background(clear: bool):
    """后台运行 KG 初始化"""
    import threading
    from pathlib import Path
    from app.kg.pipeline import KGPipeline

    global _kg_init_state
    _kg_init_state = {
        "running": True,
        "completed": False,
        "error": None,
        "result": None,
        "started_at": None
    }

    try:
        project_root = Path(__file__).parent.parent.parent
        person_file = project_root / "data/raw/1998/第二十一编人物.txt"

        if not person_file.exists():
            raise FileNotFoundError(f"人物志文件不存在: {person_file}")

        service = get_kg_service()
        service._ensure_backend()
        kg = service.in_memory_kg

        if clear:
            kg.clear()
            logger.info("KG cleared by background init")

        with open(person_file, encoding="utf-8") as f:
            text = f.read()

        logger.info(f"KG background init: reading {len(text):,} chars")

        pipeline = KGPipeline()
        result = pipeline.build_kg_from_text(
            text=text,
            source="1998年版固安县志·人物志",
            title="第二十一编人物"
        )

        stats = result["stats"]
        logger.info(f"KG pipeline: {stats['person_entities']} persons, {stats['total_relations']} relations extracted")

        dynasty_markers = [
            "西汉", "东汉", "三国", "晋", "南北朝", "南朝", "北朝",
            "隋", "唐", "五代", "宋", "辽", "金", "元", "明", "清"
        ]

        def identify_dynasty(bio_text: str) -> str:
            for marker in dynasty_markers:
                if marker in bio_text:
                    return marker
            return ""

        persons_stored = 0
        relations_stored = 0
        stored_person_names = set()

        for entity in result["entities"]:
            if entity.get("type") != "PER":
                continue
            name = entity.get("name", "")
            if not name or name in stored_person_names:
                continue

            existing = kg.get_node(name)
            if existing:
                stored_person_names.add(name)
                continue

            bio = (entity.get("biography") or "")[:500]
            dynasty = identify_dynasty(bio)
            years = entity.get("years", "")
            birthplace = entity.get("location", "")

            kg.add_node("Person", name,
                dynasty=dynasty,
                years=years,
                birthplace=birthplace,
                person_type=entity.get("person_type", 2),
                biography=bio,
                source="1998年版固安县志·人物志"
            )
            stored_person_names.add(name)
            persons_stored += 1

        # 后处理：家族关系
        import re as _re
        _stored = stored_person_names
        _DYNASTY = set(dynasty_markers)
        _ERA_NAMES = {
            "天监", "永乐", "正统", "景泰", "成化", "弘治", "正德", "嘉靖",
            "隆庆", "万历", "泰昌", "天启", "崇祯", "康熙", "雍正", "乾隆",
            "嘉庆", "道光", "咸丰", "光绪", "宣统", "建元", "永元", "中元",
        }
        _entities_dict = {e["name"]: e for e in result["entities"] if e.get("type") == "PER"}
        _full_text = text

        for person_name in list(_stored):
            entity = _entities_dict.get(person_name, {})
            bio = entity.get("biography", "") or ""
            search_text = bio + _full_text[:5000]

            REL_SUFFIX_PATTERNS = [
                ("之父", "FATHER"), ("之母", "MOTHER"), ("之子", "SON"),
                ("之女", "DAUGHTER"), ("之兄", "ELDER_BROTHER"),
                ("之弟", "YOUNGER_BROTHER"), ("之妻", "WIFE"),
            ]
            for suffix, rel_type in REL_SUFFIX_PATTERNS:
                pattern = person_name + suffix
                pos = 0
                while True:
                    pos = search_text.find(pattern, pos)
                    if pos < 0:
                        break
                    rest = search_text[pos + len(pattern):pos + len(pattern) + 8]
                    skip = 0
                    while skip < len(rest) and not ('\u4e00' <= rest[skip] <= '\u9fff'):
                        skip += 1
                    rest_cjk = rest[skip:]
                    if not rest_cjk:
                        pos += 1
                        continue
                    person_start = pos + len(pattern) - len(suffix)
                    search_back = search_text[max(0, person_start - 10):person_start]
                    target = None
                    for p_name in _stored:
                        if p_name != person_name and len(p_name) >= 2 and search_back.rfind(p_name) >= 0:
                            target = p_name
                            break
                    if target is None:
                        year_m = _re.match(r'([\u4e00-\u9fff]{1,3})年', rest_cjk)
                        if year_m and len(year_m.group(1)) >= 2:
                            cjk_seq = year_m.group(1)
                        else:
                            STOP_CHARS = set('以，。；、：（）""''【】《》' + '0123456789')
                            end_idx = 0
                            while end_idx < len(rest_cjk) and rest_cjk[end_idx] not in STOP_CHARS:
                                end_idx += 1
                            cjk_seq = rest_cjk[:end_idx] if end_idx > 0 else rest_cjk[:4]
                        m = _re.match(r'([\u4e00-\u9fff]{2,4})', cjk_seq)
                        if not m:
                            pos += 1
                            continue
                        target = m.group(1)
                        for s in ["后裔", "后"]:
                            if target.startswith(s):
                                target = target[len(s):]
                                break
                    if not target or len(target) < 2:
                        pos += 1
                        continue
                    if target in _DYNASTY or target in _ERA_NAMES or target[0].isdigit() or target.startswith("之"):
                        pos += 1
                        continue
                    is_substring_of_other = any(
                        target in p and target != p for p in _stored
                    )
                    if not is_substring_of_other:
                        try:
                            kg.add_relationship(person_name, target, rel_type, confidence=0.85)
                            relations_stored += 1
                        except Exception:
                            pass
                    pos += 1

        # 存储 pipeline 抽取的关系
        for rel in result["relations"]:
            from_name = rel.get("source", "")
            to_name = rel.get("target", "")
            if not from_name or not to_name:
                continue
            if to_name in dynasty_markers:
                continue
            if to_name not in stored_person_names:
                continue
            if from_name not in stored_person_names:
                continue
            try:
                kg.add_relationship(
                    from_name, to_name,
                    rel.get("relation", "RELATED"),
                    confidence=rel.get("confidence", 0.5)
                )
                relations_stored += 1
            except Exception as e:
                logger.warning(f"Failed to store relation {from_name}->{to_name}: {e}")

        final_stats = kg.get_stats()
        all_nodes = kg.get_all_nodes(label="Person", limit=5)
        sample_names = [n.get("name", "") for n in all_nodes]

        _kg_init_state["result"] = KGInitResponse(
            status="success",
            persons_stored=persons_stored,
            relations_stored=relations_stored,
            total_persons=final_stats["person_count"],
            total_relations=final_stats["relation_count"],
            sample_persons=sample_names
        )
        _kg_init_state["completed"] = True
        logger.info(f"KG background init complete: {persons_stored} persons, {relations_stored} relations")

    except Exception as e:
        logger.error(f"KG background init error: {e}")
        _kg_init_state["error"] = str(e)
        _kg_init_state["completed"] = True
    finally:
        _kg_init_state["running"] = False


@router.post("/kg/init", response_model=KGInitResponse)
async def kg_init(clear: bool = False, background: bool = False):
    """
    从1998年版人物志文本初始化知识图谱

    处理第二十一编人物.txt中的所有人物实体和关系，
    存储到 in-memory KG（Neo4j不可用时）。
    """
    # 如果已经在运行中，返回错误
    if _kg_init_state["running"]:
        raise HTTPException(status_code=409, detail="KG 初始化已在运行中，请等待完成或检查状态")

    # 如果已完成且有结果，且不是要求clear，直接返回结果
    if _kg_init_state["completed"] and _kg_init_state["result"] and not clear:
        return _kg_init_state["result"]

    # 启动后台任务
    if background:
        import threading
        thread = threading.Thread(target=_run_kg_init_background, args=(clear,))
        thread.daemon = True
        thread.start()
        return KGInitResponse(
            status="started",
            persons_stored=0,
            relations_stored=0,
            total_persons=0,
            total_relations=0,
            sample_persons=[]
        )

    # 同步执行（原逻辑）
    try:
        from pathlib import Path
        from app.kg.pipeline import KGPipeline

        project_root = Path(__file__).parent.parent.parent
        person_file = project_root / "data/raw/1998/第二十一编人物.txt"

        if not person_file.exists():
            raise HTTPException(status_code=404, detail=f"人物志文件不存在: {person_file}")

        service = get_kg_service()
        service._ensure_backend()
        kg = service.in_memory_kg

        if clear:
            kg.clear()
            logger.info("KG cleared by /kg/init?clear=true")

        # 读取文本
        with open(person_file, encoding="utf-8") as f:
            text = f.read()

        logger.info(f"KG init: reading {len(text):,} chars from {person_file.name}")

        # 运行 KG pipeline
        pipeline = KGPipeline()
        result = pipeline.build_kg_from_text(
            text=text,
            source="1998年版固安县志·人物志",
            title="第二十一编人物"
        )

        stats = result["stats"]
        logger.info(
            f"KG pipeline: {stats['person_entities']} persons, "
            f"{stats['total_relations']} relations extracted"
        )

        # 存储人物
        dynasty_markers = [
            "西汉", "东汉", "三国", "晋", "南北朝", "南朝", "北朝",
            "隋", "唐", "五代", "宋", "辽", "金", "元", "明", "清"
        ]

        def identify_dynasty(bio_text: str) -> str:
            for marker in dynasty_markers:
                if marker in bio_text:
                    return marker
            return ""

        persons_stored = 0
        relations_stored = 0  # 累计后处理 + pipeline 两部分关系
        # 已存储的人物名集合，用于关系验证
        stored_person_names = set()

        for entity in result["entities"]:
            if entity.get("type") != "PER":
                continue
            name = entity.get("name", "")
            if not name or name in stored_person_names:
                continue

            existing = kg.get_node(name)
            if existing:
                stored_person_names.add(name)
                continue

            bio = (entity.get("biography") or "")[:500]
            dynasty = identify_dynasty(bio)
            years = entity.get("years", "")
            birthplace = entity.get("location", "")

            kg.add_node("Person", name,
                dynasty=dynasty,
                years=years,
                birthplace=birthplace,
                person_type=entity.get("person_type", 2),
                biography=bio,
                source="1998年版固安县志·人物志"
            )
            stored_person_names.add(name)
            persons_stored += 1

        # 后处理：从原文重新抽取家族关系
        # （pipeline的extract_person_relations因实体消解覆盖短名而失效，
        #  此处直接用stored_person_names在原文中做规则匹配）
        import re as _re
        _stored = stored_person_names
        _DYNASTY = set(dynasty_markers)
        _ERA_NAMES = {
            "天监", "永乐", "正统", "景泰", "成化", "弘治", "正德", "嘉靖",
            "隆庆", "万历", "泰昌", "天启", "崇祯", "康熙", "雍正", "乾隆",
            "嘉庆", "道光", "咸丰", "光绪", "宣统", "建元", "永元", "中元",
        }
        _entities_dict = {e["name"]: e for e in result["entities"] if e.get("type") == "PER"}
        _full_text = text  # 已经加载的原文

        for person_name in list(_stored):
            entity = _entities_dict.get(person_name, {})
            bio = entity.get("biography", "") or ""
            # 同时搜索传记局部和原文全局（传记可能截断关系表述）
            search_text = bio + _full_text[:5000]

            REL_SUFFIX_PATTERNS = [
                ("之父", "FATHER"),
                ("之母", "MOTHER"),
                ("之子", "SON"),
                ("之女", "DAUGHTER"),
                ("之兄", "ELDER_BROTHER"),
                ("之弟", "YOUNGER_BROTHER"),
                ("之妻", "WIFE"),
            ]
            for suffix, rel_type in REL_SUFFIX_PATTERNS:
                pattern = person_name + suffix
                pos = 0
                while True:
                    pos = search_text.find(pattern, pos)
                    if pos < 0:
                        break
                    rest = search_text[pos + len(pattern):pos + len(pattern) + 8]
                    # 跳过非CJK字符（如句号"。"），从CJK字符开始提取
                    skip = 0
                    while skip < len(rest) and not ('\u4e00' <= rest[skip] <= '\u9fff'):
                        skip += 1
                    rest_cjk = rest[skip:]
                    if not rest_cjk:
                        pos += 1
                        continue
                    # 优先：从"之"前面找已知人名（处理"张缅，字元长，张弘策之子"类型）
                    # 排除当前person_name本身，只找其他人名
                    person_start = pos + len(pattern) - len(suffix)
                    search_back = search_text[max(0, person_start - 10):person_start]
                    target = None
                    for p_name in _stored:
                        if p_name != person_name and len(p_name) >= 2 and search_back.rfind(p_name) >= 0:
                            target = p_name
                            break
                    # 回退：提取CJK序列并清理
                    if target is None:
                        year_m = _re.match(r'([\u4e00-\u9fff]{1,3})年', rest_cjk)
                        if year_m and len(year_m.group(1)) >= 2:
                            cjk_seq = year_m.group(1)
                        else:
                            STOP_CHARS = set('以，。；、：（）""''【】《》' + '0123456789')
                            end_idx = 0
                            while end_idx < len(rest_cjk) and rest_cjk[end_idx] not in STOP_CHARS:
                                end_idx += 1
                            cjk_seq = rest_cjk[:end_idx] if end_idx > 0 else rest_cjk[:4]
                        m = _re.match(r'([\u4e00-\u9fff]{2,4})', cjk_seq)
                        if not m:
                            pos += 1
                            continue
                        target = m.group(1)
                        for s in ["后裔", "后"]:
                            if target.startswith(s):
                                target = target[len(s):]
                                break
                    if not target or len(target) < 2:
                        pos += 1
                        continue
                    if target in _DYNASTY or target in _ERA_NAMES or target[0].isdigit() or target.startswith("之"):
                        pos += 1
                        continue
                    is_substring_of_other = any(
                        target in p and target != p for p in _stored
                    )
                    if not is_substring_of_other:
                        try:
                            kg.add_relationship(
                                person_name, target, rel_type, confidence=0.85
                            )
                            relations_stored += 1
                        except Exception:
                            pass
                    pos += 1

        # 存储关系（pipeline抽取的 relations，仅当两端都已在KG时）
        for rel in result["relations"]:
            from_name = rel.get("source", "")
            to_name = rel.get("target", "")
            # 跳过：空目标、目标为朝代名、目标不在人物列表中
            if not from_name or not to_name:
                continue
            if to_name in dynasty_markers:
                continue  # 跳过朝代名
            if to_name not in stored_person_names:
                continue  # 目标不是已识别的人物
            if from_name not in stored_person_names:
                continue  # 源不是已识别的人物
            try:
                kg.add_relationship(
                    from_name, to_name,
                    rel.get("relation", "RELATED"),
                    confidence=rel.get("confidence", 0.5)
                )
                relations_stored += 1
            except Exception as e:
                logger.warning(f"Failed to store relation {from_name}->{to_name}: {e}")

        # 获取最终统计
        final_stats = kg.get_stats()
        all_nodes = kg.get_all_nodes(label="Person", limit=5)
        sample_names = [n.get("name", "") for n in all_nodes]

        logger.info(
            f"KG init complete: {persons_stored} persons, {relations_stored} relations stored. "
            f"Total: {final_stats['person_count']} persons, {final_stats['relation_count']} relations"
        )

        return KGInitResponse(
            status="success",
            persons_stored=persons_stored,
            relations_stored=relations_stored,
            total_persons=final_stats["person_count"],
            total_relations=final_stats["relation_count"],
            sample_persons=sample_names
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in KG init: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def register_routes(app):
    app.include_router(router)
    logger.info("Routes registered")
