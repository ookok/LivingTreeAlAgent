# AI驱动UI自我测试与修复系统设计方案

**项目**: LivingTreeAI  
**版本**: 2.0.0（PyQt6指挥中心版）  
**更新日期**: 2026-04-26  
**作者**: LivingTreeAI Design Team

---

## 一、核心理念

### 1.1 愿景目标

让PyQt6客户端成为"AI测试指挥官"，控制AI机器人去测试和修复任何外部应用（Web、桌面、移动端）。

### 1.2 核心理念转变

**从**："PyQt6客户端内置UI测试系统"  
**到**："PyQt6作为AI控制台，指挥外部应用测试"

### 1.3 核心能力

| 能力 | 说明 | 类比 |
|------|------|------|
| **控制能力** | PyQt6控制外部应用 | AI的指挥中心 |
| **视觉能力** | 捕获外部应用界面 | AI的眼睛 |
| **交互能力** | 操作外部应用 | AI的手 |
| **分析能力** | 诊断外部应用问题 | AI的大脑 |
| **修复能力** | 修复外部应用问题 | AI的修复工具 |

### 1.4 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   PyQt6 AI测试指挥官 (控制台)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  🎛️ PyQt6 控制面板                                                       │   │
│  │  ├── 目标应用选择（Web/桌面/移动）                                         │   │
│  │  ├── 测试任务输入                                                         │   │
│  │  ├── 测试策略配置                                                         │   │
│  │  ├── AI模型选择                                                           │   │
│  │  └── 控制按钮（开始/暂停/停止）                                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  📺 实时监控面板                                                         │   │
│  │  ├── 实时屏幕显示                                                         │   │
│  │  ├── 思维链进度                                                           │   │
│  │  ├── 测试日志                                                             │   │
│  │  └── 交互轨迹                                                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  🔍 问题分析与修复面板                                                    │   │
│  │  ├── 问题列表（分类/严重性）                                               │   │
│  │  ├── 问题详情                                                             │   │
│  │  ├── 根因分析                                                             │   │
│  │  └── 修复建议                                                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                        外部控制器 (Agents)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │  🌐 Web控制器   │  │  🖥️ 桌面控制器  │  │  📱 移动控制器  │                 │
│  │  Selenium/     │  │  PyAutoGUI/    │  │  Appium        │                 │
│  │  Playwright    │  │  pywinauto     │  │                │                 │
│  └────────────────┘  └────────────────┘  └────────────────┘                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.5 四层闭环架构

| 层级 | 名称 | 功能 |
|------|------|------|
| 🔍 问题诊断层 | AI的大脑 | 问题检测、根因分析、严重性评估 |
| 🛠️ 修复执行层 | AI的修复工具 | 自动修复引擎、修复验证器 |
| 🖱️ 交互执行层 | AI的手 | 智能交互模拟、思维链驱动、交互录制 |
| 👁️ 视觉感知层 | AI的眼睛 | 屏幕捕获、元素识别、视觉对比 |

---

## 二、PyQt6控制台设计

### 2.1 主界面架构

```python
# ui/ui_test_commander/ai_test_commander.py

class AITestCommander(QMainWindow):
    """
    AI测试指挥官主界面
    
    PyQt6作为控制中心，指挥AI测试外部应用
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LivingTreeAI - UI测试指挥官")
        self.setMinimumSize(1400, 900)
        
        # 初始化组件
        self.test_scheduler = AITestScheduler()
        self.external_controller = ExternalAppController()
        self.chain_of_thought = ChainOfThoughtTester()
        
        # 设置UI
        self.setup_ui()
        
        # 连接信号
        self.connect_signals()
    
    def setup_ui(self):
        """设置主界面"""
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # 1. 控制区域
        control_bar = self.create_control_bar()
        main_layout.addLayout(control_bar)
        
        # 2. 主内容区域
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：控制面板
        left_panel = self.create_control_panel()
        splitter.addWidget(left_panel)
        
        # 中间：实时监控
        center_panel = self.create_monitor_panel()
        splitter.addWidget(center_panel)
        
        # 右侧：问题分析
        right_panel = self.create_problem_panel()
        splitter.addWidget(right_panel)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)
        
        main_layout.addWidget(splitter)
        
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
    
    def create_control_bar(self) -> QHBoxLayout:
        """创建控制栏"""
        layout = QHBoxLayout()
        
        # 目标应用选择
        layout.addWidget(QLabel("测试目标:"))
        self.target_selector = QComboBox()
        self.target_selector.addItems([
            "🌐 Web应用",
            "🖥️ 桌面应用", 
            "📱 移动应用"
        ])
        layout.addWidget(self.target_selector)
        
        # 测试任务输入
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("描述你要测试什么...")
        self.task_input.setMinimumWidth(400)
        layout.addWidget(self.task_input)
        
        # 控制按钮
        self.start_btn = QPushButton("▶ 开始AI测试")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        layout.addWidget(self.start_btn)
        
        self.pause_btn = QPushButton("⏸ 暂停")
        self.pause_btn.setEnabled(False)
        layout.addWidget(self.pause_btn)
        
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)
        
        layout.addStretch()
        
        return layout
```

### 2.2 测试控制面板

```python
# ui/ui_test_commander/panels/test_control_panel.py

class TestControlPanel(QWidget):
    """测试控制面板"""
    
    def create_control_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 1. 目标应用配置
        target_group = QGroupBox("🎯 目标应用配置")
        target_layout = QFormLayout()
        
        # Web应用配置
        web_group = QWidget()
        web_layout = QVBoxLayout()
        
        self.web_url = QLineEdit("https://")
        self.web_url.setPlaceholderText("输入Web地址...")
        web_layout.addWidget(QLabel("Web地址:"))
        web_layout.addWidget(self.web_url)
        
        # 浏览器选择
        self.browser_selector = QComboBox()
        self.browser_selector.addItems(["Chrome", "Firefox", "Edge"])
        web_layout.addWidget(QLabel("浏览器:"))
        web_layout.addWidget(self.browser_selector)
        
        web_group.setLayout(web_layout)
        target_layout.addRow(web_group)
        
        # 桌面应用配置
        desktop_group = QWidget()
        desktop_layout = QVBoxLayout()
        
        self.desktop_app_path = QLineEdit()
        self.desktop_app_path.setPlaceholderText("选择桌面应用路径...")
        
        browse_layout = QHBoxLayout()
        self.browse_btn = QPushButton("📂 浏览...")
        self.browse_btn.clicked.connect(self.browse_desktop_app)
        browse_layout.addWidget(self.desktop_app_path)
        browse_layout.addWidget(self.browse_btn)
        
        desktop_layout.addWidget(QLabel("应用路径:"))
        desktop_layout.addLayout(browse_layout)
        
        desktop_group.setLayout(desktop_layout)
        target_layout.addRow(desktop_group)
        
        target_group.setLayout(target_layout)
        
        # 2. 测试策略选择
        strategy_group = QGroupBox("📋 测试策略")
        strategy_layout = QVBoxLayout()
        
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems([
            "🔍 探索性测试（AI自主探索）",
            "⚡ 功能测试（测试特定功能）",
            "👥 可用性测试（检查用户体验）",
            "📊 性能测试（检查性能问题）",
            "♿ 可访问性测试（检查可访问性）"
        ])
        strategy_layout.addWidget(self.strategy_combo)
        
        # 自定义测试任务
        self.custom_tasks = QTextEdit()
        self.custom_tasks.setPlaceholderText("指定要测试的具体功能...")
        self.custom_tasks.setMaximumHeight(80)
        strategy_layout.addWidget(QLabel("自定义测试任务:"))
        strategy_layout.addWidget(self.custom_tasks)
        
        strategy_group.setLayout(strategy_layout)
        
        # 3. AI设置
        ai_group = QGroupBox("🤖 AI设置")
        ai_layout = QFormLayout()
        
        self.use_local_llm = QCheckBox("使用本地AI模型")
        ai_layout.addRow("模型来源:", self.use_local_llm)
        
        self.llm_model = QComboBox()
        self.llm_model.addItems(["GPT-4", "Claude-3", "本地模型", "DeepSeek"])
        ai_layout.addRow("AI模型:", self.llm_model)
        
        self.ai_temperature = QSlider(Qt.Orientation.Horizontal)
        self.ai_temperature.setRange(0, 100)
        self.ai_temperature.setValue(70)
        ai_layout.addRow("创造性:", self.ai_temperature)
        
        ai_group.setLayout(ai_layout)
        
        # 布局
        layout.addWidget(target_group)
        layout.addWidget(strategy_group)
        layout.addWidget(ai_group)
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
```

### 2.3 实时监控面板

```python
# ui/ui_test_commander/panels/real_time_monitor.py

class RealTimeMonitor(QWidget):
    """实时监控面板"""
    
    def __init__(self):
        super().__init__()
        self.screen_capture_thread = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # 屏幕监控区域
        screen_group = QGroupBox("📺 实时屏幕监控")
        screen_layout = QVBoxLayout()
        
        # 屏幕显示标签
        self.screen_label = QLabel()
        self.screen_label.setMinimumSize(800, 500)
        self.screen_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 2px solid #333;
                border-radius: 8px;
            }
        """)
        self.screen_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screen_label.setText("等待开始测试...")
        
        screen_layout.addWidget(self.screen_label)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        
        self.capture_btn = QPushButton("📷 截屏")
        self.record_btn = QPushButton("⏺ 录制")
        self.pause_monitor_btn = QPushButton("⏸ 暂停监控")
        
        control_layout.addWidget(self.capture_btn)
        control_layout.addWidget(self.record_btn)
        control_layout.addWidget(self.pause_monitor_btn)
        control_layout.addStretch()
        
        screen_layout.addLayout(control_layout)
        screen_group.setLayout(screen_layout)
        
        # 思维链显示
        thought_group = QGroupBox("🧠 思维链进度")
        thought_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(20)
        thought_layout.addWidget(self.progress_bar)
        
        self.current_thought_label = QLabel("等待开始...")
        self.current_thought_label.setWordWrap(True)
        self.current_thought_label.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                padding: 8px;
                border-radius: 4px;
                font-size: 13px;
            }
        """)
        thought_layout.addWidget(self.current_thought_label)
        
        self.thought_list = QListWidget()
        self.thought_list.setMaximumHeight(150)
        thought_layout.addWidget(self.thought_list)
        
        thought_group.setLayout(thought_layout)
        
        # 日志显示
        log_group = QGroupBox("📝 测试日志")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextBrowser()
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("""
            QTextBrowser {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        
        layout.addWidget(screen_group, 1)
        layout.addWidget(thought_group)
        layout.addWidget(log_group)
        
        self.setLayout(layout)
    
    def start_screen_capture(self):
        """启动屏幕捕获"""
        if self.screen_capture_thread is None:
            self.screen_capture_thread = ScreenCaptureThread()
            self.screen_capture_thread.frame_captured.connect(self.update_screen)
            self.screen_capture_thread.start()
    
    def update_screen(self, image: QImage):
        """更新屏幕显示"""
        scaled_image = image.scaled(
            self.screen_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.screen_label.setPixmap(QPixmap.fromImage(scaled_image))
    
    def add_thought_step(self, step_num: int, thought: str):
        """添加思维链步骤"""
        item = QListWidgetItem(f"步骤 {step_num}: {thought}")
        item.setBackground(QColor(200, 230, 200))
        self.thought_list.addItem(item)
        self.thought_list.scrollToBottom()
        
        self.current_thought_label.setText(f"正在执行: {thought}")
        self.progress_bar.setValue(int(step_num / self.total_steps * 100))
    
    def log(self, message: str, level: str = "INFO"):
        """添加日志"""
        timestamp = QTime.currentTime().toString("hh:mm:ss")
        color = {
            "INFO": "#4FC3F7",
            "SUCCESS": "#81C784", 
            "WARNING": "#FFB74D",
            "ERROR": "#E57373"
        }.get(level, "#d4d4d4")
        
        self.log_text.append(
            f'<span style="color: #888;">[{timestamp}]</span> '
            f'<span style="color: {color};">{level}:</span> {message}'
        )
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
```

### 2.4 问题分析与修复面板

```python
# ui/ui_test_commander/panels/problem_analysis_panel.py

class ProblemAnalysisPanel(QWidget):
    """问题分析与修复面板"""
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # 问题汇总
        summary_group = QGroupBox("📊 问题汇总")
        summary_layout = QHBoxLayout()
        
        self.total_problems_label = QLabel("总问题: 0")
        self.critical_label = QLabel("🔴 严重: 0")
        self.warning_label = QLabel("🟡 警告: 0")
        self.info_label = QLabel("🔵 提示: 0")
        
        for label in [self.total_problems_label, self.critical_label, 
                      self.warning_label, self.info_label]:
            label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
            summary_layout.addWidget(label)
        
        summary_layout.addStretch()
        summary_group.setLayout(summary_layout)
        
        # 问题列表
        list_group = QGroupBox("🔍 发现的问题")
        list_layout = QVBoxLayout()
        
        self.problem_tree = QTreeWidget()
        self.problem_tree.setHeaderLabels(["问题", "类型", "严重性", "状态"])
        self.problem_tree.setAlternatingRowColors(True)
        self.problem_tree.itemClicked.connect(self.on_problem_selected)
        
        list_layout.addWidget(self.problem_tree)
        list_group.setLayout(list_layout)
        
        # 问题详情
        detail_group = QGroupBox("📝 问题详情")
        detail_layout = QVBoxLayout()
        
        self.problem_desc = QTextEdit()
        self.problem_desc.setReadOnly(True)
        self.problem_desc.setMaximumHeight(80)
        
        self.evidence_browser = QTextBrowser()
        self.evidence_browser.setMaximumHeight(100)
        
        detail_layout.addWidget(QLabel("问题描述:"))
        detail_layout.addWidget(self.problem_desc)
        detail_layout.addWidget(QLabel("证据截图:"))
        detail_layout.addWidget(self.evidence_browser)
        
        detail_group.setLayout(detail_layout)
        
        # 修复建议
        fix_group = QGroupBox("🛠️ 修复建议")
        fix_layout = QVBoxLayout()
        
        self.fix_suggestions = QTextEdit()
        self.fix_suggestions.setReadOnly(True)
        self.fix_suggestions.setStyleSheet("""
            QTextEdit {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        fix_layout.addWidget(self.fix_suggestions)
        
        # 修复按钮
        fix_buttons = QHBoxLayout()
        
        self.apply_fix_btn = QPushButton("✅ 应用修复")
        self.apply_fix_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
            }
        """)
        
        self.copy_fix_btn = QPushButton("📋 复制修复代码")
        self.skip_fix_btn = QPushButton("⏭️ 跳过")
        
        fix_buttons.addWidget(self.apply_fix_btn)
        fix_buttons.addWidget(self.copy_fix_btn)
        fix_buttons.addWidget(self.skip_fix_btn)
        fix_buttons.addStretch()
        
        fix_layout.addLayout(fix_buttons)
        fix_group.setLayout(fix_layout)
        
        # 布局
        layout.addWidget(summary_group)
        layout.addWidget(list_group, 1)
        layout.addWidget(detail_group)
        layout.addWidget(fix_group)
        
        self.setLayout(layout)
    
    def display_problems(self, problems: List[dict]):
        """显示发现的问题"""
        self.problem_tree.clear()
        
        # 更新汇总
        self.total_problems_label.setText(f"总问题: {len(problems)}")
        
        critical_count = 0
        warning_count = 0
        info_count = 0
        
        for problem in problems:
            severity = problem.get("severity", "info")
            if severity == "critical":
                critical_count += 1
            elif severity == "warning":
                warning_count += 1
            else:
                info_count += 1
            
            # 颜色
            color = {
                "critical": QColor(255, 87, 87),
                "warning": QColor(255, 183, 77),
                "info": QColor(79, 195, 247)
            }.get(severity, QColor(200, 200, 200))
            
            item = QTreeWidgetItem([
                problem["description"],
                problem.get("type", "unknown"),
                severity.upper(),
                "待修复"
            ])
            
            for i in range(4):
                item.setBackground(i, QColor(250, 250, 250) if i % 2 == 0 else QColor(240, 240, 240))
            
            item.setData(0, Qt.ItemDataRole.UserRole, problem)
            self.problem_tree.addTopLevelItem(item)
        
        self.critical_label.setText(f"🔴 严重: {critical_count}")
        self.warning_label.setText(f"🟡 警告: {warning_count}")
        self.info_label.setText(f"🔵 提示: {info_count}")
    
    def on_problem_selected(self, item: QTreeWidgetItem, column: int):
        """问题选中事件"""
        problem = item.data(0, Qt.ItemDataRole.UserRole)
        if problem:
            self.problem_desc.setText(problem.get("description", ""))
            self.fix_suggestions.setText(problem.get("fix_suggestion", ""))
```

---

## 三、外部控制器设计

### 3.1 外部应用控制器

```python
# core/ui_test_fix/controllers/external_app_controller.py

class ExternalAppController:
    """
    外部应用控制器
    
    统一控制Web、桌面、移动应用的测试
    """
    
    def __init__(self):
        self.controller = None
        self.app_type = None
    
    def create_controller(self, app_type: str, config: dict):
        """创建对应的控制器"""
        self.app_type = app_type
        
        if app_type == "web":
            self.controller = WebAppController(config)
        elif app_type == "desktop":
            self.controller = DesktopAppController(config)
        elif app_type == "mobile":
            self.controller = MobileAppController(config)
        else:
            raise ValueError(f"不支持的应用类型: {app_type}")
        
        return self.controller
    
    def launch(self, target: str) -> bool:
        """启动目标应用"""
        return self.controller.launch(target)
    
    def capture_screen(self) -> np.ndarray:
        """捕获屏幕"""
        return self.controller.capture_screen()
    
    def interact(self, instruction: dict) -> InteractionResult:
        """执行交互"""
        return self.controller.execute_action(instruction)


class WebAppController:
    """Web应用控制器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.driver = None
        self.browser_pool = BrowserPool()
    
    def launch(self, url: str) -> bool:
        """启动Web应用"""
        try:
            # 创建浏览器
            browser_type = self.config.get("browser", "chrome")
            
            if browser_type == "chrome":
                options = webdriver.ChromeOptions()
                options.add_argument("--start-maximized")
                options.add_argument("--disable-notifications")
                self.driver = webdriver.Chrome(options=options)
            elif browser_type == "firefox":
                self.driver = webdriver.Firefox()
            elif browser_type == "edge":
                self.driver = webdriver.Edge()
            
            # 访问URL
            self.driver.get(url)
            
            # 等待加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            return True
            
        except Exception as e:
            logging.error(f"启动Web应用失败: {e}")
            return False
    
    def capture_screen(self) -> np.ndarray:
        """捕获屏幕"""
        if self.driver:
            screenshot = self.driver.get_screenshot_as_png()
            return cv2.imdecode(
                np.frombuffer(screenshot, np.uint8), 
                cv2.IMREAD_COLOR
            )
        return None
    
    def analyze_current_page(self) -> PageAnalysis:
        """分析当前页面"""
        # 获取页面元素
        elements = self.extract_page_elements()
        
        # AI分析
        analysis = self.ai_analyze_page(elements)
        
        return PageAnalysis(
            url=self.driver.current_url,
            title=self.driver.title,
            elements=elements,
            ai_analysis=analysis
        )
    
    def extract_page_elements(self) -> List[dict]:
        """提取页面元素"""
        elements = []
        
        # 按钮
        for btn in self.driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit'], a.btn"):
            elements.append({
                "type": "button",
                "text": btn.text,
                "locator": self.get_locator(btn),
                "visible": btn.is_displayed()
            })
        
        # 输入框
        for inp in self.driver.find_elements(By.CSS_SELECTOR, "input, textarea"):
            elements.append({
                "type": "input",
                "name": inp.get_attribute("name"),
                "placeholder": inp.get_attribute("placeholder"),
                "locator": self.get_locator(inp),
                "visible": inp.is_displayed()
            })
        
        # 链接
        for link in self.driver.find_elements(By.TAG_NAME, "a"):
            if link.text:
                elements.append({
                    "type": "link",
                    "text": link.text,
                    "href": link.get_attribute("href"),
                    "locator": self.get_locator(link)
                })
        
        return elements
    
    def execute_action(self, action: dict) -> InteractionResult:
        """执行动作"""
        action_type = action.get("type")
        
        try:
            if action_type == "click":
                element = self.find_element(action["target"])
                element.click()
                
            elif action_type == "type":
                element = self.find_element(action["target"])
                element.clear()
                element.send_keys(action["text"])
                
            elif action_type == "navigate":
                self.driver.get(action["url"])
                
            elif action_type == "wait":
                time.sleep(action["duration"])
            
            # 捕获执行后状态
            screenshot = self.capture_screen()
            
            return InteractionResult(
                success=True,
                screenshot=screenshot,
                message=f"执行成功: {action_type}"
            )
            
        except Exception as e:
            return InteractionResult(
                success=False,
                error=str(e)
            )


class DesktopAppController:
    """桌面应用控制器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.app = None
        self.pyautogui = pyautogui
    
    def launch(self, app_path: str) -> bool:
        """启动桌面应用"""
        try:
            # 使用pywinauto启动应用
            self.app = Application(backend="win32").start(app_path)
            time.sleep(2)  # 等待应用启动
            return True
        except Exception as e:
            logging.error(f"启动桌面应用失败: {e}")
            return False
    
    def capture_screen(self) -> np.ndarray:
        """捕获屏幕"""
        screenshot = self.pyautogui.screenshot()
        return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    
    def find_element_image(self, template_path: str) -> tuple:
        """使用图像识别查找元素"""
        screen = self.capture_screen()
        result = cv2.matchTemplate(screen, cv2.imread(template_path), cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val > 0.8:
            return max_loc
        return None
    
    def execute_action(self, action: dict) -> InteractionResult:
        """执行动作"""
        action_type = action.get("type")
        
        try:
            if action_type == "click":
                if "coords" in action:
                    self.pyautogui.click(action["coords"])
                elif "template" in action:
                    loc = self.find_element_image(action["template"])
                    if loc:
                        self.pyautogui.click(loc)
            
            elif action_type == "type":
                self.pyautogui.typewrite(action["text"])
            
            elif action_type == "hotkey":
                self.pyautogui.hotkey(*action["keys"])
            
            screenshot = self.capture_screen()
            
            return InteractionResult(success=True, screenshot=screenshot)
            
        except Exception as e:
            return InteractionResult(success=False, error=str(e))
```

### 3.2 AI测试调度器

```python
# core/ui_test_fix/scheduler/ai_test_scheduler.py

class AITestScheduler(QObject):
    """
    AI测试调度器
    
    协调整个测试流程
    """
    
    # 信号
    test_started = pyqtSignal(str)
    test_progress = pyqtSignal(dict)
    test_completed = pyqtSignal(dict)
    problem_found = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.external_controller = ExternalAppController()
        self.visual_perception = UIVisualPerception()
        self.chain_of_thought = ChainOfThoughtTester()
        self.problem_diagnoser = UIProblemDiagnoser()
        self.auto_fix_engine = UIAutoFixEngine()
        
        self.is_running = False
        self.current_test = None
    
    def start_ai_test(self, config: dict):
        """开始AI测试"""
        self.is_running = True
        
        try:
            # 1. 初始化测试环境
            self.test_started.emit("初始化测试环境...")
            target = config["target"]
            app_type = config["app_type"]
            
            # 2. 启动目标应用
            self.test_started.emit(f"启动{app_type}应用: {target}")
            success = self.external_controller.create_controller(app_type, config)
            if not success:
                raise Exception(f"无法启动目标应用")
            
            self.external_controller.launch(target)
            
            # 3. AI分析应用
            self.test_started.emit("AI分析应用中...")
            initial_analysis = self.ai_analyze_application()
            
            # 4. 执行AI测试
            self.test_started.emit("执行AI测试中...")
            test_results = self.execute_ai_testing(initial_analysis, config)
            
            # 5. 分析和修复
            self.test_started.emit("分析问题中...")
            problems = self.analyze_problems(test_results)
            
            fixes = []
            for problem in problems:
                fix = self.auto_fix_engine.generate_fix(problem)
                fixes.append(fix)
            
            # 完成
            self.test_completed.emit({
                "analysis": initial_analysis,
                "results": test_results,
                "problems": problems,
                "fixes": fixes
            })
            
        except Exception as e:
            logging.error(f"测试失败: {e}")
            self.test_completed.emit({"error": str(e)})
        
        finally:
            self.is_running = False
    
    def execute_ai_testing(self, initial_analysis: dict, config: dict) -> list:
        """执行AI测试"""
        strategy = config.get("strategy", "exploratory")
        test_goal = config.get("task", "全面测试这个应用")
        
        results = []
        
        # 根据策略选择测试方法
        if strategy == "exploratory":
            results = self.exploratory_testing(initial_analysis, test_goal)
        elif strategy == "functional":
            results = self.functional_testing(initial_analysis, config.get("functions", []))
        elif strategy == "usability":
            results = self.usability_testing(initial_analysis)
        elif strategy == "performance":
            results = self.performance_testing(initial_analysis)
        
        return results
    
    def exploratory_testing(self, initial_analysis: dict, test_goal: str) -> list:
        """探索性测试"""
        results = []
        
        # 获取初始状态
        current_state = self.visual_perception.perceive_ui_state()
        
        # 使用思维链驱动测试
        thought_chain = self.chain_of_thought.generate_thought_chain(
            test_goal, 
            current_state
        )
        
        for i, thought in enumerate(thought_chain):
            # 更新进度
            self.test_progress.emit({
                "step": i + 1,
                "total": len(thought_chain),
                "current_thought": thought
            })
            
            # 执行这一步
            result = self.chain_of_thought.execute_step(thought, current_state)
            results.append(result)
            
            # 更新状态
            current_state = self.visual_perception.perceive_ui_state()
            
            # 检测问题
            problems = self.problem_diagnoser.detect_problems(result)
            for problem in problems:
                self.problem_found.emit(problem)
        
        return results
```

---

## 四、思维链驱动测试

### 4.1 思维链生成与执行

```python
# core/ui_test_fix/thought_chain/chain_of_thought.py

class ChainOfThoughtTester:
    """
    思维链驱动的测试器
    
    AI思考如何完成任务，然后逐步执行
    """
    
    def __init__(self, llm_connector):
        self.llm = llm_connector
    
    def generate_thought_chain(self, goal: str, current_state: UIState) -> List[str]:
        """生成思维链"""
        
        # 构建提示
        prompt = f"""
        任务目标: {goal}
        
        当前应用状态:
        - 页面标题: {current_state.get('title', 'Unknown')}
        - 可交互元素: {len(current_state.get('elements', []))} 个
        - 主要功能区域: {current_state.get('main_regions', [])}
        
        请思考如何完成这个测试任务，生成一个清晰的步骤序列。
        每个步骤应该是原子性的、可执行的操作。
        
        格式要求:
        1. 使用中文描述
        2. 每个步骤一行
        3. 步骤格式: [步骤序号] 具体操作
        4. 考虑前置条件和预期结果
        """
        
        # 调用LLM生成思维链
        response = self.llm.generate(prompt)
        
        # 解析思维链
        thoughts = self.parse_thought_chain(response)
        
        return thoughts
    
    def execute_step(self, thought: str, current_state: UIState) -> StepResult:
        """执行思维链中的一步"""
        
        # 解析思考内容
        parsed = self.parse_thought(thought)
        
        # 确定动作类型
        action_type = parsed["action"]
        target = parsed.get("target")
        params = parsed.get("params", {})
        
        # 执行对应动作
        try:
            if action_type == "find":
                # 查找元素
                element = self.find_element(target, current_state)
                return StepResult(success=True, element=element, thought=thought)
            
            elif action_type == "click":
                # 点击元素
                element = self.find_element(target, current_state)
                element.click()
                return StepResult(success=True, action="click", target=target, thought=thought)
            
            elif action_type == "type":
                # 输入文本
                element = self.find_element(target, current_state)
                element.type_text(params["text"])
                return StepResult(success=True, action="type", target=target, thought=thought)
            
            elif action_type == "verify":
                # 验证条件
                condition_met = self.verify_condition(params["condition"], current_state)
                return StepResult(
                    success=condition_met, 
                    action="verify", 
                    condition=params["condition"],
                    result=condition_met,
                    thought=thought
                )
            
            elif action_type == "navigate":
                # 导航到页面
                self.navigate_to(params["url"])
                return StepResult(success=True, action="navigate", url=params["url"], thought=thought)
            
            elif action_type == "wait":
                # 等待
                time.sleep(params.get("duration", 1))
                return StepResult(success=True, action="wait", duration=params.get("duration"), thought=thought)
            
            else:
                return StepResult(
                    success=False, 
                    error=f"未知动作类型: {action_type}",
                    thought=thought
                )
        
        except Exception as e:
            return StepResult(success=False, error=str(e), thought=thought)
    
    def parse_thought(self, thought: str) -> dict:
        """解析思考内容"""
        # 简单解析：提取动作类型和目标
        # 实际应用中应该使用更智能的解析
        
        parsed = {"action": None, "target": None, "params": {}}
        
        thought_lower = thought.lower()
        
        if "点击" in thought or "click" in thought_lower:
            parsed["action"] = "click"
            parsed["target"] = self.extract_target(thought)
        elif "输入" in thought or "type" in thought_lower:
            parsed["action"] = "type"
            parsed["target"] = self.extract_target(thought)
            parsed["params"]["text"] = self.extract_text(thought)
        elif "查找" in thought or "find" in thought_lower:
            parsed["action"] = "find"
            parsed["target"] = self.extract_target(thought)
        elif "验证" in thought or "verify" in thought_lower:
            parsed["action"] = "verify"
            parsed["params"]["condition"] = self.extract_condition(thought)
        elif "导航" in thought or "navigate" in thought_lower:
            parsed["action"] = "navigate"
            parsed["params"]["url"] = self.extract_url(thought)
        elif "等待" in thought or "wait" in thought_lower:
            parsed["action"] = "wait"
            parsed["params"]["duration"] = self.extract_duration(thought)
        
        return parsed
```

---

## 五、问题诊断与修复

### 5.1 问题诊断器

```python
# core/ui_test_fix/diagnoser/ui_problem_diagnoser.py

class UIProblemDiagnoser:
    """
    UI问题诊断系统
    
    检测和分类UI问题
    """
    
    PROBLEM_CATEGORIES = {
        "functional": {
            "name": "功能性问题",
            "indicators": ["crash", "freeze", "error", "not_working", "无响应"]
        },
        "usability": {
            "name": "可用性问题", 
            "indicators": ["confusing", "unclear", "inconsistent", "困惑", "不清楚"]
        },
        "performance": {
            "name": "性能问题",
            "indicators": ["slow", "laggy", "loading", "延迟", "慢"]
        },
        "accessibility": {
            "name": "可访问性问题",
            "indicators": ["low_contrast", "small_text", "missing_alt", "对比度", "文本过小"]
        }
    }
    
    def __init__(self, llm_connector):
        self.llm = llm_connector
    
    def detect_problems(self, step_result: StepResult) -> List[UIProblem]:
        """检测问题"""
        problems = []
        
        # 1. 检查执行失败
        if not step_result.success:
            problems.append(UIProblem(
                type="functional",
                description=f"操作失败: {step_result.error}",
                severity="critical",
                evidence=step_result
            ))
        
        # 2. 检查异常状态
        state_after = step_result.state_after
        if state_after:
            problems.extend(self.check_functional_issues(state_after))
            problems.extend(self.check_usability_issues(state_after))
            problems.extend(self.check_performance_issues(state_after))
        
        # 3. AI深度分析
        ai_problems = await self.ai_analyze_problems(step_result)
        problems.extend(ai_problems)
        
        return problems
    
    async def ai_analyze_problems(self, step_result: StepResult) -> List[UIProblem]:
        """使用AI分析问题"""
        
        prompt = f"""
        请分析以下测试结果，识别潜在问题：
        
        测试步骤: {step_result.thought}
        执行结果: {'成功' if step_result.success else '失败'}
        错误信息: {step_result.error or '无'}
        
        当前页面截图: [已捕获]
        
        请检查以下方面:
        1. 功能是否正常
        2. 是否有可用性问题
        3. 是否有性能问题
        4. 是否有可访问性问题
        
        返回JSON格式的问题列表。
        """
        
        response = await self.llm.analyze(step_result.screenshot, prompt)
        
        # 解析AI响应
        problems = self.parse_ai_response(response)
        
        return problems
```

### 5.2 自动修复引擎

```python
# core/ui_test_fix/fix_engine/ui_auto_fix_engine.py

class UIAutoFixEngine:
    """
    UI自动修复引擎
    
    生成并应用修复方案
    """
    
    def __init__(self, llm_connector):
        self.llm = llm_connector
    
    def generate_fix(self, problem: UIProblem) -> FixProposal:
        """生成修复方案"""
        
        # 1. 根因分析
        root_cause = self.analyze_root_cause(problem)
        
        # 2. 选择修复策略
        strategy = self.select_fix_strategy(problem, root_cause)
        
        # 3. 生成修复代码
        fix_code = self.generate_fix_code(problem, strategy)
        
        # 4. 评估可行性
        feasibility = self.assess_feasibility(fix_code, problem)
        
        return FixProposal(
            problem=problem,
            root_cause=root_cause,
            strategy=strategy,
            fix_code=fix_code,
            feasibility=feasibility,
            estimated_effort=self.estimate_effort(fix_code),
            risk_level=self.assess_risk(fix_code)
        )
    
    def analyze_root_cause(self, problem: UIProblem) -> RootCause:
        """分析问题根因"""
        
        # 使用AI分析
        prompt = f"""
        分析以下问题的根本原因：
        
        问题: {problem.description}
        类型: {problem.type}
        严重性: {problem.severity}
        
        请提供:
        1. 最可能的根本原因
        2. 相关的代码位置
        3. 修复建议
        """
        
        response = self.llm.analyze(prompt)
        
        return RootCause(
            cause=response["root_cause"],
            confidence=response["confidence"],
            evidence=response["evidence"]
        )
    
    def generate_fix_code(self, problem: UIProblem, strategy: str) -> str:
        """生成修复代码"""
        
        # 根据问题类型生成不同的修复代码
        if problem.type == "functional":
            return self.generate_functional_fix(problem)
        elif problem.type == "usability":
            return self.generate_usability_fix(problem)
        elif problem.type == "performance":
            return self.generate_performance_fix(problem)
        elif problem.type == "accessibility":
            return self.generate_accessibility_fix(problem)
        
        return "// 暂无可用修复方案"
```

---

## 六、完整工作流示例

### 场景：测试淘宝购物流程

```
1️⃣ 用户在PyQt6界面配置：
   ├─ 目标类型：Web应用
   ├─ URL：https://www.taobao.com
   ├─ 测试策略：探索性测试
   ├─ 任务：完整测试购物流程
   └─ 点击"开始测试"

2️⃣ PyQt6客户端启动：
   ├─ 打开Chrome浏览器
   ├─ 访问目标网站
   └─ 在PyQt6界面显示实时屏幕

3️⃣ AI开始测试：
   ├─ AI分析首页
   │  ├─ 识别搜索框
   │  ├─ 识别导航菜单
   │  └─ 识别登录入口
   │
   ├─ 思维链生成：
   │  ├─ [1] 找到搜索框
   │  ├─ [2] 输入"手机"
   │  ├─ [3] 点击搜索按钮
   │  ├─ [4] 等待结果加载
   │  ├─ [5] 点击第一个商品
   │  └─ [6] 验证商品详情
   │
   └─ 逐步执行并显示进度

4️⃣ 发现问题：
   ├─ 问题1：搜索按钮点击无响应
   │  ├─ 类型：功能性
   │  ├─ 严重性：严重
   │  └─ 证据：[截图]
   │
   └─ 问题2：商品图片加载慢
      ├─ 类型：性能
      ├─ 严重性：警告
      └─ 证据：[截图]

5️⃣ 提出修复：
   ├─ 问题1修复：
   │  ├─ 根因：JavaScript事件绑定失败
   │  ├─ 建议：检查事件监听器
   │  └─ 代码：element.addEventListener(...)
   │
   └─ 问题2修复：
      ├─ 根因：图片未压缩
      ├─ 建议：使用WebP格式
      └─ 代码：src="image.webp"

6️⃣ 用户决策：
   ├─ 查看修复建议
   ├─ 复制修复代码
   └─ 或点击"应用修复"

7️⃣ 验证修复：
   ├─ AI重新测试
   ├─ 验证问题已解决
   └─ 生成测试报告
```

---

## 七、实施路径

### 阶段1：基础自动化（2周）

| 周次 | 任务 | 交付物 |
|------|------|--------|
| 第1周 | PyQt6控制台框架 | 主界面、控制面板 |
| 第2周 | 外部控制器 | Web/桌面控制器 |

### 阶段2：智能测试（3周）

| 周次 | 任务 | 交付物 |
|------|------|--------|
| 第3周 | 视觉感知层 | 屏幕捕获、元素识别 |
| 第4周 | 思维链系统 | 思维链生成、执行 |
| 第5周 | 问题诊断 | 问题检测、分类 |

### 阶段3：问题诊断（4周）

| 周次 | 任务 | 交付物 |
|------|------|--------|
| 第6周 | 根因分析 | 根因分析器 |
| 第7周 | 修复引擎 | 修复方案生成 |
| 第8-9周 | 集成测试 | 完整流程测试 |

### 阶段4：自动修复（4周）

| 周次 | 任务 | 交付物 |
|------|------|--------|
| 第10周 | 修复执行 | 自动修复系统 |
| 第11周 | 验证测试 | 修复验证 |
| 第12-13周 | 优化完善 | 性能优化、用户体验 |

---

## 八、技术栈

### 核心技术

| 技术 | 用途 |
|------|------|
| PyQt6 | 控制台UI框架 |
| Selenium/Playwright | Web自动化 |
| PyAutoGUI | 桌面自动化 |
| Appium | 移动端自动化 |
| OpenCV | 视觉识别 |
| OCR | 文本提取 |
| LLM API | AI分析 |

### 可复用现有模块

| 模块 | 复用方式 |
|------|---------|
| browser_use_adapter.py | 浏览器控制能力 |
| browser_pool.py | 多浏览器管理 |
| browser_automation_guide.py | 引导自动化 |

---

## 九、总结

### 核心价值

1. **非侵入式测试** - PyQt6作为控制台，不修改被测应用
2. **可视化过程** - 实时监控测试全程
3. **AI驱动决策** - 思维链驱动的智能测试
4. **自动修复能力** - 不仅发现问题，还能修复

### 最终形态

用户只需要在PyQt6界面输入"测试淘宝购物流程"，AI就能：

1. 自动打开浏览器
2. 完成完整的购物流程测试
3. 发现并分析问题
4. 生成修复建议
5. 全程在PyQt6界面可视化展示

---

**文档版本**: 2.0.0  
**更新日期**: 2026-04-26  
**状态**: 已完成设计
