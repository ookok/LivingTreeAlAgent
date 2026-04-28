"""
llmfit 独立测试

完全独立测试 llmfit 核心功能，不依赖项目其他模块
"""

import platform
import os
import time


# ============ 复制 llmfit 核心组件 ============

class HardwareBackend:
    OLLAMA = "ollama"
    LLAMA_CPP = "llama.cpp"
    VLLM = "vLLM"
    UNKNOWN = "unknown"


class HardwareSpec:
    def __init__(self):
        self.cpu_cores = 0
        self.cpu_model = ""
        self.ram_gb = 0.0
        self.ram_available_gb = 0.0
        self.gpu_name = ""
        self.gpu_memory_gb = 0.0
        self.gpu_count = 0
        self.gpu_vendor = ""
        self.backend = HardwareBackend.UNKNOWN
        self.os_name = ""
        self.os_version = ""
        self.python_version = ""
        self.is_apple_silicon = False


class HardwareDetector:
    def detect_cpu(self):
        cpu_count = os.cpu_count() or 0
        cpu_model = platform.processor() or "Unknown"
        return {"cores": cpu_count, "model": cpu_model}
    
    def detect_memory(self):
        try:
            import psutil
            vm = psutil.virtual_memory()
            return {
                "total_gb": vm.total / (1024**3),
                "available_gb": vm.available / (1024**3),
            }
        except:
            return {"total_gb": 0, "available_gb": 0}
    
    def detect_os(self):
        return {
            "name": platform.system(),
            "version": platform.version(),
        }
    
    def detect_gpu(self):
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                gpus = []
                for line in lines:
                    parts = line.split(",")
                    if len(parts) >= 2:
                        gpus.append({
                            "name": parts[0].strip(),
                            "memory_mb": float(parts[1].strip().replace("MiB", "")),
                        })
                return {"gpus": gpus, "count": len(gpus)} if gpus else {"gpus": [], "count": 0}
        except:
            pass
        return {"gpus": [], "count": 0}
    
    def detect(self):
        spec = HardwareSpec()
        cpu = self.detect_cpu()
        memory = self.detect_memory()
        os_info = self.detect_os()
        gpu_info = self.detect_gpu()
        
        spec.cpu_cores = cpu.get("cores", 0)
        spec.cpu_model = cpu.get("model", "")
        spec.ram_gb = memory.get("total_gb", 0)
        spec.ram_available_gb = memory.get("available_gb", 0)
        spec.os_name = os_info.get("name", "")
        spec.os_version = os_info.get("version", "")
        spec.python_version = platform.python_version()
        
        if gpu_info.get("count", 0) > 0:
            gpus = gpu_info.get("gpus", [])
            if gpus:
                spec.gpu_name = gpus[0].get("name", "")
                spec.gpu_memory_gb = gpus[0].get("memory_mb", 0) / 1024
                spec.gpu_count = gpu_info.get("count", 0)
                spec.gpu_vendor = "NVIDIA"
        
        spec.is_apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"
        
        return spec


class ModelInfo:
    def __init__(self, name, provider, params, context_length, quantization="fp16", base_score=0.5, use_cases=None):
        self.name = name
        self.provider = provider
        self.params = params
        self.context_length = context_length
        self.quantization = quantization
        self.base_score = base_score
        self.use_cases = use_cases or []


class ModelScore:
    def __init__(self):
        self.quality = 0.0
        self.speed = 0.0
        self.fit = 0.0
        self.context = 0.0
        self.composite = 0.0
    
    def calculate_composite(self, weights=None):
        if weights is None:
            weights = {"quality": 0.3, "speed": 0.2, "fit": 0.3, "context": 0.2}
        self.composite = (
            self.quality * weights.get("quality", 0.3) +
            self.speed * weights.get("speed", 0.2) +
            self.fit * weights.get("fit", 0.3) +
            self.context * weights.get("context", 0.2)
        )
        return self.composite


class ModelScorer:
    def __init__(self):
        self.hardware_spec = None
    
    def set_hardware(self, hardware_spec):
        self.hardware_spec = hardware_spec
    
    def score(self, model, hardware_spec=None):
        if hardware_spec is None:
            hardware_spec = self.hardware_spec
        
        score = ModelScore()
        
        # Quality score
        if model.params <= 7:
            base_quality = 0.6
        elif model.params <= 13:
            base_quality = 0.7
        elif model.params <= 30:
            base_quality = 0.8
        else:
            base_quality = 0.85
        score.quality = base_quality * model.base_score
        
        # Speed score (estimated)
        base_speed = 50.0 / (model.params ** 0.5)
        if hardware_spec and hardware_spec.gpu_count > 0:
            speed = base_speed * 5
        else:
            speed = base_speed * 2
        score.speed = min(1.0, speed / 50.0)
        
        # Fit score
        quant_mult = {"fp16": 2.0, "int8": 1.0, "int4": 0.5}
        bytes_per_param = quant_mult.get(model.quantization.lower(), 2.0)
        model_memory_gb = model.params * bytes_per_param
        
        if hardware_spec:
            if hardware_spec.gpu_count > 0:
                if model_memory_gb <= hardware_spec.gpu_memory_gb:
                    score.fit = 1.0
                elif model_memory_gb <= hardware_spec.ram_gb:
                    score.fit = 0.6
                else:
                    score.fit = 0.3
            else:
                if model_memory_gb <= hardware_spec.ram_gb * 0.5:
                    score.fit = 0.5
                else:
                    score.fit = 0.2
        else:
            score.fit = 0.5
        
        # Context score
        score.context = min(1.0, model.context_length / 32768)
        
        score.calculate_composite()
        return score


class ModelDatabase:
    def __init__(self):
        self.models = []
        self._init_default_models()
    
    def _init_default_models(self):
        self.models = [
            ModelInfo("llama-3.2-1b", "Meta", 1.0, 128000, "bf16", 0.75, ["general"]),
            ModelInfo("llama-3.2-3b", "Meta", 3.0, 128000, "bf16", 0.80, ["general", "coding"]),
            ModelInfo("llama-3.1-8b", "Meta", 8.0, 128000, "fp16", 0.85, ["general", "coding", "reasoning"]),
            ModelInfo("llama-3.1-70b", "Meta", 70.0, 128000, "fp8", 0.92, ["general", "coding", "reasoning"]),
            ModelInfo("qwen-2.5-7b", "Alibaba", 7.0, 32768, "fp16", 0.83, ["general", "coding"]),
            ModelInfo("qwen-2.5-14b", "Alibaba", 14.0, 32768, "fp16", 0.87, ["general", "coding", "reasoning"]),
            ModelInfo("qwen-2.5-72b", "Alibaba", 72.0, 32768, "fp8", 0.91, ["general", "reasoning"]),
            ModelInfo("phi-3.5-mini-3.8b", "Microsoft", 3.8, 4096, "fp16", 0.78, ["general", "coding"]),
            ModelInfo("phi-3.5-small-7b", "Microsoft", 7.0, 8192, "fp16", 0.82, ["general", "coding"]),
            ModelInfo("deepseek-coder-6.7b", "DeepSeek", 6.7, 16384, "fp16", 0.84, ["coding", "general"]),
            ModelInfo("deepseek-coder-33b", "DeepSeek", 33.0, 16384, "fp8", 0.90, ["coding", "reasoning"]),
            ModelInfo("gemma-2-2b", "Google", 2.0, 8192, "fp16", 0.76, ["general"]),
            ModelInfo("gemma-2-9b", "Google", 9.0, 8192, "fp16", 0.84, ["general", "coding"]),
            ModelInfo("gemma-2-27b", "Google", 27.0, 8192, "fp16", 0.88, ["general", "reasoning"]),
        ]
    
    def filter_runnable(self, hardware_spec):
        runnable = []
        for model in self.models:
            quant_mult = {"fp16": 2.0, "int8": 1.0, "int4": 0.5, "bf16": 2.0, "fp8": 1.5}
            bytes_per_param = quant_mult.get(model.quantization.lower(), 2.0)
            model_memory_gb = model.params * bytes_per_param
            
            if hardware_spec.gpu_count > 0:
                if model_memory_gb <= hardware_spec.gpu_memory_gb * 1.2:
                    runnable.append(model)
                elif model_memory_gb <= hardware_spec.ram_gb * 0.9:
                    runnable.append(model)
            else:
                if model_memory_gb <= hardware_spec.ram_gb * 0.6:
                    runnable.append(model)
        return runnable
    
    def list_all(self):
        return self.models


class UseCase:
    GENERAL = "general"
    CODING = "coding"
    REASONING = "reasoning"


class ModelRecommender:
    def __init__(self):
        self.hardware_detector = HardwareDetector()
        self.model_scorer = ModelScorer()
        self.model_database = ModelDatabase()
    
    def detect_hardware(self):
        return self.hardware_detector.detect()
    
    def recommend(self, hardware_spec=None, use_case=UseCase.GENERAL, top_k=5, min_fit=0.3):
        if hardware_spec is None:
            hardware_spec = self.hardware_detector.detect()
        
        self.model_scorer.set_hardware(hardware_spec)
        
        candidates = self.model_database.filter_runnable(hardware_spec)
        
        if use_case != UseCase.GENERAL:
            candidates = [m for m in candidates if use_case in m.use_cases]
        
        recommendations = []
        for model in candidates:
            score = self.model_scorer.score(model, hardware_spec)
            
            if score.fit >= min_fit:
                recommendations.append({
                    "model": model,
                    "score": score,
                    "fit_level": "perfect" if score.fit >= 0.8 else "good" if score.fit >= 0.6 else "marginal",
                })
            
            if len(recommendations) >= top_k:
                break
        
        recommendations.sort(key=lambda x: x["score"].composite, reverse=True)
        
        return {
            "hardware": hardware_spec,
            "use_case": use_case,
            "recommendations": recommendations,
            "total_models_scored": len(candidates),
        }


# ============ 测试函数 ============

def test_hardware_detector():
    print("=== Test Hardware Detector ===")
    
    detector = HardwareDetector()
    spec = detector.detect()
    
    print(f"CPU: {spec.cpu_model} ({spec.cpu_cores} cores)")
    print(f"RAM: {spec.ram_gb:.1f} GB ({spec.ram_available_gb:.1f} GB available)")
    print(f"GPU: {spec.gpu_count} x {spec.gpu_name} ({spec.gpu_memory_gb:.1f} GB VRAM)")
    print(f"Backend: {spec.backend}")
    print(f"OS: {spec.os_name} {spec.os_version}")
    print(f"Python: {spec.python_version}")
    print(f"Apple Silicon: {spec.is_apple_silicon}")
    
    print("\nHardware detection test completed!")


def test_model_scorer():
    print("\n=== Test Model Scorer ===")
    
    detector = HardwareDetector()
    hardware = detector.detect()
    
    scorer = ModelScorer()
    scorer.set_hardware(hardware)
    
    models = [
        ModelInfo("llama-3.2-1b", "Meta", 1.0, 128000, "bf16", 0.75),
        ModelInfo("llama-3.1-8b", "Meta", 8.0, 128000, "fp16", 0.85),
        ModelInfo("qwen-2.5-7b", "Alibaba", 7.0, 32768, "fp16", 0.83),
    ]
    
    print(f"Scoring {len(models)} models...\n")
    
    for model in models:
        score = scorer.score(model, hardware)
        print(f"Model: {model.name}")
        print(f"  Params: {model.params}B | Quantization: {model.quantization}")
        print(f"  Quality: {score.quality:.3f}")
        print(f"  Speed: {score.speed:.3f}")
        print(f"  Fit: {score.fit:.3f}")
        print(f"  Context: {score.context:.3f}")
        print(f"  Composite: {score.composite:.3f}")
        print()
    
    print("Model scorer test completed!")


def test_model_recommender():
    print("\n=== Test Model Recommender ===")
    
    recommender = ModelRecommender()
    hardware = recommender.detect_hardware()
    
    print(f"Hardware: {hardware.cpu_model}")
    print(f"RAM: {hardware.ram_gb:.1f} GB")
    print(f"GPU: {hardware.gpu_count} x {hardware.gpu_name}")
    print()
    
    # General recommendations
    print("--- General Use Case ---")
    result = recommender.recommend(hardware_spec=hardware, use_case=UseCase.GENERAL, top_k=5)
    
    print(f"Evaluated {result['total_models_scored']} models")
    print(f"Recommended {len(result['recommendations'])}:\n")
    
    for i, rec in enumerate(result['recommendations'], 1):
        model = rec['model']
        score = rec['score']
        print(f"{i}. {model.name} ({model.provider})")
        print(f"   Params: {model.params}B | Quant: {model.quantization}")
        print(f"   Fit Level: {rec['fit_level']}")
        print(f"   Composite Score: {score.composite:.3f}")
        print(f"   Quality: {score.quality:.3f} | Speed: {score.speed:.3f} | Fit: {score.fit:.3f} | Context: {score.context:.3f}")
        print()
    
    # Coding recommendations
    print("--- Coding Use Case ---")
    coding_result = recommender.recommend(hardware_spec=hardware, use_case=UseCase.CODING, top_k=3)
    
    print(f"Recommended {len(coding_result['recommendations'])}:\n")
    
    for i, rec in enumerate(coding_result['recommendations'], 1):
        model = rec['model']
        score = rec['score']
        print(f"{i}. {model.name} ({model.provider})")
        print(f"   Composite Score: {score.composite:.3f}")
        print()
    
    print("Model recommender test completed!")


def test_model_database():
    print("\n=== Test Model Database ===")
    
    db = ModelDatabase()
    print(f"Model database has {len(db.list_all())} models\n")
    
    detector = HardwareDetector()
    hardware = detector.detect()
    
    runnable_models = db.filter_runnable(hardware)
    print(f"Runnable models on current hardware: {len(runnable_models)}")
    
    for m in runnable_models[:5]:
        print(f"  - {m.name} ({m.params}B)")
    
    print("\nModel database test completed!")


if __name__ == "__main__":
    print("=" * 60)
    print("llmfit Standalone Test")
    print("=" * 60)
    
    try:
        test_hardware_detector()
        test_model_scorer()
        test_model_recommender()
        test_model_database()
        
        print("\n" + "=" * 60)
        print("All tests passed!")
        print("=" * 60)
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nTest completed")
