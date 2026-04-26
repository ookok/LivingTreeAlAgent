"""
Evolution Panel - 进化引擎可视化面板
PyQt6 UI for visualizing and controlling the evolution engine

Author: LivingTreeAI Team
Version: 2.0.0
"""

from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout,
    QWidget, QPushButton, QLabel, QProgressBar, QTextEdit,
    QTabWidget, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QGroupBox, QFormLayout, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QFont, QColor, QPalette
from typing import List, Dict, Any, Optional, Callable
import numpy as np
import random
import time
from dataclasses import asdict

# 尝试导入进化引擎
try:
    from client.src.business.evolution import (
        VisualEvolutionEngine, ParameterTuner, ABTestFramework,
        SelfDiagnosis, GeneType, Gene, Chromosome, EvolutionSnapshot
    )
    EVOLUTION_AVAILABLE = True
except ImportError:
    EVOLUTION_AVAILABLE = False
    VisualEvolutionEngine = None


class EvolutionWorker(QThread):
    """进化引擎工作线程"""
    
    generation_complete = pyqtSignal(object)  # EvolutionSnapshot
    evolution_complete = pyqtSignal(list)      # List[EvolutionSnapshot]
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.engine: Optional[VisualEvolutionEngine] = None
        self.max_generations = 100
        self.target_fitness = None
        self.running = False
        
    def set_engine(self, engine: VisualEvolutionEngine):
        self.engine = engine
        
    def set_parameters(self, max_gen: int, target_fit: Optional[float]):
        self.max_generations = max_gen
        self.target_fitness = target_fit
        
    def run(self):
        self.running = True
        
        try:
            snapshots = []
            
            for _ in range(self.max_generations):
                if not self.running:
                    break
                    
                snapshot = self.engine.evolve_generation()
                snapshots.append(snapshot)
                self.generation_complete.emit(snapshot)
                
                if self.target_fitness and snapshot.best_fitness >= self.target_fitness:
                    break
                    
            self.evolution_complete.emit(snapshots)
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            
    def stop(self):
        self.running = False
        

class EvolutionPanel(QWidget):
    """
    进化引擎可视化面板
    
    功能：
    - 参数配置
    - 实时进化可视化
    - 适应度曲线图
    - 基因分析
    - 诊断报告
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        if not EVOLUTION_AVAILABLE:
            self._init_error_ui()
            return
            
        self.engine: Optional[VisualEvolutionEngine] = None
        self.worker: Optional[EvolutionWorker] = None
        self.tuner: Optional[ParameterTuner] = None
        self.ab_tester: Optional[ABTestFramework] = None
        self.diagnostics: Optional[SelfDiagnosis] = None
        
        self._init_ui()
        self._init_engine()
        
    def _init_error_ui(self):
        """初始化错误 UI"""
        layout = QVBoxLayout(self)
        label = QLabel("❌ 进化引擎模块不可用\n请确保 core.evolution 模块已正确安装")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
    def _init_ui(self):
        """初始化 UI"""
        main_layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel("🧬 进化引擎控制面板")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        # 选项卡
        tabs = QTabWidget()
        tabs.addTab(self._create_config_tab(), "⚙️ 参数配置")
        tabs.addTab(self._create_control_tab(), "▶️ 运行控制")
        tabs.addTab(self._create_visualization_tab(), "📊 可视化")
        tabs.addTab(self._create_diagnostics_tab(), "🔍 诊断")
        tabs.addTab(self._create_ab_test_tab(), "🧪 A/B 测试")
        
        main_layout.addWidget(tabs)
        
        # 状态栏
        self.status_bar = QLabel("就绪")
        self.status_bar.setStyleSheet("padding: 5px; background: #f0f0f0;")
        main_layout.addWidget(self.status_bar)
        
    def _create_config_tab(self) -> QWidget:
        """创建参数配置选项卡"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 种群大小
        self.pop_size_spin = QSpinBox()
        self.pop_size_spin.setRange(10, 1000)
        self.pop_size_spin.setValue(100)
        layout.addRow("种群大小:", self.pop_size_spin)
        
        # 精英数量
        self.elite_spin = QSpinBox()
        self.elite_spin.setRange(1, 50)
        self.elite_spin.setValue(10)
        layout.addRow("精英数量:", self.elite_spin)
        
        # 变异率
        self.mutation_spin = QDoubleSpinBox()
        self.mutation_spin.setRange(0.01, 0.5)
        self.mutation_spin.setValue(0.1)
        self.mutation_spin.setSingleStep(0.01)
        layout.addRow("变异率:", self.mutation_spin)
        
        # 交叉率
        self.crossover_spin = QDoubleSpinBox()
        self.crossover_spin.setRange(0.1, 0.95)
        self.crossover_spin.setValue(0.7)
        self.crossover_spin.setSingleStep(0.05)
        layout.addRow("交叉率:", self.crossover_spin)
        
        # 初始化按钮
        init_btn = QPushButton("初始化种群")
        init_btn.clicked.connect(self._initialize_population)
        layout.addRow(init_btn)
        
        return widget
        
    def _create_control_tab(self) -> QWidget:
        """创建运行控制选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶️ 开始进化")
        self.start_btn.clicked.connect(self._start_evolution)
        btn_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏸️ 停止")
        self.stop_btn.clicked.connect(self._stop_evolution)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)
        
        self.step_btn = QPushButton("⏭️ 单步")
        self.step_btn.clicked.connect(self._step_evolution)
        btn_layout.addWidget(self.step_btn)
        
        layout.addLayout(btn_layout)
        
        # 运行参数
        param_layout = QFormLayout()
        
        self.max_gen_spin = QSpinBox()
        self.max_gen_spin.setRange(1, 10000)
        self.max_gen_spin.setValue(100)
        param_layout.addRow("最大代数:", self.max_gen_spin)
        
        self.target_fit_spin = QDoubleSpinBox()
        self.target_fit_spin.setRange(0, 1000)
        self.target_fit_spin.setValue(0)
        param_layout.addRow("目标适应度 (0=无):", self.target_fit_spin)
        
        layout.addLayout(param_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 统计信息
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(200)
        layout.addWidget(QLabel("实时统计:"))
        layout.addWidget(self.stats_text)
        
        return widget
        
    def _create_visualization_tab(self) -> QWidget:
        """创建可视化选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 适应度趋势图 (占位)
        self.fitness_plot_label = QLabel("📈 适应度趋势图\n(需要 matplotlib 集成)")
        self.fitness_plot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fitness_plot_label.setStyleSheet("border: 1px solid #ccc; padding: 20px;")
        self.fitness_plot_label.setMinimumHeight(300)
        layout.addWidget(self.fitness_plot_label)
        
        # 数据表格
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(5)
        self.data_table.setHorizontalHeaderLabels(["代数", "最佳适应度", "平均适应度", "最差适应度", "多样性"])
        layout.addWidget(QLabel("进化历史:"))
        layout.addWidget(self.data_table)
        
        return widget
        
    def _create_diagnostics_tab(self) -> QWidget:
        """创建诊断选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 诊断按钮
        diag_btn = QPushButton("🔍 运行诊断")
        diag_btn.clicked.connect(self._run_diagnostics)
        layout.addWidget(diag_btn)
        
        # 诊断报告
        self.diagnostic_text = QTextEdit()
        self.diagnostic_text.setReadOnly(True)
        layout.addWidget(QLabel("诊断报告:"))
        layout.addWidget(self.diagnostic_text)
        
        # 历史记录
        self.diagnostic_history = QTableWidget()
        self.diagnostic_history.setColumnCount(4)
        self.diagnostic_history.setHorizontalHeaderLabels(["时间", "问题", "警告", "建议"])
        layout.addWidget(QLabel("诊断历史:"))
        layout.addWidget(self.diagnostic_history)
        
        return widget
        
    def _create_ab_test_tab(self) -> QWidget:
        """创建 A/B 测试选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 创建测试按钮
        create_btn = QPushButton("➕ 创建 A/B 测试")
        create_btn.clicked.connect(self._create_ab_test)
        layout.addWidget(create_btn)
        
        # 测试结果
        self.ab_test_results = QTextEdit()
        self.ab_test_results.setReadOnly(True)
        layout.addWidget(QLabel("测试结果:"))
        layout.addWidget(self.ab_test_results)
        
        return widget
        
    def _init_engine(self):
        """初始化进化引擎"""
        try:
            self.engine = VisualEvolutionEngine(
                population_size=self.pop_size_spin.value(),
                elite_size=self.elite_spin.value(),
                mutation_rate=self.mutation_spin.value(),
                crossover_rate=self.crossover_spin.value(),
            )
            
            # 创建增强模块
            self.tuner = ParameterTuner(self.engine)
            self.ab_tester = ABTestFramework()
            self.diagnostics = SelfDiagnosis(self.engine)
            
            self.status_bar.setText("✅ 进化引擎已初始化")
            
        except Exception as e:
            self.status_bar.setText(f"❌ 初始化失败: {e}")
            
    def _initialize_population(self):
        """初始化种群"""
        if not self.engine:
            QMessageBox.warning(self, "警告", "引擎未初始化")
            return
            
        # 创建示例基因模板
        gene_templates = [
            Gene(id="gene_0", gene_type=GeneType.PARAMETER, name="学习率", value=0.01),
            Gene(id="gene_1", gene_type=GeneType.PARAMETER, name="批量大小", value=32),
            Gene(id="gene_2", gene_type=GeneType.PARAMETER, name="隐藏层大小", value=128),
            Gene(id="gene_3", gene_type=GeneType.STRATEGY, name="优化器", value="adam"),
        ]
        
        # 设置适应度函数
        def sample_fitness(chromosome: Chromosome) -> float:
            """示例适应度函数：Rastrigin 函数（多峰，难优化）"""
            genes = [g.value for g in chromosome.genes if isinstance(g.value, (int, float))]
            if not genes:
                return 0.0
            x = np.array(genes)
            A = 10
            n = len(x)
            return A * n + np.sum(x**2 - A * np.cos(2 * np.pi * x))
            
        self.engine.set_fitness_function(sample_fitness)
        self.engine.initialize_population(gene_templates)
        
        self.status_bar.setText(f"✅ 种群已初始化 ({self.engine._population_size} 个个体)")
        
    def _start_evolution(self):
        """开始进化"""
        if not self.engine:
            QMessageBox.warning(self, "警告", "请先初始化种群")
            return
            
        self.worker = EvolutionWorker()
        self.worker.set_engine(self.engine)
        self.worker.set_parameters(
            self.max_gen_spin.value(),
            self.target_fit_spin.value() if self.target_fit_spin.value() > 0 else None,
        )
        
        # 连接信号
        self.worker.generation_complete.connect(self._on_generation_complete)
        self.worker.evolution_complete.connect(self._on_evolution_complete)
        self.worker.error_occurred.connect(self._on_error)
        
        # 更新 UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.step_btn.setEnabled(False)
        
        # 启动线程
        self.worker.start()
        
        self.status_bar.setText("▶️ 进化中...")
        
    def _stop_evolution(self):
        """停止进化"""
        if self.worker:
            self.worker.stop()
            self.worker.wait()
            
        self._reset_buttons()
        self.status_bar.setText("⏸️ 已停止")
        
    def _step_evolution(self):
        """单步进化"""
        if not self.engine:
            return
            
        try:
            snapshot = self.engine.evolve_generation()
            self._on_generation_complete(snapshot)
            self.status_bar.setText(f"⏭️ 第 {snapshot.generation} 代完成")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
            
    def _on_generation_complete(self, snapshot: EvolutionSnapshot):
        """一代进化完成"""
        # 更新进度
        if self.max_gen_spin.value() > 0:
            progress = int((snapshot.generation / self.max_gen_spin.value()) * 100)
            self.progress_bar.setValue(progress)
            
        # 更新统计
        stats = f"""=== 第 {snapshot.generation} 代 ===
最佳适应度: {snapshot.best_fitness:.6f}
平均适应度: {snapshot.avg_fitness:.6f}
最差适应度: {snapshot.worst_fitness:.6f}
多样性: {snapshot.diversity:.6f}
种群大小: {snapshot.population_size}
"""
        self.stats_text.setText(stats)
        
        # 更新表格
        row = self.data_table.rowCount()
        self.data_table.insertRow(row)
        self.data_table.setItem(row, 0, QTableWidgetItem(str(snapshot.generation)))
        self.data_table.setItem(row, 1, QTableWidgetItem(f"{snapshot.best_fitness:.6f}"))
        self.data_table.setItem(row, 2, QTableWidgetItem(f"{snapshot.avg_fitness:.6f}"))
        self.data_table.setItem(row, 3, QTableWidgetItem(f"{snapshot.worst_fitness:.6f}"))
        self.data_table.setItem(row, 4, QTableWidgetItem(f"{snapshot.diversity:.6f}"))
        
        # 自动调参
        if self.tuner:
            new_params = self.tuner.tune_parameters(snapshot)
            if new_params:
                self.status_bar.setText(f"🔧 参数已调整: {new_params}")
                
    def _on_evolution_complete(self, snapshots: List[EvolutionSnapshot]):
        """进化完成"""
        self._reset_buttons()
        
        best = self.engine.get_best_chromosome()
        msg = f"""进化完成！
        
总代数: {len(snapshots)}
最佳适应度: {best.fitness if best else 0:.6f}
"""
        QMessageBox.information(self, "完成", msg)
        self.status_bar.setText("✅ 进化完成")
        
    def _on_error(self, error_msg: str):
        """错误处理"""
        self._reset_buttons()
        QMessageBox.critical(self, "错误", error_msg)
        self.status_bar.setText(f"❌ 错误: {error_msg}")
        
    def _reset_buttons(self):
        """重置按钮状态"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.step_btn.setEnabled(True)
        
    def _run_diagnostics(self):
        """运行诊断"""
        if not self.diagnostics:
            QMessageBox.warning(self, "警告", "诊断模块未初始化")
            return
            
        report = self.diagnostics.run_diagnosis()
        
        # 显示报告
        text = f"""=== 诊断报告 ===
时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(report['timestamp']))}
代数: {report['generation']}

问题:
"""
        for issue in report['issues']:
            text += f"  - {issue}\n"
            
        if report['warnings']:
            text += "\n警告:\n"
            for warning in report['warnings']:
                text += f"  - {warning}\n"
                
        if report['suggestions']:
            text += "\n建议:\n"
            for suggestion in report['suggestions']:
                text += f"  - {suggestion}\n"
                
        self.diagnostic_text.setText(text)
        
        # 更新历史表格
        row = self.diagnostic_history.rowCount()
        self.diagnostic_history.insertRow(row)
        self.diagnostic_history.setItem(row, 0, QTableWidgetItem(
            time.strftime('%H:%M:%S', time.localtime(report['timestamp']))
        ))
        self.diagnostic_history.setItem(row, 1, QTableWidgetItem(
            "\n".join(report['issues']) if report['issues'] else "无"
        ))
        self.diagnostic_history.setItem(row, 2, QTableWidgetItem(
            "\n".join(report['warnings']) if report['warnings'] else "无"
        ))
        self.diagnostic_history.setItem(row, 3, QTableWidgetItem(
            "\n".join(report['suggestions']) if report['suggestions'] else "无"
        ))
        
        self.status_bar.setText("🔍 诊断完成")
        
    def _create_ab_test(self):
        """创建 A/B 测试"""
        if not self.ab_tester:
            QMessageBox.warning(self, "警告", "A/B 测试模块未初始化")
            return
            
        # 创建示例测试
        test_id = f"test_{int(time.time())}"
        
        param_configs = [
            {"mutation_rate": 0.1, "crossover_rate": 0.7, "population_size": 50},
            {"mutation_rate": 0.2, "crossover_rate": 0.5, "population_size": 100},
            {"mutation_rate": 0.05, "crossover_rate": 0.9, "population_size": 200},
        ]
        
        try:
            self.ab_tester.create_test(
                test_id=test_id,
                param_configs=param_configs,
                max_generations=50,
            )
            
            result = self.ab_tester.run_test(test_id)
            
            # 显示结果
            text = f"""=== A/B 测试结果 ===
测试 ID: {result['test_id']}
最优配置 ID: {result['best_config_id']}
最优适应度: {result['best_fitness']:.6f}

所有配置结果:
"""
            for r in result['results']:
                text += f"\n配置 {r['config_id']}:\n"
                text += f"  最佳适应度: {r['best_fitness']:.6f}\n"
                text += f"  平均适应度: {r['avg_fitness']:.6f}\n"
                text += f"  代数: {r['generations']}\n"
                
            self.ab_test_results.setText(text)
            self.status_bar.setText(f"🧪 A/B 测试完成: {test_id}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
            

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = EvolutionPanel()
    window.show()
    sys.exit(app.exec())
