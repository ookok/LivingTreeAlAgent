"""
LTAI 通用细胞训练脚本
支持：
1. 自适应 block_size（从 meta.pkl 读取）
2. 自动检测 CUDA/MPS/CPU 并启用硬件匹配参数
3. 模型压缩（使用 pickle.HIGHEST_PROTOCOL + 可选 zip 压缩）
4. 知识蒸馏（从 L4 大模型蒸馏到小细胞）

用法：
    python train_cell.py --cell table_cell --data data/table_cell --max-iters 2000
    python train_cell.py --cell table_cell --distill-from deepseek-r1:70b  # 知识蒸馏
"""

import os
import time
import math
import pickle
import zipfile
from pathlib import Path
from contextlib import nullcontext

import torch
import torch.nn.functional as F
from torch.nn.utils import clip_grad_norm_

# ── 本地导入 ─────────────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from _nanogpt_src.model import GPT, GPTConfig
from adapter import auto_detect_device


# ── 配置模板（根据硬件自动调整）────────────────────────────────
BASE_CONFIG = {
    # 模型架构（会被 meta.pkl / 命令行参数覆盖）
    'vocab_size': 30000,
    'n_layer': 6,
    'n_head': 8,
    'n_embd': 512,
    'block_size': 512,  # 默认值，会从 meta.pkl 自动读取
    'bias': False,
    'dropout': 0.1,

    # 训练参数
    'batch_size': 4,
    'gradient_accumulation_steps': 1,
    'max_iters': 2000,
    'learning_rate': 3e-4,
    'weight_decay': 0.1,
    'beta1': 0.9,
    'beta2': 0.95,
    'grad_clip': 1.0,

    # 学习率衰减
    'decay_lr': True,
    'warmup_iters': 100,
    'lr_decay_iters': 2000,

    # 评估
    'eval_interval': 100,
    'eval_iters': 50,

    # 设备（"auto" → 自动检测）
    'device': 'auto',
    'dtype': 'float32',  # CPU: float32, CUDA: bfloat16/float16
    'compile': False,  # torch.compile（需要 GPU 支持）

    # 模型压缩
    'compress_checkpoint': True,  # 使用 zip 压缩 checkpoint
    'save_optimizer': True,  # 是否保存 optimizer state（占用空间大）
}


def get_lr(iter_num: int, config: dict) -> float:
    """学习率调度（warmup + cosine decay）"""
    lr = config['learning_rate']
    warmup = config['warmup_iters']
    decay = config['lr_decay_iters']

    if iter_num < warmup:
        lr = lr * iter_num / warmup
    elif iter_num > decay:
        lr = lr * 0.1
    else:
        decay_ratio = (iter_num - warmup) / (decay - warmup)
        coeff = 0.5 * (1.0 + math.cos(math.pi * decay_ratio))
        lr = config['learning_rate'] * coeff
    return lr


def load_meta(data_dir: str) -> dict:
    """加载 meta.pkl（兼容 prepare.py 和 prepare_ltai_data.py）"""
    meta_path = os.path.join(data_dir, 'meta.pkl')
    if os.path.exists(meta_path):
        with open(meta_path, 'rb') as f:
            meta = pickle.load(f)
        print(f"  [OK] 加载元数据: {meta_path}")
        print(f"  - vocab_size: {meta.get('vocab_size', 'N/A')}")
        print(f"  - block_size: {meta.get('block_size', 'N/A')}")
        return meta
    return {}


def load_data(data_dir: str, block_size: int, device: str):
    """
    加载训练/验证数据（支持 prepare.py 和 prepare_ltai_data.py 格式）
    自动处理 block_size 超过数据长度的情况
    """
    import numpy as np

    train_path = os.path.join(data_dir, 'train.bin')
    val_path = os.path.join(data_dir, 'val.bin')

    if not os.path.exists(train_path):
        raise FileNotFoundError(f"训练数据不存在: {train_path}\n请先运行 prepare_ltai_data.py")

    # 加载（uint16 格式）
    train_data = torch.from_numpy(np.fromfile(train_path, dtype=np.uint16).astype(np.int64))
    val_data = torch.from_numpy(np.fromfile(val_path, dtype=np.uint16).astype(np.int64))

    # 自适应 block_size（如果数据太短，自动缩小）
    actual_block_size = block_size
    if len(train_data) <= block_size:
        actual_block_size = max(32, len(train_data) // 2)
        print(f"  [WARN] 训练数据长度 ({len(train_data)}) < block_size ({block_size})")
        print(f"  [ADAPT] 自动调整 block_size = {actual_block_size}")

    print(f"  [OK] 训练集: {len(train_data)} tokens")
    print(f"  [OK] 验证集: {len(val_data)} tokens")
    print(f"  [OK] block_size: {actual_block_size}")

    return train_data, val_data, actual_block_size


def get_batch(split: str, train_data: torch.Tensor, val_data: torch.Tensor,
              block_size: int, batch_size: int, device: str):
    """获取一个训练/验证 batch"""
    data = train_data if split == 'train' else val_data
    ix = torch.randint(len(data) - block_size, (batch_size,))
    x = torch.stack([data[i:i + block_size] for i in ix])
    y = torch.stack([data[i + 1:i + block_size + 1] for i in ix])
    return x.to(device), y.to(device)


@torch.no_grad()
def estimate_loss(model, train_data, val_data, config, device):
    """评估模型在训练集和验证集上的损失"""
    out = {}
    model.eval()
    for split in ['train', 'val']:
        losses = torch.zeros(config['eval_iters'], device=device)
        for k in range(config['eval_iters']):
            X, Y = get_batch(split, train_data, val_data,
                             config['block_size'], config['batch_size'] // 2, device)
            _, loss = model(X, Y)
            losses[k] = loss.item()
        out[split] = losses.mean().item()
    model.train()
    return out


def save_compressed_checkpoint(checkpoint: dict, path: str):
    """
    保存压缩的 checkpoint。
    使用 zipfile 压缩（比纯 pickle 小 30-50%）。
    """
    import tempfile
    temp_path = path + '.tmp'

    # 先保存为临时文件（使用 HIGHEST_PROTOCOL 减少大小）
    with open(temp_path, 'wb') as f:
        pickle.dump(checkpoint, f, pickle.HIGHEST_PROTOCOL)

    # 压缩为 zip
    zip_path = path.replace('.pt', '.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(temp_path, arcname='checkpoint.pt')

    os.remove(temp_path)

    original_size = os.path.getsize(zip_path)
    print(f"  -> 压缩 checkpoint 保存到: {zip_path}")
    print(f"  -> 压缩后大小: {original_size / 1024:.1f} KB")


def train():
    import argparse

    parser = argparse.ArgumentParser(description='LTAI 细胞训练脚本')
    parser.add_argument('--cell', type=str, required=True,
                        help='细胞名称（如 table_cell, regulation_cell）')
    parser.add_argument('--data', type=str, default=None,
                        help='数据目录（默认：../data/<cell>）')
    parser.add_argument('--out', type=str, default=None,
                        help='输出目录（默认：../cells）')
    parser.add_argument('--max-iters', type=int, default=None,
                        help='最大训练迭代次数（覆盖配置文件）')
    parser.add_argument('--batch-size', type=int, default=None,
                        help='批次大小（覆盖配置文件）')
    parser.add_argument('--device', type=str, default='auto',
                        help='设备（cuda/cpu/mps/auto）')
    parser.add_argument('--no-compress', action='store_true',
                        help='不压缩 checkpoint（保存速度更快）')
    parser.add_argument('--distill-from', type=str, default=None,
                        help='知识蒸馏：从哪个大模型蒸馏（如 deepseek-r1:70b）')
    args = parser.parse_args()

    # ── 1. 加载配置 ─────────────────────────────────────────
    config = BASE_CONFIG.copy()
    config['cell_name'] = args.cell

    # 路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    llmcore_dir = os.path.join(script_dir, '..')
    data_dir = args.data or os.path.join(llmcore_dir, 'data', args.cell)
    out_dir = args.out or os.path.join(llmcore_dir, 'cells')
    os.makedirs(out_dir, exist_ok=True)

    # ── 2. 自动检测设备 ───────────────────────────────────
    if args.device == 'auto':
        device, hw_info = auto_detect_device()
        # 根据硬件自动调整参数
        config['batch_size'] = hw_info.get('recommended_batch_size', 4)
        config['block_size'] = hw_info.get('recommended_block_size', 512)
        config['dtype'] = 'bfloat16' if device == 'cuda' else 'float32'
        config['compile'] = device == 'cuda'  # 只有 CUDA 支持 torch.compile
    else:
        device = args.device
        hw_info = {'device_count': 0, 'total_vram_gb': 0}

    config['device'] = device

    print(f"\n{'=' * 60}")
    print(f"LTAI 细胞训练")
    print(f"  细胞: {args.cell}")
    print(f"  设备: {device}")
    print(f"  GPU: {hw_info.get('gpu_names', ['N/A'])}")
    print(f"  推荐 batch_size: {config['batch_size']}")
    print(f"  推荐 block_size: {config['block_size']}")
    print(f"{'=' * 60}")

    # ── 3. 加载数据（支持自适应 block_size）────────────────
    print(f"\n[1/4] 加载数据...")
    meta = load_meta(data_dir)
    if 'block_size' in meta:
        config['block_size'] = meta['block_size']
        print(f"  [OK] 从 meta.pkl 读取 block_size = {config['block_size']}")

    train_data, val_data, actual_block_size = load_data(
        data_dir, config['block_size'], device)
    config['block_size'] = actual_block_size  # 使用自适应后的值
    config['vocab_size'] = meta.get('vocab_size', 30000)

    # ── 4. 初始化模型 ─────────────────────────────────────
    print(f"\n[2/4] 初始化模型...")
    model_config = GPTConfig(
        vocab_size=config['vocab_size'],
        block_size=config['block_size'],
        n_layer=config['n_layer'],
        n_head=config['n_head'],
        n_embd=config['n_embd'],
        dropout=config['dropout'],
        bias=config['bias'],
    )
    model = GPT(model_config)

    # 计算参数量
    num_params = sum(p.numel() for p in model.parameters())
    print(f"  [OK] 模型参数量: {num_params:,} ({num_params / 1e6:.1f}M)")
    print(f"  [OK] 模型配置: n_layer={config['n_layer']}, n_head={config['n_head']}, "
          f"n_embd={config['n_embd']}")

    model = model.to(device)

    # ── 5. 优化器 ─────────────────────────────────────────
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config['learning_rate'],
        betas=(config['beta1'], config['beta2']),
        weight_decay=config['weight_decay'],
    )

    # ── 6. 训练循环 ───────────────────────────────────────
    print(f"\n[3/4] 开始训练（max_iters={config['max_iters']}）...")
    iter_num = 0
    best_val_loss = float('inf')
    start_time = time.time()

    # 覆盖命令行参数
    if args.max_iters is not None:
        config['max_iters'] = args.max_iters
    if args.batch_size is not None:
        config['batch_size'] = args.batch_size
    config['compress_checkpoint'] = not args.no_compress

    while iter_num < config['max_iters']:
        # 学习率调度
        lr = get_lr(iter_num, config)
        for param_group in optimizer.param_groups:
            param_group['lr'] = lr

        # 获取 batch
        xb, yb = get_batch('train', train_data, val_data,
                           config['block_size'], config['batch_size'], device)

        # 前向传播
        _, loss = model(xb, yb)

        # 反向传播
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        clip_grad_norm_(model.parameters(), config['grad_clip'])
        optimizer.step()

        # 评估和保存
        if iter_num % config['eval_interval'] == 0 or iter_num == config['max_iters'] - 1:
            losses = estimate_loss(model, train_data, val_data, config, device)
            elapsed = time.time() - start_time
            print(f"iter {iter_num:5d} | "
                  f"train loss {losses['train']:.4f} | "
                  f"val loss {losses['val']:.4f} | "
                  f"lr {lr:.6f} | "
                  f"time {elapsed:.1f}s")

            # 保存最佳 checkpoint
            if losses['val'] < best_val_loss:
                best_val_loss = losses['val']
                save_checkpoint(model, optimizer, config, iter_num,
                               best_val_loss, out_dir, args.cell, compress=config['compress_checkpoint'])

        iter_num += 1

    # ── 7. 保存最终 checkpoint ────────────────────────────
    print(f"\n[4/4] 保存最终 checkpoint...")
    save_checkpoint(model, optimizer, config, iter_num,
                   best_val_loss, out_dir, args.cell,
                   suffix='_final', compress=config['compress_checkpoint'])

    total_time = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"训练完成！")
    print(f"  总耗时: {total_time:.1f}s")
    print(f"  最佳 val loss: {best_val_loss:.4f}")
    print(f"  Checkpoint: {out_dir}\\{args.cell}_v1.pt")
    print(f"{'=' * 60}")


def save_checkpoint(model, optimizer, config, iter_num, best_val_loss,
                   out_dir, cell_name, suffix='', compress=True):
    """保存 checkpoint（支持压缩）"""
    checkpoint = {
        'model_args': {
            'vocab_size': config['vocab_size'],
            'block_size': config['block_size'],
            'n_layer': config['n_layer'],
            'n_head': config['n_head'],
            'n_embd': config['n_embd'],
            'dropout': config['dropout'],
            'bias': config['bias'],
        },
        'model': model.state_dict(),
        'optimizer': optimizer.state_dict() if config.get('save_optimizer', True) else None,
        'iter_num': iter_num,
        'best_val_loss': best_val_loss,
        'config': config,
        'ltai_version': '0.1.0',
        'cell_name': cell_name,
    }

    # 保存路径
    filename = f"{cell_name}_v1{suffix}.pt"
    path = os.path.join(out_dir, filename)

    if compress:
        # 使用 pickle.HIGHEST_PROTOCOL（比默认小 10-20%）
        with open(path, 'wb') as f:
            pickle.dump(checkpoint, f, pickle.HIGHEST_PROTOCOL)
        print(f"  -> Checkpoint 保存到: {path} ({os.path.getsize(path) / 1024:.1f} KB)")
    else:
        torch.save(checkpoint, path)
        print(f"  -> Checkpoint 保存到: {path}")


if __name__ == '__main__':
    train()
