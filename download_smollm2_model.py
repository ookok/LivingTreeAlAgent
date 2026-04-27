#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载 SmolLM2 模型
"""

import os
from pathlib import Path
from core.smolllm2.downloader import HuggingFaceDownloader


def download_smollm2_model():
    """下载 SmolLM2 模型"""
    print("🚀 开始下载 SmolLM2 模型")
    print("=" * 60)
    
    # 设置缓存目录
    cache_dir = Path.home() / ".hermes-desktop" / "models"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"缓存目录: {cache_dir}")
    
    try:
        # 创建下载器
        downloader = HuggingFaceDownloader(cache_dir=cache_dir)
        
        # 下载 SmolLM2 模型
        model_id = "second-state/SmolLM2-135M-Instruct-GGUF"
        gguf_filename = "smollm2-135m-instruct-q4_k_m.gguf"
        
        print(f"开始下载模型: {model_id}")
        print(f"目标文件: {gguf_filename}")
        
        # 下载模型
        model_path = downloader.download_model(
            model_id=model_id,
            gguf_filename=gguf_filename
        )
        
        if model_path:
            print(f"✅ 模型下载成功: {model_path}")
        else:
            print("❌ 模型下载失败")
            
    except Exception as e:
        print(f"❌ 下载过程中出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)
    print("📋 下载完成")


if __name__ == "__main__":
    download_smollm2_model()
