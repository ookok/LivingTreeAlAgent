"""
进化日志器 - 记录进化过程
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import os


@dataclass
class EvolutionLog:
    """进化日志条目"""
    generation: int
    timestamp: str
    best_fitness: float
    average_fitness: float
    worst_fitness: float
    fitness_variance: float
    population_diversity: float
    mutation_count: int
    crossover_count: int
    selection_pressure: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class EvolutionLogger:
    """
    进化日志器
    
    记录进化过程中的各种指标，用于分析和可视化
    """
    
    def __init__(self, log_dir: Optional[str] = None):
        self.log_dir = log_dir or "./evolution_logs"
        self.current_run: Optional[str] = None
        self.logs: List[EvolutionLog] = []
        
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
    def start_run(self, run_id: Optional[str] = None) -> str:
        """
        开始新的进化运行
        
        Args:
            run_id: 运行ID，默认使用时间戳
            
        Returns:
            运行ID
        """
        if run_id is None:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            
        self.current_run = run_id
        self.logs = []
        
        # 创建运行目录
        run_dir = os.path.join(self.log_dir, run_id)
        if not os.path.exists(run_dir):
            os.makedirs(run_dir)
            
        return run_id
    
    def log_generation(self, generation: int, 
                      population_stats: Dict[str, Any],
                      mutation_count: int = 0,
                      crossover_count: int = 0,
                      selection_pressure: float = 1.0,
                      metadata: Optional[Dict[str, Any]] = None):
        """
        记录一代的进化信息
        
        Args:
            generation: 代数
            population_stats: 种群统计信息
            mutation_count: 突变次数
            crossover_count: 交叉次数
            selection_pressure: 选择压力
            metadata: 额外元数据
        """
        log = EvolutionLog(
            generation=generation,
            timestamp=datetime.now().isoformat(),
            best_fitness=population_stats.get('best_fitness', 0),
            average_fitness=population_stats.get('average_fitness', 0),
            worst_fitness=population_stats.get('worst_fitness', 0),
            fitness_variance=population_stats.get('variance', 0),
            population_diversity=population_stats.get('diversity', 0),
            mutation_count=mutation_count,
            crossover_count=crossover_count,
            selection_pressure=selection_pressure,
            metadata=metadata or {},
        )
        
        self.logs.append(log)
        
    def save_run(self):
        """保存当前运行的所有日志"""
        if not self.current_run:
            return
            
        log_file = os.path.join(self.log_dir, self.current_run, "evolution_log.json")
        
        log_data = {
            'run_id': self.current_run,
            'start_time': self.logs[0].timestamp if self.logs else None,
            'end_time': self.logs[-1].timestamp if self.logs else None,
            'total_generations': len(self.logs),
            'logs': [
                {
                    'generation': log.generation,
                    'timestamp': log.timestamp,
                    'best_fitness': log.best_fitness,
                    'average_fitness': log.average_fitness,
                    'worst_fitness': log.worst_fitness,
                    'fitness_variance': log.fitness_variance,
                    'population_diversity': log.population_diversity,
                    'mutation_count': log.mutation_count,
                    'crossover_count': log.crossover_count,
                    'selection_pressure': log.selection_pressure,
                    'metadata': log.metadata,
                }
                for log in self.logs
            ]
        }
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
            
    def load_run(self, run_id: str) -> List[EvolutionLog]:
        """加载指定运行的日志"""
        log_file = os.path.join(self.log_dir, run_id, "evolution_log.json")
        
        if not os.path.exists(log_file):
            return []
            
        with open(log_file, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
            
        return [
            EvolutionLog(**log) for log in log_data['logs']
        ]
    
    def get_best_generation(self) -> Optional[EvolutionLog]:
        """获取最佳代数"""
        if not self.logs:
            return None
        return max(self.logs, key=lambda x: x.best_fitness)
    
    def get_convergence_info(self) -> Dict[str, Any]:
        """获取收敛信息"""
        if len(self.logs) < 10:
            return {'converged': False, 'reason': 'not_enough_data'}
            
        recent_best = [log.best_fitness for log in self.logs[-10:]]
        improvement = max(recent_best) - min(recent_best)
        
        return {
            'converged': improvement < 1e-6,
            'recent_improvement': improvement,
            'generations_without_improvement': self._count_stagnant_generations(),
        }
    
    def _count_stagnant_generations(self) -> int:
        """计算没有改进的代数"""
        if not self.logs:
            return 0
            
        count = 0
        best_ever = self.logs[0].best_fitness
        
        for log in self.logs[1:]:
            if log.best_fitness <= best_ever:
                count += 1
            else:
                best_ever = log.best_fitness
                count = 0
                
        return count
    
    def generate_report(self) -> str:
        """生成进化报告"""
        if not self.logs:
            return "No evolution data available."
            
        best = self.get_best_generation()
        convergence = self.get_convergence_info()
        
        report = f"""
========================================
        Evolution Report
========================================

Run ID: {self.current_run}
Total Generations: {len(self.logs)}

Best Solution:
  Generation: {best.generation}
  Best Fitness: {best.best_fitness:.6f}
  Average Fitness: {best.average_fitness:.6f}

Convergence:
  Converged: {convergence.get('converged', False)}
  Generations Without Improvement: {convergence.get('generations_without_improvement', 0)}

Population Statistics:
  Final Average Fitness: {self.logs[-1].average_fitness:.6f}
  Final Diversity: {self.logs[-1].population_diversity:.6f}
  
Operations:
  Total Mutations: {sum(log.mutation_count for log in self.logs)}
  Total Crossovers: {sum(log.crossover_count for log in self.logs)}
  
========================================
"""
        return report
