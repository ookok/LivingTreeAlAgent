
# Ollama Deployment Guide

## Installation

### Linux/macOS
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows
Download from https://ollama.com/download

### Docker
```bash
docker run -d -v ollama:/root/.ollama -p 11434:11434 ollama/ollama
```

## Usage

### Basic Commands
- `ollama run llama2` - Run a model
- `ollama list` - List installed models
- `ollama pull <model>` - Download a model
- `ollama show <model>` - Show model info

### API Usage
POST http://localhost:11434/api/generate
```json
{
  "model": "llama2",
  "prompt": "Hello!",
  "stream": false
}
```

## GPU Support

Ollama supports NVIDIA GPU acceleration. Ensure CUDA is installed:
```bash
nvidia-smi
```

## Environment Variables

- OLLAMA_HOST - Listen address
- OLLAMA_MODELS - Model storage path
- OLLAMA_NUM_PARALLEL - Parallel requests
    