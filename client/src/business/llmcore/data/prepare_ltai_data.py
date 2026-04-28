"""
LTAI 通用数据准备脚本
支持 .txt / .md 格式，自动检测并提取训练文本。
自适应上下文长度（根据硬件资源自动调整 block_size）。

用法：
    python prepare_ltai_data.py --input data/raw/table_cell_input.txt --dataset table_cell
    python prepare_ltai_data.py --input data/raw/ --dataset table_cell  # 批量处理目录
"""

import os
import re
import argparse
import numpy as np
from pathlib import Path
from typing import List, Optional


def read_text_file(filepath: str) -> str:
    """读取 .txt 文件，返回文本内容"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def read_markdown_file(filepath: str) -> str:
    """
    读取 .md 文件，提取正文（去除 Markdown 格式标记）。
    保留段落结构，去除 # ## 标题、**加粗**、[链接]() 等标记。
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 移除代码块（```...```）
    content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    # 移除行内代码（`...`）
    content = re.sub(r'`[^`]*`', '', content)
    # 移除图片（![...](...)）
    content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
    # 将链接替换为文本（[text](url) → text）
    content = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', content)
    # 移除 Markdown 标题标记（# ## ### 等）
    content = re.sub(r'^#{1,6}\s+', '', content, flags=re.MULTILINE)
    # 移除加粗/斜体标记（**...** 或 *...*）
    content = re.sub(r'\*{1,2}([^\*]*)\*{1,2}', r'\1', content)
    # 移除水平线（--- 或 ***）
    content = re.sub(r'^[-*_]{3,}\s*$', '', content, flags=re.MULTILINE)
    # 移除 HTML 标签
    content = re.sub(r'<[^>]+>', '', content)

    return content


def load_training_data(input_path: str) -> str:
    """
    加载训练数据，支持：
    - 单个文件（.txt 或 .md）
    - 目录（自动扫描所有 .txt 和 .md 文件）
    """
    input_path = Path(input_path)

    if input_path.is_file():
        # 单个文件
        if input_path.suffix == '.md':
            print(f"  [读取] Markdown 文件: {input_path.name}")
            return read_markdown_file(str(input_path))
        else:  # .txt 或默认
            print(f"  [读取] 文本文件: {input_path.name}")
            return read_text_file(str(input_path))

    elif input_path.is_dir():
        # 目录：扫描所有 .txt 和 .md 文件
        all_text = []
        for ext in ['*.txt', '*.md', '*.markdown']:
            files = list(input_path.rglob(ext))
            for fpath in files:
                if fpath.suffix == '.md':
                    print(f"  [读取] Markdown: {fpath.name}")
                    all_text.append(read_markdown_file(str(fpath)))
                else:
                    print(f"  [读取] 文本: {fpath.name}")
                    all_text.append(read_text_file(str(fpath)))

        if not all_text:
            raise ValueError(f"目录 {input_path} 中没有找到 .txt 或 .md 文件")

        combined = "\n\n".join(all_text)
        print(f"  [合并] 共 {len(all_text)} 个文件，总长度: {len(combined)} 字符")
        return combined

    else:
        raise FileNotFoundError(f"输入路径不存在: {input_path}")


def auto_detect_block_size(available_vram_gb: float = 0) -> int:
    """
    自适应上下文长度（根据可用 VRAM 自动推荐 block_size）
    如果 available_vram_gb=0（未知），则使用保守值。
    """
    if available_vram_gb >= 40:
        return 2048
    elif available_vram_gb >= 20:
        return 1024
    elif available_vram_gb >= 8:
        return 512
    elif available_vram_gb >= 4:
        return 256
    else:
        return 128  # CPU 或低显存


def prepare_dataset(
    input_path: str,
    dataset_name: str,
    output_dir: str = "data",
    val_ratio: float = 0.1,
    force_block_size: Optional[int] = None,
):
    """
    准备训练数据集（兼容 nanoGPT 的 prepare.py 输出格式）

    参数：
    - input_path: 输入文件或目录
    - dataset_name: 数据集名称（如 "table_cell"）
    - output_dir: 输出目录（默认 "data"）
    - val_ratio: 验证集比例（默认 0.1）
    - force_block_size: 强制指定 block_size（如果为 None，则自动检测）
    """
    import torch
    from pathlib import Path as PathLib

    # 1. 加载训练数据（支持 .txt / .md）
    print(f"\n[1/5] 加载训练数据...")
    data = load_training_data(input_path)
    print(f"  [OK] 数据长度: {len(data)} 字符")

    # 2. 创建字符级词表（与 nanoGPT 的 prepare.py 对齐）
    print(f"\n[2/5] 创建字符级词表...")
    chars = sorted(list(set(data)))
    vocab_size = len(chars)
    print(f"  [OK] 词表大小: {vocab_size}")

    stoi = {ch: i for i, ch in enumerate(chars)}
    itos = {i: ch for i, ch in enumerate(chars)}

    # 3. 编码数据
    print(f"\n[3/5] 编码数据...")
    encoded = np.array([stoi[ch] for ch in data], dtype=np.uint16)
    print(f"  [OK] 编码后长度: {len(encoded)} tokens")

    # 4. 分割训练集/验证集
    print(f"\n[4/5] 分割数据集 (val_ratio={val_ratio})...")
    n = len(encoded)
    val_size = int(n * val_ratio)
    train_data = encoded[:-val_size]
    val_data = encoded[-val_size:]
    print(f"  [OK] 训练集: {len(train_data)} tokens")
    print(f"  [OK] 验证集: {len(val_data)} tokens")

    # 5. 保存为二进制文件（兼容 nanoGPT）
    print(f"\n[5/5] 保存数据集...")
    out_dir = PathLib(output_dir) / dataset_name
    out_dir.mkdir(parents=True, exist_ok=True)

    train_path = out_dir / "train.bin"
    val_path = out_dir / "val.bin"

    train_data.tofile(str(train_path))
    val_data.tofile(str(val_path))

    # 保存元数据（兼容 nanoGPT 的 meta.pkl）
    meta = {
        "vocab_size": vocab_size,
        "stoi": stoi,
        "itos": itos,
        "block_size": force_block_size or auto_detect_block_size(),
        "source_files": [str(input_path)],
    }

    import pickle
    with open(out_dir / "meta.pkl", "wb") as f:
        pickle.dump(meta, f)

    print(f"  [OK] 训练集保存到: {train_path}")
    print(f"  [OK] 验证集保存到: {val_path}")
    print(f"  [OK] 元数据保存到: {out_dir / 'meta.pkl'}")

    # 打印统计信息
    print(f"\n" + "=" * 60)
    print(f"数据集准备完成！")
    print(f"  词表大小: {vocab_size}")
    print(f"  训练集: {len(train_data)} tokens ({os.path.getsize(train_path)} bytes)")
    print(f"  验证集: {len(val_data)} tokens ({os.path.getsize(val_path)} bytes)")
    print(f"  block_size（推荐）: {meta['block_size']}")
    print(f"=" * 60)

    return str(train_path), str(val_path), meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LTAI 通用数据准备脚本")
    parser.add_argument("--input", type=str, required=True,
                        help="输入文件或目录（支持 .txt / .md）")
    parser.add_argument("--dataset", type=str, required=True,
                        help="数据集名称（如 table_cell, regulation_cell）")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="输出目录（默认：../data 相对于本脚本）")
    parser.add_argument("--val-ratio", type=float, default=0.1,
                        help="验证集比例（默认 0.1）")
    parser.add_argument("--block-size", type=int, default=None,
                        help="强制指定 block_size（默认自动检测）")
    args = parser.parse_args()

    # 自动计算 output_dir（相对于本脚本的位置）
    if args.output_dir is None:
        script_dir = Path(__file__).parent
        args.output_dir = script_dir.parent / "data"

    prepare_dataset(
        input_path=args.input,
        dataset_name=args.dataset,
        output_dir=args.output_dir,
        val_ratio=args.val_ratio,
        force_block_size=args.block_size,
    )
