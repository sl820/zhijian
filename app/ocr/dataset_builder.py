"""
数据集构建模块
收集、下载、预处理古籍/文物图像数据
"""

import os
import json
import requests
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

class AncientTextDatasetBuilder:
    """古籍/文物铭文数据集构建器"""

    def __init__(self, raw_dir: str, output_dir: str):
        self.raw_dir = Path(raw_dir)
        self.output_dir = Path(output_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 公开数据集URL列表
        self.public_datasets = {
            # 故宫文物数据集（示例URL，需替换为实际地址）
            "palace_museum": {
                "name": "故宫文物",
                "url": None,
                "description": "故宫博物院文物图像"
            },
            # CASIA手写/印刷数据集
            "casia": {
                "name": "CASIA中文手写数据集",
                "url": "http://www.nlpr.ia.ac.cn/databases/handwriting/",
                "description": "中科院自动化所手写识别数据集"
            },
            # 清华大学古籍数据集（GitHub等来源）
            "thu_ancient": {
                "name": "清华大学古籍",
                "url": None,
                "description": "清华大学古籍数字化项目"
            }
        }

    def download_file(self, url: str, dest_path: Path, chunk_size: int = 8192) -> bool:
        """下载文件，支持断点续传"""
        try:
            headers = {}
            if dest_path.exists():
                headers["Range"] = f"bytes={dest_path.stat().st_size}-"
                mode = "ab"
            else:
                mode = "wb"

            response = requests.get(url, stream=True, timeout=30, headers=headers)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(dest_path, mode) as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

            return True
        except Exception as e:
            print(f"Download failed: {e}")
            return False

    def compute_image_hash(self, image_path: Path) -> str:
        """计算图像MD5哈希"""
        hash_md5 = hashlib.md5()
        with open(image_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def deduplicate_images(self, images: List[Path]) -> List[Path]:
        """图像去重"""
        seen_hashes = set()
        unique_images = []

        for img in images:
            img_hash = self.compute_image_hash(img)
            if img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                unique_images.append(img)

        return unique_images

    def collect_local_images(self, folders: List[str], extensions: List[str] = None) -> List[Path]:
        """收集本地文件夹中的图像"""
        if extensions is None:
            extensions = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"]

        all_images = []
        for folder in folders:
            folder_path = Path(folder)
            if folder_path.exists():
                for ext in extensions:
                    all_images.extend(folder_path.rglob(f"*{ext}"))
                    all_images.extend(folder_path.rglob(f"*{ext.upper()}"))

        return self.deduplicate_images(all_images)

    def build_dataset_manifest(self, images: List[Path], output_path: Path) -> Dict:
        """构建数据集清单"""
        manifest = {
            "version": "1.0",
            "description": "古籍/文物铭文OCR训练数据集",
            "total_images": len(images),
            "images": []
        }

        for idx, img_path in enumerate(images):
            entry = {
                "id": f"sample_{idx:05d}",
                "file_path": str(img_path.absolute()),
                "file_name": img_path.name,
                "status": "pending"  # pending, annotated, verified
            }
            manifest["images"].append(entry)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        return manifest


class AnnotationTools:
    """标注工具集"""

    @staticmethod
    def create_coco_format_template() -> Dict:
        """创建COCO格式标注模板"""
        return {
            "info": {
                "description": "古籍OCR标注",
                "version": "1.0"
            },
            "images": [],
            "annotations": [],
            "categories": [{
                "id": 1,
                "name": "text",
                "supercategory": "none"
            }]
        }

    @staticmethod
    def create_easyocr_format_sample(image_path: str, texts: List[Dict]) -> Dict:
        """创建EasyOCR训练格式"""
        return {
            "image_path": image_path,
            "texts": texts  # [{"text": "文字内容", "bbox": [x1,y1,x2,y2]}]
        }


if __name__ == "__main__":
    # 测试数据集构建器
    builder = AncientTextDatasetBuilder(
        raw_dir="C:/Users/hbusl/qi_wu_bo_yan/dataset/ocr_raw",
        output_dir="C:/Users/hbusl/qi_wu_bo_yan/dataset/ocr_training"
    )

    # 收集本地图像（如果有的话）
    local_folders = [
        "C:/Users/hbusl/qi_wu_bo_yan/dataset",
        "E:/博言/文物图像"
    ]

    images = builder.collect_local_images(local_folders)
    print(f"Found {len(images)} images")

    if images:
        manifest = builder.build_dataset_manifest(
            images,
            Path("C:/Users/hbusl/qi_wu_bo_yan/dataset/ocr_training/manifest.json")
        )
        print(f"Manifest saved with {manifest['total_images']} entries")
