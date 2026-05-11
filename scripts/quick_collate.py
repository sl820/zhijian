"""
快速校勘测试 - 用康熙版和咸丰版的相同卷进行校勘测试
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 项目路径配置
PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
COLLATION_RESULTS_DIR = DATA_PROCESSED_DIR / "collation_results"


class CollationProcessor:
    """
    简单的文本校勘处理器
    用于比较两个版本的文本差异
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def load_text(self, file_path: Path) -> str:
        """加载文本文件"""
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def compute_alignment_score(self, text1: str, text2: str) -> float:
        """
        计算两个文本的对齐分数
        基于字符级相似度
        """
        if not text1 or not text2:
            return 0.0

        # 简单的字符级相似度计算
        # 使用滑动窗口匹配
        matches = 0
        total = min(len(text1), len(text2))

        # 取样计算（避免性能问题）
        sample_size = min(1000, total)
        step = max(1, total // sample_size)

        for i in range(0, total, step):
            if i < len(text1) and i < len(text2):
                if text1[i] == text2[i]:
                    matches += 1

        return (matches / sample_size) * 100 if sample_size > 0 else 0.0

    def find_differences(self, text1: str, text2: str, chunk_size: int = 500) -> List[Dict]:
        """
        找出两个文本的差异

        Returns:
            差异列表，每个差异是一个字典
        """
        differences = []

        # 按chunk_size分块比较
        chunks1 = [text1[i:i+chunk_size] for i in range(0, len(text1), chunk_size)]
        chunks2 = [text2[i:i+chunk_size] for i in range(0, len(text2), chunk_size)]

        min_chunks = min(len(chunks1), len(chunks2))

        for i in range(min_chunks):
            if chunks1[i] != chunks2[i]:
                # 计算该块的相似度
                common_chars = sum(1 for a, b in zip(chunks1[i], chunks2[i]) if a == b)
                similarity = common_chars / max(len(chunks1[i]), len(chunks2[i])) if chunks1[i] or chunks2[i] else 0

                differences.append({
                    "position": i,
                    "chunk_start": i * chunk_size,
                    "similarity": round(similarity, 3),
                    "length1": len(chunks1[i]),
                    "length2": len(chunks2[i]),
                    "text1_preview": chunks1[i][:100] + "..." if len(chunks1[i]) > 100 else chunks1[i],
                    "text2_preview": chunks2[i][:100] + "..." if len(chunks2[i]) > 100 else chunks2[i],
                })

        return differences

    def process(self, text1: str, text2: str, version1_name: str = "版本1", version2_name: str = "版本2") -> Dict:
        """
        处理两个文本的校勘

        Args:
            text1: 第一个文本（通常是较早的版本）
            text2: 第二个文本（通常是较晚的版本）
            version1_name: 版本1名称
            version2_name: 版本2名称

        Returns:
            包含校勘结果的字典
        """
        self.logger.info(f"开始校勘: {version1_name} vs {version2_name}")
        self.logger.info(f"文本长度: {len(text1):,} vs {len(text2):,}")

        # 计算对齐分数
        alignment_score = self.compute_alignment_score(text1, text2)
        self.logger.info(f"对齐分数: {alignment_score:.2f}%")

        # 找出差异
        differences = self.find_differences(text1, text2)
        self.logger.info(f"发现 {len(differences)} 处差异")

        # 构建结果
        result = {
            "version1": {
                "name": version1_name,
                "length": len(text1),
            },
            "version2": {
                "name": version2_name,
                "length": len(text2),
            },
            "alignment_score": round(alignment_score, 2),
            "difference_count": len(differences),
            "differences": differences[:50],  # 最多保留50个差异
        }

        return result


def find_best_matching_pair() -> Tuple[Optional[Path], Optional[Path], Optional[str]]:
    """
    查找康熙版和咸丰版中最佳匹配的卷

    Returns:
        (kangxi_path, xianfeng_path, volume_name) 或 (None, None, None)
    """
    kangxi_dir = DATA_RAW_DIR / "kangxi"
    xianfeng_dir = DATA_RAW_DIR / "xianfeng"

    if not kangxi_dir.exists() or not xianfeng_dir.exists():
        return None, None, None

    # 尝试匹配"卷一"
    kangxi_vol1 = kangxi_dir / "卷一.txt"
    xianfeng_vol1 = xianfeng_dir / "卷一.txt"

    if kangxi_vol1.exists() and xianfeng_vol1.exists():
        return kangxi_vol1, xianfeng_vol1, "卷一"

    # 尝试其他卷
    kangxi_files = {f.stem: f for f in kangxi_dir.glob("*.txt")}
    xianfeng_files = {f.stem: f for f in xianfeng_dir.glob("*.txt")}

    for name in ["卷一", "卷二", "卷三"]:
        if name in kangxi_files and name in xianfeng_files:
            return kangxi_files[name], xianfeng_files[name], name

    # 返回第一对匹配的
    common_names = set(kangxi_files.keys()) & set(xianfeng_files.keys())
    if common_names:
        name = sorted(common_names)[0]
        return kangxi_files[name], xianfeng_files[name], name

    return None, None, None


def check_data_exists() -> bool:
    """检查数据是否已提取"""
    kangxi_dir = DATA_RAW_DIR / "kangxi"
    xianfeng_dir = DATA_RAW_DIR / "xianfeng"

    if not kangxi_dir.exists() or not xianfeng_dir.exists():
        return False

    kangxi_files = list(kangxi_dir.glob("*.txt"))
    xianfeng_files = list(xianfeng_dir.glob("*.txt"))

    return len(kangxi_files) > 0 and len(xianfeng_files) > 0


def print_instructions():
    """打印运行说明"""
    logger.warning("=" * 60)
    logger.warning("数据文件尚未提取！")
    logger.warning("=" * 60)
    logger.info("\n请先运行 process_guanzhi.py 来提取数据:")
    logger.info("  python scripts/process_guanzhi.py")
    logger.info("\n或者手动运行:")
    logger.info(f"  cd {PROJECT_ROOT}")
    logger.info("  python -m scripts.process_guanzhi")
    logger.warning("=" * 60)


def print_diff_summary(result: Dict):
    """打印差异汇总"""
    print("\n" + "=" * 60)
    print("校勘结果汇总")
    print("=" * 60)
    print(f"版本1: {result['version1']['name']} ({result['version1']['length']:,} 字符)")
    print(f"版本2: {result['version2']['name']} ({result['version2']['length']:,} 字符)")
    print(f"对齐分数: {result['alignment_score']}%")
    print(f"差异块数: {result['difference_count']}")
    print("=" * 60)

    if result['differences']:
        print("\n前5个差异预览:")
        for i, diff in enumerate(result['differences'][:5]):
            print(f"\n  差异 {i+1} (位置 {diff['position']}, 相似度 {diff['similarity']:.1%}):")
            print(f"    {result['version1']['name']}: {diff['text1_preview'][:80]}...")
            print(f"    {result['version2']['name']}: {diff['text2_preview'][:80]}...")


def main():
    """主函数"""
    logger.info("快速校勘测试脚本启动")
    logger.info(f"项目根目录: {PROJECT_ROOT}")

    # 检查数据是否存在
    if not check_data_exists():
        print_instructions()
        return

    # 确保输出目录存在
    COLLATION_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 查找最佳匹配的卷
    kangxi_path, xianfeng_path, volume_name = find_best_matching_pair()

    if not kangxi_path or not xianfeng_path:
        logger.error("未找到匹配的卷")
        print_instructions()
        return

    logger.info(f"使用配对: {volume_name}")
    logger.info(f"  康熙版: {kangxi_path}")
    logger.info(f"  咸丰版: {xianfeng_path}")

    try:
        # 加载文本
        processor = CollationProcessor()
        text1 = processor.load_text(kangxi_path)
        text2 = processor.load_text(xianfeng_path)

        # 进行校勘
        result = processor.process(
            text1, text2,
            version1_name=f"康熙版 {volume_name}",
            version2_name=f"咸丰版 {volume_name}"
        )

        # 打印汇总
        print_diff_summary(result)

        # 保存完整结果到JSON
        output_file = COLLATION_RESULTS_DIR / f"collation_{volume_name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"\n完整结果已保存到: {output_file}")
        print("=" * 60)

    except Exception as e:
        logger.error(f"校勘过程出错: {e}")
        raise


if __name__ == "__main__":
    main()
