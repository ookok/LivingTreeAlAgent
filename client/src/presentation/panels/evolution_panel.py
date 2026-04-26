"""
进化面板 - 可视化进化引擎
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextEdit, QProgressBar, 
    QGroupBox, QFormLayout, QSpinBox, 
    QDoubleSpinBox, QComboBox, QCheckBox,
)
from PyQt6.QtGui import QFont


class EvolutionPanel(QWidget):
    """进化面板 - 可视化进化引擎"""
    
    evolution_started = pyqtSignal()
    evolution_stopped = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._init_data()
        
    def _setup_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("🧬 进化面板")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        # 描述
        desc = QLabel("可视化进化引擎 - 监控和控制系统自我进化过程")
        desc.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(desc)
        
        # 控制区域
        control_group = QGroupBox("进化控制")
        control_layout = QHBoxLayout(control_group)
        
        self.start_btn = QPushButton("开始进化")
        self.start_btn.clicked.connect(self._start_evolution)
        control_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止进化")
        self.stop_btn.clicked.connect(self._stop_evolution)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)
        
        control_layout.addStretch()
        
        # 状态标签
        self.status_label = QLabel("⚪ 就绪")
        self.status_label.setStyleSheet("font-size: 14px;")
        control_layout.addWidget(self.status_label)
        
        layout.addWidget(control_group)
        
        # 参数配置
        param_group = QGroupBox("进化参数")
        param_layout = QFormLayout(param_group)
        
        self.population_spin = QSpinBox()
        self.population_spin.setRange(10, 1000)
        self.population_spin.setValue(100)
        param_layout.addRow("种群大小:", self.population_spin)
        
        self.generations_spin = QSpinBox()
        self.generations_spin.setRange(1, 1000)
        self.generations_spin.setValue(50)
        param_layout.addRow("进化代数:", self.generations_spin)
        
        self.mutation_spin = QDoubleSpinBox()
        self.mutation_spin.setRange(0.0, 1.0)
        self.mutation_spin.setValue(0.1)
        self.mutation_spin.setSingleStep(0.01)
        param_layout.addRow("变异率:", self.mutation_spin)
        
        self.crossover_spin = QDoubleSpinBox()
        self.crossover_spin.setRange(0.0, 1.0)
        self.crossover_spin.setValue(0.8)
        self.crossover_spin.setSingleStep(0.01)
        param_layout.addRow("交叉率:", self.crossover_spin)
        
        layout.addWidget(param_group)
        
        # 进化日志
        log_group = QGroupBox("进化日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(300)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
    def _init_data(self):
        """初始化数据"""
        self._evolution_running = False
        self._current_generation = 0
        self._timer = QTimer()
        self._timer.timeout.connect(self._evolution_step)
        
    def _start_evolution(self):
        """开始进化"""
        self._evolution_running = True
        self._current_generation = 0
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("🟢 进化中...")
        
        self._log("开始进化...")
        self._log(f"  种群大小: {self.population_spin.value()}")
        self._log(f"  进化代数: {self.generations_spin.value()}")
        self._log(f"  变异率: {self.mutation_spin.value()}")
        self._log(f"  交叉率: {self.crossover_spin.value()}")
        
        self.evolution_started.emit()
        
        # 启动定时器（模拟进化过程）
        self._timer.start(100)  # 每100ms执行一代
        
    def _stop_evolution(self):
        """停止进化"""
        self._evolution_running = False
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("⚪ 已停止")
        
        self._log("进化已停止")
        
        self.evolution_stopped.emit()
        
        self._timer.stop()
        
    def _evolution_step(self):
        """进化步骤（模拟）"""
        if not self._evolution_running:
            return
            
        self._current_generation += 1
        
        # 模拟进化过程
        fitness = 0.5 + 0.5 * (1 - 1 / (1 + self._current_generation))
        
        self._log(f"第 {self._current_generation} 代: 最佳适应度 = {fitness:.4f}")
        
        # 更新进度
        progress = int((self._current_generation / self.generations_spin.value()) * 100)
        self.progress_bar.setValue(progress)
        
        # 检查是否完成
        if self._current_generation >= self.generations_spin.value():
            self._stop_evolution()
            self.status_label.setText("✅ 进化完成")
            self._log("进化完成！")
            
    def _log(self, message: str):
        """添加日志"""
        self.log_text.append(message)
        
    def get_config(self) -> dict:
        """获取进化配置"""
        return {
            "population_size": self.population_spin.value(),
            "generations": self.generations_spin.value(),
            "mutation_rate": self.mutation_spin.value(),
            "crossover_rate": self.crossover_spin.value(),
        }
