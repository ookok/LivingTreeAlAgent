@echo off
cd /d "%~dp0"

set "OLLAMA_HOST=0.0.0.0:11434"
set "OLLAMA_CONTEXT_LENGTH=16384"
set "OLLAMA_KEEP_ALIVE=30m"
set "OLLAMA_MAX_LOADED_MODELS=3"
set "OLLAMA_FLASH_ATTENTION=1"

echo Starting Ollama Server...
start /MIN "" ollama serve

timeout /t 3 /nobreak >nul

echo Checking Ollama Server status...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ollama Server failed to start. Please check if Ollama is installed.
    pause
    exit /b 1
)

echo Ollama Server started successfully!
echo.
echo Available models:
curl -s http://localhost:11434/api/tags | python -c "
import sys, json
data = json.load(sys.stdin)
for m in data['models']:
    name = m['name']
    params = m['details'].get('parameter_size', 'N/A')
    quant = m['details'].get('quantization_level', 'N/A')
    size_gb = m['size'] / (1024 * 1024 * 1024)
    print(f'  - {name} ({params}, {quant}, {size_gb:.2f} GB)')
"
echo.

set PYTHON_CMD=
if exist ".venv\Scripts\python.exe" (
    set PYTHON_CMD=.venv\Scripts\python.exe
) else (
    where python >nul 2>&1 && set PYTHON_CMD=python
)

if "%PYTHON_CMD%"=="" (
    echo ERROR: Python not found
    pause
    exit /b 1
)

echo Starting LivingTree AI Agent...
echo Web UI: http://localhost:8100
echo API Docs: http://localhost:8100/docs
echo Ollama API: http://localhost:11434/v1
echo.

set "LT_FLASH_MODEL=qwen3.5:0.8b"
set "LT_PRO_MODEL=qwen3.5:9b"
set "LT_FALLBACK_MODEL=qwen2.5:1.5b"

"%PYTHON_CMD%" -m livingtree

pause
