#!/usr/bin/env python
"""
LivingTree AI Agent - Ollama Server Launcher

This script:
1. Configures and starts Ollama server with optimal settings for the hardware
2. Detects available models from Ollama
3. Launches LivingTree AI Agent with Ollama models configured
"""

import os
import sys
import time
import json
import subprocess
import threading
from pathlib import Path

def check_ollama_installed():
    """Check if Ollama is installed."""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def check_ollama_server(host="localhost", port=11434):
    """Check if Ollama server is running."""
    try:
        import urllib.request
        url = f"http://{host}:{port}/api/tags"
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False

def get_ollama_models(host="localhost", port=11434):
    """Get list of available models from Ollama."""
    try:
        import urllib.request
        url = f"http://{host}:{port}/api/tags"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("models", [])
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []

def start_ollama_server():
    """Start Ollama server as a background process."""
    env = os.environ.copy()
    env["OLLAMA_HOST"] = "0.0.0.0:11434"
    env["OLLAMA_CONTEXT_LENGTH"] = "16384"
    env["OLLAMA_KEEP_ALIVE"] = "30m"
    env["OLLAMA_MAX_LOADED_MODELS"] = "3"
    env["OLLAMA_FLASH_ATTENTION"] = "1"
    
    print("Starting Ollama server...")
    try:
        process = subprocess.Popen(
            ["ollama", "serve"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        return process
    except Exception as e:
        print(f"Failed to start Ollama server: {e}")
        return None

def launch_livingtree():
    """Launch LivingTree AI Agent."""
    os.environ["LT_FLASH_MODEL"] = "qwen3.5:0.8b"
    os.environ["LT_PRO_MODEL"] = "qwen3.5:9b"
    os.environ["LT_FALLBACK_MODEL"] = "qwen2.5:1.5b"
    
    python_cmd = sys.executable
    print(f"\nStarting LivingTree AI Agent with {python_cmd}")
    print("Web UI: http://localhost:8100")
    print("API Docs: http://localhost:8100/docs")
    print("Ollama API: http://localhost:11434/v1")
    print()
    
    subprocess.run([python_cmd, "-m", "livingtree"], check=True)

def main():
    print("="*60)
    print("LivingTree AI Agent - Ollama Server Launcher")
    print("="*60)
    print()
    
    if not check_ollama_installed():
        print("ERROR: Ollama is not installed.")
        print("Please install Ollama from https://ollama.com/download")
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    if not check_ollama_server():
        print("Ollama server not running, starting...")
        process = start_ollama_server()
        if not process:
            print("ERROR: Failed to start Ollama server")
            input("\nPress Enter to exit...")
            sys.exit(1)
        
        print("Waiting for Ollama server to start...")
        for _ in range(10):
            if check_ollama_server():
                break
            time.sleep(1)
        else:
            print("ERROR: Ollama server failed to start")
            input("\nPress Enter to exit...")
            sys.exit(1)
    
    print("Ollama server is running!")
    print()
    
    models = get_ollama_models()
    if models:
        print("Available Ollama models:")
        for model in models:
            name = model["name"]
            params = model["details"].get("parameter_size", "N/A")
            quant = model["details"].get("quantization_level", "N/A")
            size_gb = model["size"] / (1024 * 1024 * 1024)
            print(f"  - {name} ({params}, {quant}, {size_gb:.2f} GB)")
    else:
        print("No models found. Please pull models using 'ollama pull <model>'")
        print("Recommended models:")
        print("  - ollama pull qwen3.5:0.8b")
        print("  - ollama pull qwen3.5:4b")
        print("  - ollama pull qwen3.5:9b")
    
    print()
    print("Configuration summary:")
    print(f"  Flash model: qwen3.5:0.8b")
    print(f"  Pro model: qwen3.5:9b")
    print(f"  Fallback model: qwen2.5:1.5b")
    print()
    
    try:
        launch_livingtree()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except subprocess.CalledProcessError as e:
        print(f"LivingTree Agent exited with error: {e}")
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
