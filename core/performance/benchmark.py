#!/usr/bin/env python3
"""
Performance Benchmark - 性能基准测试
Phase 6 核心：性能测试、延迟测量、吞吐量测试

Author: LivingTreeAI Team
Version: 1.0.0
"""

import gc
import json
import random
import statistics
import string
import sys
import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    name: str
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    std_dev: float
    ops_per_second: float
    memory_before: int = 0
    memory_after: int = 0
    memory_delta: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time": f"{self.total_time:.4f}s",
            "avg_time": f"{self.avg_time:.4f}ms",
            "min_time": f"{self.min_time:.4f}ms",
            "max_time": f"{self.max_time:.4f}ms",
            "std_dev": f"{self.std_dev:.4f}ms",
            "ops_per_second": f"{self.ops_per_second:.2f}",
            "memory_delta": f"{self.memory_delta / 1024 / 1024:.2f}MB",
        }


@dataclass
class LatencyResult:
    """延迟测试结果"""
    percentile_50: float  # P50
    percentile_95: float  # P95
    percentile_99: float  # P99
    percentile_999: float  # P999
    mean: float
    median: float
    std_dev: float
    samples: int


@dataclass
class ThroughputResult:
    """吞吐量测试结果"""
    duration: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_per_second: float
    avg_latency: float
    max_latency: float
    min_latency: float


class MemoryProfiler:
    """内存分析器"""
    
    @staticmethod
    def get_memory_usage() -> int:
        """获取当前内存使用 (bytes)"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss
        except ImportError:
            # 备用方案
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    
    @staticmethod
    def enable():
        """启用内存追踪"""
        gc.enable()
    
    @staticmethod
    def get_delta() -> int:
        """获取内存变化"""
        gc.collect()
        return MemoryProfiler.get_memory_usage()


class BenchmarkRunner:
    """
    基准测试运行器
    
    核心功能：
    - 性能基准测试
    - 延迟分布测试
    - 吞吐量测试
    - 并发测试
    - 内存分析
    """
    
    def __init__(self, warmup_iterations: int = 10, iterations: int = 100):
        """
        初始化运行器
        
        Args:
            warmup_iterations: 预热迭代次数
            iterations: 测试迭代次数
        """
        self._warmup = warmup_iterations
        self._iterations = iterations
        self._results: List[BenchmarkResult] = []
    
    def run(
        self,
        name: str,
        func: Callable,
        *args,
        **kwargs
    ) -> BenchmarkResult:
        """
        运行基准测试
        
        Args:
            name: 测试名称
            func: 测试函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            测试结果
        """
        # 预热
        for _ in range(self._warmup):
            func(*args, **kwargs)
        
        # 强制垃圾回收
        gc.collect()
        
        # 记录初始内存
        memory_before = MemoryProfiler.get_delta()
        
        # 运行测试
        times = []
        for _ in range(self._iterations):
            start = time.perf_counter()
            func(*args, **kwargs)
            end = time.perf_counter()
            times.append((end - start) * 1000)  # 转换为毫秒
        
        # 记录最终内存
        gc.collect()
        memory_after = MemoryProfiler.get_delta()
        
        # 计算统计
        total_time = sum(times)
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        
        result = BenchmarkResult(
            name=name,
            iterations=self._iterations,
            total_time=total_time,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            std_dev=std_dev,
            ops_per_second=1000 / avg_time if avg_time > 0 else 0,
            memory_before=memory_before,
            memory_after=memory_after,
            memory_delta=memory_after - memory_before,
        )
        
        self._results.append(result)
        return result
    
    def get_results(self) -> List[BenchmarkResult]:
        """获取所有结果"""
        return self._results
    
    def print_results(self) -> None:
        """打印结果"""
        print("\n" + "="*70)
        print("Benchmark Results")
        print("="*70)
        
        for result in self._results:
            print(f"\n📊 {result.name}")
            print(f"   迭代次数: {result.iterations}")
            print(f"   总耗时: {result.total_time:.4f}s")
            print(f"   平均延迟: {result.avg_time:.4f}ms")
            print(f"   最小延迟: {result.min_time:.4f}ms")
            print(f"   最大延迟: {result.max_time:.4f}ms")
            print(f"   标准差: {result.std_dev:.4f}ms")
            print(f"   吞吐量: {result.ops_per_second:.2f} ops/s")
            if result.memory_delta != 0:
                print(f"   内存变化: {result.memory_delta / 1024 / 1024:.2f}MB")


class LatencyTester:
    """延迟测试器"""
    
    @staticmethod
    def measure_latency(
        func: Callable,
        iterations: int = 1000,
        warmup: int = 100
    ) -> LatencyResult:
        """
        测量延迟分布
        
        Args:
            func: 测试函数
            iterations: 迭代次数
            warmup: 预热次数
            
        Returns:
            延迟结果
        """
        # 预热
        for _ in range(warmup):
            func()
        
        # 测试
        latencies = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # ms
        
        # 计算百分位数
        latencies.sort()
        n = len(latencies)
        
        def percentile(data: List[float], p: float) -> float:
            k = (len(data) - 1) * p
            f = int(k)
            c = f + 1 if f < len(data) - 1 else f
            return data[f] + (k - f) * (data[c] - data[f])
        
        return LatencyResult(
            percentile_50=percentile(latencies, 0.50),
            percentile_95=percentile(latencies, 0.95),
            percentile_99=percentile(latencies, 0.99),
            percentile_999=percentile(latencies, 0.999),
            mean=statistics.mean(latencies),
            median=statistics.median(latencies),
            std_dev=statistics.stdev(latencies) if len(latencies) > 1 else 0,
            samples=iterations,
        )
    
    @staticmethod
    def print_latency_result(result: LatencyResult) -> None:
        """打印延迟结果"""
        print("\n" + "="*70)
        print("Latency Distribution")
        print("="*70)
        print(f"样本数: {result.samples}")
        print(f"平均值: {result.mean:.4f}ms")
        print(f"中位数: {result.median:.4f}ms")
        print(f"标准差: {result.std_dev:.4f}ms")
        print(f"P50: {result.percentile_50:.4f}ms")
        print(f"P95: {result.percentile_95:.4f}ms")
        print(f"P99: {result.percentile_99:.4f}ms")
        print(f"P999: {result.percentile_999:.4f}ms")


class ThroughputTester:
    """吞吐量测试器"""
    
    @staticmethod
    def measure_throughput(
        func: Callable,
        duration: float = 10.0,
        workers: int = 4
    ) -> ThroughputResult:
        """
        测量吞吐量
        
        Args:
            func: 测试函数
            duration: 测试时长 (秒)
            workers: 并发工作线程数
            
        Returns:
            吞吐量结果
        """
        results: Dict[str, List[float]] = defaultdict(list)
        successful = 0
        failed = 0
        lock = threading.Lock()
        start_time = time.time()
        
        def worker():
            nonlocal successful, failed
            while time.time() - start_time < duration:
                try:
                    work_start = time.perf_counter()
                    func()
                    work_end = time.perf_counter()
                    latency = (work_end - work_start) * 1000
                    
                    with lock:
                        successful += 1
                        results["latencies"].append(latency)
                except Exception:
                    with lock:
                        failed += 1
        
        # 启动工作线程
        threads = []
        for _ in range(workers):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)
        
        # 等待完成
        for t in threads:
            t.join()
        
        elapsed = time.time() - start_time
        latencies = results.get("latencies", [])
        
        return ThroughputResult(
            duration=elapsed,
            total_requests=successful + failed,
            successful_requests=successful,
            failed_requests=failed,
            requests_per_second=successful / elapsed if elapsed > 0 else 0,
            avg_latency=statistics.mean(latencies) if latencies else 0,
            max_latency=max(latencies) if latencies else 0,
            min_latency=min(latencies) if latencies else 0,
        )
    
    @staticmethod
    def print_throughput_result(result: ThroughputResult) -> None:
        """打印吞吐量结果"""
        print("\n" + "="*70)
        print("Throughput Test")
        print("="*70)
        print(f"测试时长: {result.duration:.2f}s")
        print(f"总请求数: {result.total_requests}")
        print(f"成功请求: {result.successful_requests}")
        print(f"失败请求: {result.failed_requests}")
        print(f"吞吐量: {result.requests_per_second:.2f} req/s")
        print(f"平均延迟: {result.avg_latency:.4f}ms")
        print(f"最小延迟: {result.min_latency:.4f}ms")
        print(f"最大延迟: {result.max_latency:.4f}ms")


# 预定义的基准测试
class StandardBenchmarks:
    """标准基准测试"""
    
    @staticmethod
    def json_serialization(data_size: int = 100) -> Callable:
        """JSON 序列化基准"""
        data = {"key": "value", "number": 42, "list": list(range(10))}
        
        def benchmark():
            json.dumps(data)
        
        return benchmark
    
    @staticmethod
    def json_deserialization(iterations: int = 100) -> Callable:
        """JSON 反序列化基准"""
        json_str = json.dumps({"key": "value", "number": 42, "list": list(range(10))})
        
        def benchmark():
            json.loads(json_str)
        
        return benchmark
    
    @staticmethod
    def dict_operations(size: int = 1000) -> Callable:
        """字典操作基准"""
        d = {i: i * 2 for i in range(size)}
        
        def benchmark():
            for i in range(size):
                _ = d.get(i)
            d["new_key"] = "value"
            del d["new_key"]
        
        return benchmark
    
    @staticmethod
    def list_operations(size: int = 1000) -> Callable:
        """列表操作基准"""
        lst = list(range(size))
        
        def benchmark():
            lst.append(size)
            lst.pop()
            _ = lst[500]
            _ = lst[-1]
        
        return benchmark
    
    @staticmethod
    def string_concatenation(size: int = 1000) -> Callable:
        """字符串拼接基准"""
        parts = ["part" + str(i) for i in range(size)]
        
        def benchmark():
            _ = "".join(parts)
        
        return benchmark


def run_all_benchmarks():
    """运行所有标准基准测试"""
    runner = BenchmarkRunner(warmup_iterations=10, iterations=100)
    
    print("Running LivingTreeAI Performance Benchmarks...")
    print("="*70)
    
    # JSON 操作
    runner.run("JSON Serialization", StandardBenchmarks.json_serialization())
    runner.run("JSON Deserialization", StandardBenchmarks.json_deserialization())
    
    # 数据结构操作
    runner.run("Dict Operations", StandardBenchmarks.dict_operations())
    runner.run("List Operations", StandardBenchmarks.list_operations())
    runner.run("String Concatenation", StandardBenchmarks.string_concatenation())
    
    # 打印结果
    runner.print_results()
    
    # 返回结果
    return runner.get_results()


if __name__ == "__main__":
    results = run_all_benchmarks()
    
    # 可选：导出 JSON
    if "--export" in sys.argv:
        export_data = [r.to_dict() for r in results]
        with open("benchmark_results.json", "w") as f:
            json.dump(export_data, f, indent=2)
        print("\nResults exported to benchmark_results.json")
