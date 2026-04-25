#!/usr/bin/env python3
"""
进化引擎 Demo 脚本
展示 NSGA-II 多目标优化和自适应进化的效果
Author: LivingTreeAI Team
"""

import numpy as np
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from evolution.nsga2_engine import NSGA2Engine, Individual
from evolution.adaptive_evolution import AdaptiveEvolutionEngine, EvolutionState


def demo_nsga2():
    """演示 NSGA-II 多目标优化"""
    print("=" * 60)
    print("NSGA-II 多目标进化优化 Demo")
    print("=" * 60)

    # ZDT1 测试函数
    def zdt1(genes: np.ndarray) -> List[float]:
        f1 = genes[0]
        g = 1 + 9 * np.sum(genes[1:]) / (len(genes) - 1)
        h = 1 - np.sqrt(f1 / g)
        f2 = g * h
        return [f1, f2]

    # 创建引擎
    engine = NSGA2Engine(
        population_size=50,
        n_objectives=2,
        gene_dim=5,
        gene_min=0.0,
        gene_max=1.0,
    )
    engine.set_objectives_function(zdt1)

    print("\n初始化种群...")
    engine.initialize_population()

    print("\n开始进化 (50 代)...")
    start_time = time.time()
    pareto, history = engine.run(max_generations=50)
    elapsed = time.time() - start_time

    print(f"\n完成！用时: {elapsed:.2f} 秒")
    print(f"Pareto 前沿大小: {len(pareto)}")
    print(f"历史记录条数: {len(history)}")

    # 显示 Pareto 前沿
    print("\nPareto 前沿 (前 10 个):")
    print("-" * 40)
    for i, ind in enumerate(pareto[:10]):
        print(f"{i+1}. f1={ind.objectives[0]:.4f}, f2={ind.objectives[1]:.4f}")

    # 计算超体积
    ref_point = [1.1, 1.1]
    hv = engine.get_hypervolume(ref_point)
    print(f"\n超体积 (HV): {hv:.4f}")

    return pareto, history


def demo_adaptive_evolution():
    """演示自适应进化"""
    print("\n" + "=" * 60)
    print("自适应进化引擎 Demo")
    print("=" * 60)

    # Sphere 函数（单目标）
    def sphere(x: np.ndarray) -> float:
        return -np.sum(x ** 2)  # 最大化（取负）

    # 创建引擎
    engine = AdaptiveEvolutionEngine(
        base_population_size=50,
        base_mutation_rate=0.1,
        base_crossover_rate=0.7,
        adaptation_interval=5,
    )
    engine.set_fitness_function(sphere)
    engine.initialize_population(dim=5)

    print("\n开始自适应进化 (30 代)...")
    start_time = time.time()

    for gen in range(30):
        state = engine.evolve_generation()

        if gen % 5 == 0:
            print(f"Gen {gen}: best={state.best_fitness:.4f}, "
                  f"diversity={state.diversity:.4f}, "
                  f"mutation_rate={engine.current_mutation_rate:.3f}")

    elapsed = time.time() - start_time
    print(f"\n完成！用时: {elapsed:.2f} 秒")

    # 显示最终结果
    best_ind, best_fit = engine.get_best_individual()
    print(f"\n最佳个体适应度: {best_fit:.6f}")
    print(f"最终变异率: {engine.current_mutation_rate:.3f}")
    print(f"最终交叉率: {engine.current_crossover_rate:.3f}")

    # 显示参数调整历史
    print("\n参数调整历史:")
    print("-" * 60)
    for record in engine.parameter_history[:5]:
        print(f"Gen {record['generation']}: "
              f"mutation={record['mutation_rate']:.3f}, "
              f"crossover={record['crossover_rate']:.3f}")

    return engine


def demo_comparison():
    """对比实验：固定参数 vs 自适应参数"""
    print("\n" + "=" * 60)
    print("对比实验: 固定参数 vs 自适应参数")
    print("=" * 60)

    def rastrigin(x: np.ndarray) -> float:
        """Rastrigin 函数（多峰，难优化）"""
        A = 10
        n = len(x)
        return -(A * n + np.sum(x ** 2 - A * np.cos(2 * np.pi * x)))  # 取负（最大化）

    # 实验设置
    n_runs = 3
    n_gen = 30

    print(f"\n运行 {n_runs} 次，每次 {n_gen} 代...")

    # 固定参数
    fixed_results = []
    for run in range(n_runs):
        engine = AdaptiveEvolutionEngine(
            base_population_size=50,
            base_mutation_rate=0.1,
            base_crossover_rate=0.7,
            adaptation_interval=100,  # 不调整（固定）
        )
        engine.set_fitness_function(rastrigin)
        engine.initialize_population(dim=5)

        for _ in range(n_gen):
            engine.evolve_generation()

        best_fit = max(engine.fitnesses)
        fixed_results.append(best_fit)
        print(f"  固定参数 Run {run+1}: best={best_fit:.4f}")

    # 自适应参数
    adaptive_results = []
    for run in range(n_runs):
        engine = AdaptiveEvolutionEngine(
            base_population_size=50,
            base_mutation_rate=0.1,
            base_crossover_rate=0.7,
            adaptation_interval=5,  # 每 5 代调整
        )
        engine.set_fitness_function(rastrigin)
        engine.initialize_population(dim=5)

        for _ in range(n_gen):
            engine.evolve_generation()

        best_fit = max(engine.fitnesses)
        adaptive_results.append(best_fit)
        print(f"  自适应 Run {run+1}: best={best_fit:.4f}")

    # 统计
    fixed_mean = np.mean(fixed_results)
    adaptive_mean = np.mean(adaptive_results)

    print("\n结果对比:")
    print("-" * 40)
    print(f"固定参数平均: {fixed_mean:.4f}")
    print(f"自适应参数平均: {adaptive_mean:.4f}")
    print(f"提升: {(adaptive_mean - fixed_mean) / abs(fixed_mean) * 100:.2f}%")

    return fixed_results, adaptive_results


def main():
    """主函数"""
    print("\n" + "#" * 60)
    print("# 进化引擎 Demo")
    print("# LivingTreeAI - Evolution Engine")
    print("#" * 60)

    try:
        # Demo 1: NSGA-II
        pareto, history = demo_nsga2()

        # Demo 2: 自适应进化
        adaptive_engine = demo_adaptive_evolution()

        # Demo 3: 对比实验
        fixed_results, adaptive_results = demo_comparison()

        print("\n" + "=" * 60)
        print("所有 Demo 完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
