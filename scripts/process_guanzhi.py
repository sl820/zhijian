"""
固安县志多版本数据处理脚本
1. 提取康熙版、咸丰版PDF文本
2. 提取98年版文本（更容易）
3. 对应卷配对（卷一康熙 vs 卷一咸丰）
4. 输出到 data/raw/ 目录
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from tqdm import tqdm

from pdf_extractor import PDFExtractor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 版本配置
VERSION_CONFIGS = {
    "kangxi": {
        "path": "E:/文献学/固安县志/固安县志（康熙）",
        "files": {
            "卷首": "卷首（叙一 序二 目录 旧序 历修姓名 例言 图 廵幸志）.pdf",
            "卷一": "卷一 封域志（星野 疆界 沿革 县名 形胜 川凟 风俗 祥异）.pdf",
            "卷二": "卷二 建置志（城池 公署 正祀 学校 坊表 街巷 乡里 集塲 堡寨 堤堰 桥梁 古迹 坟墓 寺庙）.pdf",
            "卷三": "卷三 赋役志（户口 田赋 徭役 驿逓 器杖 土产）.pdf",
            "卷四": "卷四 官师志（知县 县丞 主簿 典史 训导 教谕 廵检 武职 封建）.pdf",
            "卷五": "卷五 选举志（进士 举人 贡生 监生 椽吏 武进士 武举）.pdf",
            "卷六": "卷六 人物志（文治 武功 戚畹 封赠 恩荫 隐逸 仁厚 孝友 忠节 贞烈 释僊）.pdf",
            "卷七": "卷七 艺文志旧集（赋 疏 箴 诗 记 文）.pdf",
            "卷八": "卷八 艺文志新集（奏疏 牌记 序 详呈 杂记 诗 对联）.pdf",
        }
    },
    "xianfeng": {
        "path": "E:/文献学/固安县志/固安县志（咸丰）",
        "files": {
            "卷一": "卷一（序一 序二 旧序 纂修姓氏 凡例 目录 巡幸 图 舆地志）.pdf",
            "卷二": "卷二 建置志（城池 公署 仓场 坛庙 寺观 街巷 村庄 市集 庙会 保甲 坊表 桥梁 堡寨 驿递 兵.pdf",
            "卷三": "卷三 赋役志（户口 起运 存留 盐额 杂税 物产）.pdf",
            "卷四": "卷四 学校志（释奠仪节 陈设图 礼器 乐章 歌谱 乐器 乐谱 合乐节奏 舞器 舞谱 书籍 学额 碑刻.pdf",
            "卷五": "卷五 官师志（名宦 宦绩 封爵 知县 县丞 主簿 典史 教谕 训导 河员 武职）.pdf",
            "卷六": "卷六 选举志（荐辟 进士 举人 贡生 例仕 封赠 恩荫）.pdf",
            "卷七上": "卷七上 人物志 .pdf",
            "卷七下": "卷七下 列女志.pdf",
            "卷八上": "卷八上 艺文志（晋赋 梁赋 元文 明文 国朝文 诗 楹联）.pdf",
            "卷八下": "卷八下 艺文志（晋赋 梁赋 元文 明文 国朝文 诗 楹联）.pdf",
        }
    },
    "1998": {
        "path": "E:/文献学/固安县志/固安县志（98年版）",
        "files": {
            "概述": "概述.pdf",
            "大事记": "大事记.pdf",
            "第一编政区建置": "第一编政区建置.pdf",
            "第二编自然环境": "第二编自然环境.pdf",
            "第三编人口": "第三编人口.pdf",
            "第二十一编人物": "第二十一编人物.pdf",
        }
    }
}

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"


def extract_version(extractor: PDFExtractor, version_name: str, config: Dict) -> Dict[str, int]:
    """
    处理单个版本的固安县志

    Args:
        extractor: PDFExtractor实例
        version_name: 版本名称（如"kangxi"）
        config: 版本配置字典

    Returns:
        各卷文本长度的字典
    """
    logger.info(f"=" * 60)
    logger.info(f"开始处理 {version_name} 版固安县志")
    logger.info(f"=" * 60)

    base_path = Path(config["path"])
    files_config = config["files"]

    # 创建输出目录
    output_dir = DATA_RAW_DIR / version_name
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"输出目录: {output_dir}")

    results = {}
    failed_files = []

    # 使用tqdm显示进度
    volume_names = list(files_config.keys())
    for volume_name in tqdm(volume_names, desc=f"处理 {version_name}"):
        pdf_filename = files_config[volume_name]
        pdf_path = base_path / pdf_filename

        # 检查文件是否存在
        if not pdf_path.exists():
            logger.warning(f"文件不存在，跳过: {pdf_path}")
            failed_files.append((volume_name, pdf_filename))
            continue

        try:
            # 提取该卷所有页面的文本
            pages_text = extractor.extract_all_pages_text(str(pdf_path))

            if not pages_text:
                logger.warning(f"未能提取 {volume_name} 的文本")
                results[volume_name] = 0
                continue

            # 合并所有页面的文本
            full_text = "\n\n".join([f"--- 第 {page['page_num']} 页 ---" for page in pages_text])

            # 添加各页详细内容
            for page in pages_text:
                full_text += f"\n\n{page['text']}"

            # 保存到文件
            output_file = output_dir / f"{volume_name}.txt"
            output_file.write_text(full_text, encoding="utf-8")

            text_length = len(full_text)
            results[volume_name] = text_length
            logger.info(f"  {volume_name}: {text_length} 字符 -> {output_file.name}")

        except Exception as e:
            logger.error(f"处理 {volume_name} 失败: {e}")
            failed_files.append((volume_name, pdf_filename))
            results[volume_name] = 0

    # 打印统计信息
    logger.info(f"\n{version_name} 版处理完成:")
    logger.info(f"  成功: {len([v for v in results.values() if v > 0])} 卷")
    logger.info(f"  失败: {len(failed_files)} 卷")

    if failed_files:
        logger.warning("失败的文件:")
        for vol, fname in failed_files:
            logger.warning(f"  - {vol}: {fname}")

    return results


def print_summary(all_results: Dict[str, Dict[str, int]]):
    """打印所有版本的汇总信息"""
    logger.info("\n" + "=" * 60)
    logger.info("所有版本处理汇总")
    logger.info("=" * 60)

    for version_name, results in all_results.items():
        total_chars = sum(results.values())
        total_volumes = len(results)
        successful = len([v for v in results.values() if v > 0])

        logger.info(f"\n{version_name} 版:")
        logger.info(f"  总卷数: {total_volumes}")
        logger.info(f"  成功: {successful}")
        logger.info(f"  总字符数: {total_chars:,}")

        # 显示各卷详情
        for vol_name, char_count in sorted(results.items()):
            if char_count > 0:
                logger.info(f"    {vol_name}: {char_count:,} 字符")


def main():
    """主函数"""
    logger.info("固安县志多版本数据处理脚本启动")
    logger.info(f"项目根目录: {PROJECT_ROOT}")
    logger.info(f"数据输出目录: {DATA_RAW_DIR}")

    # 确保输出目录存在
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

    # 初始化PDF提取器
    extractor = PDFExtractor()

    # 存储所有结果
    all_results = {}

    # 处理康熙版
    all_results["kangxi"] = extract_version(
        extractor,
        "kangxi",
        VERSION_CONFIGS["kangxi"]
    )

    # 处理咸丰版
    all_results["xianfeng"] = extract_version(
        extractor,
        "xianfeng",
        VERSION_CONFIGS["xianfeng"]
    )

    # 处理98年版
    all_results["1998"] = extract_version(
        extractor,
        "1998",
        VERSION_CONFIGS["1998"]
    )

    # 打印汇总
    print_summary(all_results)

    logger.info("\n所有版本处理完成！")
    logger.info(f"文本文件已保存到: {DATA_RAW_DIR}")

    # 提示下一步操作
    logger.info("\n提示: 运行 quick_collate.py 可以进行校勘测试")


if __name__ == "__main__":
    main()
