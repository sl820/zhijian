"""
版本管理器 - 管理校勘版本的存储和元数据
版本文件存储在 data/collation_versions/ 目录下
"""
import json
import os
import uuid
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime


class VersionManager:
    """管理校勘版本的存储和元数据"""

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            # 项目根目录下的 data/collation_versions/
            project_root = Path(__file__).parent.parent.parent
            base_dir = project_root / "data" / "collation_versions"
        else:
            base_dir = Path(base_dir)

        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.versions_file = self.base_dir / "versions.json"
        self._ensure_versions_file()

    def _ensure_versions_file(self):
        """确保版本索引文件存在"""
        if not self.versions_file.exists():
            self._save_versions({})

    def _load_versions(self) -> Dict:
        """加载版本索引"""
        try:
            with open(self.versions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save_versions(self, versions: Dict):
        """保存版本索引"""
        with open(self.versions_file, 'w', encoding='utf-8') as f:
            json.dump(versions, f, ensure_ascii=False, indent=2)

    def _generate_id(self) -> str:
        """生成唯一版本ID"""
        return str(uuid.uuid4())[:8]

    def save_text_version(self, name: str, text_content: str, metadata: Dict = None) -> Dict:
        """
        保存文本版本

        Args:
            name: 版本名称（如"康熙志"）
            text_content: 文本内容
            metadata: 额外元数据（year, dynasty 等）

        Returns:
            版本信息字典
        """
        version_id = self._generate_id()
        text_file = self.base_dir / f"{version_id}.txt"

        # 保存文本内容
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text_content)

        # 更新索引
        versions = self._load_versions()
        versions[version_id] = {
            'id': version_id,
            'name': name,
            'type': 'text',
            'text_file': str(text_file),
            'image_file': None,
            'char_count': len(text_content),
            'metadata': metadata or {},
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        self._save_versions(versions)

        return versions[version_id]

    def save_image_version(self, name: str, image_path: str, text_content: str = '',
                           ocr_confidence: float = 0.0, metadata: Dict = None) -> Dict:
        """
        保存图片版本（OCR 结果）

        Args:
            name: 版本名称
            image_path: 原始图片路径
            text_content: OCR 识别文本
            ocr_confidence: OCR 置信度
            metadata: 额外元数据

        Returns:
            版本信息字典
        """
        version_id = self._generate_id()

        # 复制图片到版本目录
        image_ext = Path(image_path).suffix or '.png'
        stored_image = self.base_dir / f"{version_id}{image_ext}"
        if os.path.exists(image_path):
            import shutil
            shutil.copy(image_path, stored_image)

        # 保存文本内容
        text_file = self.base_dir / f"{version_id}.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text_content)

        # 更新索引
        versions = self._load_versions()
        versions[version_id] = {
            'id': version_id,
            'name': name,
            'type': 'image',
            'text_file': str(text_file),
            'image_file': str(stored_image),
            'char_count': len(text_content),
            'ocr_confidence': ocr_confidence,
            'metadata': metadata or {},
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        self._save_versions(versions)

        return versions[version_id]

    def list_versions(self) -> List[Dict]:
        """列出所有已保存的版本"""
        versions = self._load_versions()
        result = []
        for v in versions.values():
            result.append({
                'id': v['id'],
                'name': v['name'],
                'type': v['type'],
                'char_count': v.get('char_count', 0),
                'year': v.get('metadata', {}).get('year'),
                'dynasty': v.get('metadata', {}).get('dynasty'),
                'ocr_confidence': v.get('ocr_confidence', 0.0),
                'created_at': v.get('created_at', '')
            })
        # 按创建时间倒序
        result.sort(key=lambda x: x['created_at'], reverse=True)
        return result

    def get_version(self, version_id: str) -> Optional[Dict]:
        """获取指定版本的内容"""
        versions = self._load_versions()
        v = versions.get(version_id)
        if not v:
            return None

        # 读取文本内容
        text_content = ''
        text_file = v.get('text_file')
        if text_file and os.path.exists(text_file):
            with open(text_file, 'r', encoding='utf-8') as f:
                text_content = f.read()

        return {
            'id': v['id'],
            'name': v['name'],
            'type': v['type'],
            'text_content': text_content,
            'image_file': v.get('image_file'),
            'char_count': v.get('char_count', 0),
            'ocr_confidence': v.get('ocr_confidence', 0.0),
            'metadata': v.get('metadata', {}),
            'created_at': v.get('created_at', '')
        }

    def update_version_text(self, version_id: str, text_content: str) -> bool:
        """更新版本的文本内容（OCR 重新识别后）"""
        versions = self._load_versions()
        v = versions.get(version_id)
        if not v:
            return False

        text_file = v.get('text_file')
        if text_file:
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(text_content)

        v['text_content'] = text_content
        v['char_count'] = len(text_content)
        v['updated_at'] = datetime.now().isoformat()
        versions[version_id] = v
        self._save_versions(versions)
        return True

    def delete_version(self, version_id: str) -> bool:
        """删除指定版本"""
        versions = self._load_versions()
        v = versions.pop(version_id, None)
        if not v:
            return False

        # 删除文本文件
        text_file = v.get('text_file')
        if text_file and os.path.exists(text_file):
            os.remove(text_file)

        # 删除图片文件
        image_file = v.get('image_file')
        if image_file and os.path.exists(image_file):
            os.remove(image_file)

        self._save_versions(versions)
        return True

    def get_all_texts(self, version_ids: List[str]) -> List[Dict]:
        """获取多个版本的文本内容"""
        result = []
        for vid in version_ids:
            v = self.get_version(vid)
            if v:
                result.append(v)
        return result


# 全局单例
_version_manager = None


def get_version_manager() -> VersionManager:
    """获取全局版本管理器实例"""
    global _version_manager
    if _version_manager is None:
        _version_manager = VersionManager()
    return _version_manager
