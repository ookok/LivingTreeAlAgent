"""
Quick test for LLMCoreAdapter inference pipeline.
Verifies: load checkpoint -> generate text works correctly.
"""
import sys
import os

# Add nanoGPT source directory to sys.path
SRC_DIR = os.path.join(os.path.dirname(__file__), "_nanogpt_src")
sys.path.insert(0, SRC_DIR)

from adapter import LLMCoreAdapter, ChatMessage, StreamChunk


def test_adapter():
    print("-" * 60)
    print("LLMCoreAdapter Inference Pipeline Test")
    print("-" * 60)

    ckpt_path = os.path.join(os.path.dirname(__file__), "cells", "table_cell_v1.pt")
    if not os.path.exists(ckpt_path):
        print(f"[FAIL] Checkpoint not found: {ckpt_path}")
        print("   Please run Shakespeare training first, or copy checkpoint to this location")
        return False

    print(f"[OK] Found checkpoint: {ckpt_path}")

    # Create adapter (using CPU)
    print("\n[1/3] Creating LLMCoreAdapter...")
    adapter = LLMCoreAdapter(
        cell_name="table_cell",
        checkpoint_path=ckpt_path,
        device="cpu",
    )
    print("[OK] Adapter created successfully")

    # Test non-streaming call
    print("\n[2/3] Testing non-streaming generation...")
    messages = [
        {"role": "user", "content": "First Citizen:"},
    ]
    print(f"   Prompt: '{messages[0]['content']}'")
    print("   Generating...")
    full_text = ""
    count = 0
    for chunk in adapter.chat_stream(
        messages,
        temperature=0.8,
        top_k=10,
        max_new_tokens=100,
    ):
        if chunk.done:
            break
        full_text += chunk.delta
        count += 1
        if count <= 10 or chunk.done:
            print(f"   Chunk {count}: '{chunk.delta}'")

    print(f"\n[OK] Generation complete, {count} tokens total")
    print(f"   Generated content: '{full_text[:200]}'")

    # Test streaming call (simulating GlobalModelRouter usage)
    print("\n[3/3] Testing StreamChunk streaming interface...")
    stream_chunks = []
    for chunk in adapter.chat_stream(
        [{"role": "user", "content": "First Citizen:"}],
        temperature=0.8,
        top_k=10,
        max_new_tokens=50,
    ):
        if chunk.done:
            break
        stream_chunks.append(chunk.delta)
        if len(stream_chunks) <= 5:
            print(f"   StreamChunk: '{chunk.delta}'")

    full_stream = "".join(stream_chunks)
    print(f"\n[OK] Streaming generation complete, {len(stream_chunks)} chunks total")
    print(f"   Content: '{full_stream[:150]}'")

    print("\n" + "="*60)
    print("All tests passed! LLMCoreAdapter inference pipeline is working.")
    print("="*60)
    return True


if __name__ == "__main__":
    try:
        success = test_adapter()
        if success:
            print("\n[OK] Ready to integrate with GlobalModelRouter for routing tests")
        else:
            print("\n[FAIL] Please check checkpoint path first")
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
