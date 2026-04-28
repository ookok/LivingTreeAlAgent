"""
Quick test for table_cell training
Verifies data loading and model forward pass work correctly
"""
import os
import sys
import torch
import numpy as np

# Add llmcore/ directory to path (parent of training/)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from _nanogpt_src.model import GPT, GPTConfig

def test_data_loading():
    """Test data loading"""
    print("=" * 50)
    print("Testing data loading...")
    print("=" * 50)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, '..', 'data', 'table_cell')
    data_dir = os.path.abspath(data_dir)

    train_path = os.path.join(data_dir, 'train.bin')
    val_path = os.path.join(data_dir, 'val.bin')

    print(f"Loading from: {train_path}")
    print(f"Loading from: {val_path}")

    # Load as numpy uint16, then convert to torch
    train_data_np = np.fromfile(train_path, dtype=np.uint16)
    val_data_np = np.fromfile(val_path, dtype=np.uint16)

    train_data = torch.from_numpy(train_data_np.astype(np.int64))
    val_data = torch.from_numpy(val_data_np.astype(np.int64))

    print(f"\n[OK] Train data shape: {train_data.shape}")
    print(f"[OK] Val data shape: {val_data.shape}")
    print(f"[OK] Train data dtype: {train_data.dtype}")
    print(f"[OK] First 20 tokens: {train_data[:20]}")

    return train_data, val_data

def test_model_forward(train_data):
    """Test model forward pass"""
    print("\n" + "=" * 50)
    print("Testing model forward pass...")
    print("=" * 50)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {device}")

    # Create model
    config = GPTConfig(
        vocab_size=613,
        block_size=128,
        n_layer=6,
        n_head=8,
        n_embd=512,
        dropout=0.1,
        bias=False,
    )
    model = GPT(config)
    model.to(device)
    print(f"[OK] Model created with {sum(p.numel() for p in model.parameters())/1e6:.2f}M parameters")

    # Test forward pass
    block_size = 128
    batch_size = 4

    # Get a small batch
    ix = torch.randint(len(train_data) - block_size, (batch_size,))
    x = torch.stack([train_data[i:i+block_size] for i in ix])
    y = torch.stack([train_data[i+1:i+block_size+1] for i in ix])
    x, y = x.to(device), y.to(device)

    print(f"\nInput shape: {x.shape}")
    print(f"Target shape: {y.shape}")

    # Forward pass
    logits, loss = model(x, y)
    print(f"[OK] Logits shape: {logits.shape}")
    print(f"[OK] Loss: {loss.item():.4f}")

    return True

def test_training_step(train_data):
    """Test a single training step"""
    print("\n" + "=" * 50)
    print("Testing training step...")
    print("=" * 50)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    # Create model and optimizer
    config = GPTConfig(
        vocab_size=613,
        block_size=128,
        n_layer=6,
        n_head=8,
        n_embd=512,
        dropout=0.1,
        bias=False,
    )
    model = GPT(config)
    model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)

    # Get batch
    block_size = 128
    batch_size = 4

    ix = torch.randint(len(train_data) - block_size, (batch_size,))
    x = torch.stack([train_data[i:i+block_size] for i in ix])
    y = torch.stack([train_data[i+1:i+block_size+1] for i in ix])
    x, y = x.to(device), y.to(device)

    # Forward and backward
    logits, loss = model(x, y)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    optimizer.step()

    print(f"[OK] Training step completed successfully!")
    print(f"[OK] Loss: {loss.item():.4f}")

    return True

def main():
    print("\n" + "=" * 50)
    print("QUICK TEST: table_cell Training Pipeline")
    print("=" * 50)

    try:
        # Test 1: Data loading
        train_data, val_data = test_data_loading()

        # Test 2: Model forward pass
        test_model_forward(train_data)

        # Test 3: Training step
        test_training_step(train_data)

        print("\n" + "=" * 50)
        print("ALL TESTS PASSED!")
        print("=" * 50)
        print("\nYou can now run the full training with:")
        print("  cd \"D:\\mhzyapp\\LivingTreeAlAgent\\client\\src\\business\\llmcore\\training\"")
        print("  python train_table_cell.py")
        print()

        return True

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
