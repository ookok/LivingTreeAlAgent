"""
Test the trained table_cell checkpoint with LLMCoreAdapter
"""
import os
import sys

# Add llmcore/ directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from adapter import LLMCoreAdapter

def main():
    print("=" * 60)
    print("Testing LLMCoreAdapter with trained table_cell checkpoint")
    print("=" * 60)

    # Path to the trained checkpoint
    checkpoint_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', 'cells', 'table_cell_v1.pt'
    )
    checkpoint_path = os.path.abspath(checkpoint_path)

    print(f"\nLoading checkpoint from: {checkpoint_path}")
    print(f"Checkpoint exists: {os.path.exists(checkpoint_path)}")

    if not os.path.exists(checkpoint_path):
        print("[ERROR] Checkpoint not found!")
        return False

    try:
        # Create adapter (requires cell_name and checkpoint_path)
        print("\n[1/3] Creating LLMCoreAdapter...")
        cell_name = "table_cell"  # Must match the cell name
        adapter = LLMCoreAdapter(cell_name, checkpoint_path)
        print(f"[OK] Adapter created successfully!")
        print(f"  - Cell name: {adapter.cell_name}")
        print(f"  - Checkpoint: {adapter.checkpoint_path}")
        print(f"  - Model config: block_size={adapter.model.config.block_size}, vocab_size={adapter.model.config.vocab_size}")

        # Test streaming interface (chat_stream)
        print("\n[2/3] Testing StreamChunk streaming interface...")
        test_prompt = "<project_name>某化工厂扩建项目<location>广东省深圳市"
        print(f"  Prompt: {test_prompt}")
        stream_chunks = []
        for chunk in adapter.chat_stream(
            messages=[{"role": "user", "content": test_prompt}],
            max_new_tokens=30,
            temperature=0.8,
            top_k=50
        ):
            stream_chunks.append(chunk)

        print(f"[OK] Streaming generation complete!")
        print(f"  Total chunks: {len(stream_chunks)}")
        if stream_chunks:
            first = stream_chunks[0]
            print(f"  First chunk delta: {first.delta[:50] if first.delta else 'N/A'}")
            print(f"  First chunk done: {first.done}")
        full_text = "".join([c.delta for c in stream_chunks if c.delta])
        print(f"  Generated text: {full_text[:100]}...")

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        print("\nThe trained table_cell model can be loaded and used for inference!")
        print("\nNext steps:")
        print("  1. Run full training with max_iters=2000")
        print("  2. Register the model in GlobalModelRouter")
        print("  3. Integrate with the EIA table filling pipeline")

        return True

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
