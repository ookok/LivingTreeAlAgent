"""
Training script for table_cell model
Based on nanoGPT train.py, adapted for EIA table filling task
Supports both CPU and single-GPU training (no distributed)
"""
import os
import time
import math
import pickle
from contextlib import nullcontext

import torch
import torch.nn.functional as F

# Local imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _nanogpt_src.model import GPT, GPTConfig

# Configuration for table_cell
config = {
    # Model architecture (matches DEFAULT_CELL_CONFIGS in __init__.py)
    'n_layer': 6,
    'n_head': 8,
    'n_embd': 512,
    'block_size': 128,  # Reduced for small dataset
    'vocab_size': 613,  # Actual vocab size from data
    'bias': False,
    'dropout': 0.1,

    # Training parameters
    'batch_size': 8,  # Small batch for small dataset
    'gradient_accumulation_steps': 1,
    'max_iters': 500,  # Moderate training (increase to 2000 for full training)
    'learning_rate': 3e-4,
    'weight_decay': 0.1,
    'beta1': 0.9,
    'beta2': 0.95,
    'grad_clip': 1.0,

    # Learning rate decay
    'decay_lr': True,
    'warmup_iters': 100,
    'lr_decay_iters': 2000,

    # Data
    'dataset': 'table_cell',
    'out_dir': os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cells'),

    # Evaluation
    'eval_interval': 100,
    'eval_iters': 50,

    # Device
    'device': 'cuda' if torch.cuda.is_available() else 'cpu',
    'dtype': 'float32',  # Use float32 for CPU training
    'compile': False,  # Disable torch.compile for compatibility
}

def get_lr(iter_num, config):
    """Learning rate schedule with warmup and cosine decay"""
    lr = config['learning_rate']
    if iter_num < config['warmup_iters']:
        lr = lr * iter_num / config['warmup_iters']
    elif iter_num > config['lr_decay_iters']:
        lr = lr * 0.1  # Small decay after schedule
    else:
        decay_ratio = (iter_num - config['warmup_iters']) / (config['lr_decay_iters'] - config['warmup_iters'])
        assert 0 <= decay_ratio <= 1
        coeff = 0.5 * (1.0 + math.cos(math.pi * decay_ratio))
        lr = config['learning_rate'] * coeff
    return lr

def load_data(dataset, out_dir):
    """Load training and validation data"""
    import numpy as np

    # Construct path relative to this script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, '..', 'data', dataset)
    data_dir = os.path.abspath(data_dir)

    train_path = os.path.join(data_dir, 'train.bin')
    val_path = os.path.join(data_dir, 'val.bin')

    print(f"Loading training data from: {train_path}")
    print(f"Loading validation data from: {val_path}")

    # Load as numpy uint16, then convert to torch long
    # (prepare.py saves as np.uint16)
    train_data_np = np.fromfile(train_path, dtype=np.uint16)
    val_data_np = np.fromfile(val_path, dtype=np.uint16)

    train_data = torch.from_numpy(train_data_np.astype(np.int64))
    val_data = torch.from_numpy(val_data_np.astype(np.int64))

    print(f"Train data size: {train_data.shape}")
    print(f"Val data size: {val_data.shape}")

    return train_data, val_data

def get_batch(split, train_data, val_data, config):
    """Get a batch of data"""
    data = train_data if split == 'train' else val_data
    block_size = config['block_size']
    batch_size = config['batch_size']

    ix = torch.randint(len(data) - block_size, (batch_size,))
    x = torch.stack([data[i:i+block_size] for i in ix])
    y = torch.stack([data[i+1:i+block_size+1] for i in ix])
    x, y = x.to(config['device']), y.to(config['device'])
    return x, y

@torch.no_grad()
def estimate_loss(model, train_data, val_data, config):
    """Estimate loss on train and validation sets"""
    out = {}
    model.eval()
    for split in ['train', 'val']:
        losses = torch.zeros(config['eval_iters'])
        for k in range(config['eval_iters']):
            X, Y = get_batch(split, train_data, val_data, config)
            logits, loss = model(X, Y)
            losses[k] = loss.item()
        out[split] = losses.mean()
    model.train()
    return out

def train():
    """Main training loop"""
    # Set up device
    device = config['device']
    print(f"Training on: {device}")

    # Load data
    train_data, val_data = load_data(config['dataset'], config['out_dir'])
    print(f"Train data shape: {train_data.shape}")
    print(f"Val data shape: {val_data.shape}")

    # Initialize model
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
    model.to(device)

    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config['learning_rate'],
        betas=(config['beta1'], config['beta2']),
        weight_decay=config['weight_decay'],
    )

    # Training loop
    iter_num = 0
    best_val_loss = float('inf')

    print(f"Starting training for {config['max_iters']} iterations...")
    start_time = time.time()

    while iter_num < config['max_iters']:
        # Get batch
        xb, yb = get_batch('train', train_data, val_data, config)

        # Forward pass
        logits, loss = model(xb, yb)

        # Backward pass
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), config['grad_clip'])
        optimizer.step()

        # Evaluation
        if iter_num % config['eval_interval'] == 0 or iter_num == config['max_iters'] - 1:
            losses = estimate_loss(model, train_data, val_data, config)
            elapsed = time.time() - start_time
            print(f"iter {iter_num}: train loss {losses['train']:.4f}, val loss {losses['val']:.4f}, time {elapsed:.2f}s")

            # Save checkpoint if best
            if losses['val'] < best_val_loss:
                best_val_loss = losses['val']
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
                    'optimizer': optimizer.state_dict(),
                    'iter_num': iter_num,
                    'best_val_loss': best_val_loss,
                    'config': config,
                }
                checkpoint_path = os.path.join(config['out_dir'], 'table_cell_v1.pt')
                os.makedirs(config['out_dir'], exist_ok=True)
                torch.save(checkpoint, checkpoint_path)
                print(f"  -> Saved checkpoint to {checkpoint_path}")

        iter_num += 1

    # Save final checkpoint
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
        'optimizer': optimizer.state_dict(),
        'iter_num': iter_num,
        'best_val_loss': best_val_loss,
        'config': config,
    }
    checkpoint_path = os.path.join(config['out_dir'], 'table_cell_v1_final.pt')
    torch.save(checkpoint, checkpoint_path)
    print(f"\nTraining complete! Final checkpoint saved to {checkpoint_path}")
    print(f"Best val loss: {best_val_loss:.4f}")

if __name__ == '__main__':
    train()
