"""
性能基准测试 - Phase 6 云原生

测试项目：
1. API 响应时间
2. 并发处理能力
3. 内存占用
4. CPU 占用
5. 启动时间
"""

import time
import json
import statistics
from typing import Dict, List, Any
import concurrent.futures
import threading

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    from core.config_provider import get_ollama_url
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False


class BenchmarkResult:
    """基准测试结果"""
    
    def __init__(self, name: str):
        self.name = name
        self.values: List[float] = []
        self.unit: str = "ms"
        self.metadata: Dict[str, Any] = {}
    
    def add(self, value: float) -> None:
        """添加测试结果"""
        self.values.append(value)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.values:
            return {}
        
        sorted_values = sorted(self.values)
        return {
            "name": self.name,
            "unit": self.unit,
            "count": len(self.values),
            "min": min(self.values),
            "max": max(self.values),
            "mean": statistics.mean(self.values),
            "median": statistics.median(self.values),
            "std_dev": statistics.stdev(self.values) if len(self.values) > 1 else 0.0,
            "p95": sorted_values[int(len(sorted_values) * 0.95)],
            "p99": sorted_values[int(len(sorted_values) * 0.99)],
        }


class PerformanceBenchmark:
    """性能基准测试器"""
    
    def __init__(self):
        self.results: Dict[str, BenchmarkResult] = {}
        self.system_info: Dict[str, Any] = {}
    
    def collect_system_info(self) -> None:
        """收集系统信息"""
        if HAS_PSUTIL:
            import psutil
            self.system_info = {
                "cpu_count": psutil.cpu_count(logical=False),
                "cpu_count_logical": psutil.cpu_count(logical=True),
                "memory_total": psutil.virtual_memory().total,
                "python_version": self._get_python_version(),
            }
        else:
            self.system_info = {
                "python_version": self._get_python_version(),
            }
    
    def _get_python_version(self) -> str:
        """获取 Python 版本"""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    def benchmark_api_response_time(self, url: str = "http://localhost:8000/health") -> BenchmarkResult:
        """
        测试 API 响应时间
        
        模拟 100 次请求，统计响应时间。
        """
        result = BenchmarkResult("API 响应时间", "ms")
        
        try:
            import requests
        except ImportError:
            print("⚠️ requests 未安装，跳过 API 响应时间测试")
            return result
        
        print(f"测试 API 响应时间：{url} ...")
        
        for i in range(100):
            start = time.time()
            try:
                resp = requests.get(url, timeout=10)
                elapsed = (time.time() - start) * 1000  # 转为毫秒
                if resp.status_code == 200:
                    result.add(elapsed)
            except Exception as e:
                print(f"  请求失败：{e}")
                continue
        
        self.results["api_response_time"] = result
        return result
    
    def benchmark_concurrency(self, url: str = "http://localhost:8000/health") -> BenchmarkResult:
        """
        测试并发处理能力
        
        模拟 50 个并发用户，每个用户 10 个请求。
        """
        result = BenchmarkResult("并发处理能力", "req/s")
        
        try:
            import requests
        except ImportError:
            print("⚠️ requests 未安装，跳过并发测试")
            return result
        
        print("测试并发处理能力...")
        
        def make_requests(url: str, count: int) -> int:
            """发送请求"""
            success = 0
            for _ in range(count):
                try:
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        success += 1
                except Exception:
                    pass
            return success
        
        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_requests, url, 10) for _ in range(50)]
            total_success = sum(f.result() for f in concurrent.futures.as_completed(futures))
        
        elapsed = time.time() - start
        req_per_sec = total_success / elapsed if elapsed > 0 else 0
        
        result.add(req_per_sec)
        self.results["concurrency"] = result
        return result
    
    def benchmark_memory_usage(self, duration: int = 60) -> BenchmarkResult:
        """
        测试内存占用
        
        采样 60 秒，每秒采样一次。
        """
        result = BenchmarkResult("内存占用", "MB")
        
        if not HAS_PSUTIL:
            print("⚠️ psutil 未安装，跳过内存测试")
            return result
        
        print(f"测试内存占用（采样 {duration} 秒）...")
        
        import psutil
        process = psutil.Process()
        
        for _ in range(duration):
            try:
                mem_info = process.memory_info()
                mem_mb = mem_info.rss / 1024 / 1024
                result.add(mem_mb)
                time.sleep(1)
            except Exception as e:
                print(f"  采样失败：{e}")
                continue
        
        self.results["memory_usage"] = result
        return result
    
    def benchmark_cpu_usage(self, duration: int = 10) -> BenchmarkResult:
        """
        测试 CPU 占用
        
        采样 10 秒，每秒采样一次。
        """
        result = BenchmarkResult("CPU 占用", "%")
        
        if not HAS_PSUTIL:
            print("⚠️ psutil 未安装，跳过 CPU 测试")
            return result
        
        print(f"测试 CPU 占用（采样 {duration} 秒）...")
        
        import psutil
        
        for _ in range(duration):
            cpu_percent = psutil.cpu_percent(interval=1)
            result.add(cpu_percent)
        
        self.results["cpu_usage"] = result
        return result
    
    def benchmark_startup_time(self) -> BenchmarkResult:
        """
        测试启动时间
        
        启动应用并测量时间。
        """
        result = BenchmarkResult("启动时间", "s")
        
        print("测试启动时间...")
        
        # 模拟启动（实际应启动真实进程）
        import subprocess
        
        start = time.time()
        try:
            # 这里简化为测量导入时间
            import importlib
            start = time.time()
            importlib.import_module("core")
            elapsed = time.time() - start
            result.add(elapsed)
        except Exception as e:
            print(f"  启动测试失败：{e}")
        
        self.results["startup_time"] = result
        return result
    
    def run_all(self, url: str = "http://localhost:8000") -> Dict[str, BenchmarkResult]:
        """运行所有基准测试"""
        self.collect_system_info()
        
        print("=" * 60)
        print("LivingTreeAI 性能基准测试")
        print("=" * 60)
        
        # API 响应时间
        self.benchmark_api_response_time(f"{url}/health")
        
        # 并发测试
        self.benchmark_concurrency(f"{url}/health")
        
        # 启动时间
        self.benchmark_startup_time()
        
        # 内存和 CPU 测试（需要应用运行）
        if HAS_PSUTIL:
            self.benchmark_memory_usage(duration=10)
            self.benchmark_cpu_usage(duration=5)
        
        return self.results
    
    def generate_report(self) -> str:
        """生成报告"""
        report = []
        report.append("# LivingTreeAI 性能基准测试报告\n")
        report.append(f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 系统信息
        report.append("## 系统信息\n")
        for key, value in self.system_info.items():
            report.append(f"- {key}：{value}\n")
        report.append("\n")
        
        # 测试结果
        report.append("## 测试结果\n")
        report.append("| 指标 | 单位 | 次数 | 最小值 | 最大值 | 平均值 | 中位数 | 标准差 | P95 | P99 |\n")
        report.append("|------|------|------|--------|--------|--------|--------|--------|-----|-----|\n")
        
        for result in self.results.values():
            stats = result.get_stats()
            if not stats:
                continue
            report.append(
                f"| {stats['name']} | {stats['unit']} | "
                f"{stats['count']} | "
                f"{stats['min']:.2f} | "
                f"{stats['max']:.2f} | "
                f"{stats['mean']:.2f} | "
                f"{stats['median']:.2f} | "
                f"{stats['std_dev']:.2f} | "
                f"{stats['p95']:.2f} | "
                f"{stats['p99']:.2f} |\n"
            )
        
        report.append("\n")
        
        # 结论
        report.append("## 结论\n")
        report.append("- 基准测试完成\n")
        
        return "".join(report)
    
    def save_report(self, path: str = "deploy/benchmark/REPORT.md") -> None:
        """保存报告"""
        report = self.generate_report()
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n报告已保存：{path}")


if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    benchmark.run_all()
    benchmark.save_report()
    print(benchmark.generate_report())
