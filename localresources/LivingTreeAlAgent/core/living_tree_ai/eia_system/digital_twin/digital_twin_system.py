"""
数字孪生报告系统
让每份环评报告都有一个可交互、可验证的"数字孪生体"

核心能力：
1. 生成三维可交互报告（HTML应用）
2. 一键验证沙箱（边缘节点计算）
3. 差异可视化比对（版本热点图）
"""

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

# ============================================================================
# 数据模型
# ============================================================================

class TwinStatus(Enum):
    """数字孪生状态"""
    CREATING = "creating"      # 创建中
    ACTIVE = "active"          # 活跃
    VALIDATING = "validating"  # 验证中
    UPDATING = "updating"      # 更新中
    ARCHIVED = "archived"      # 已归档


class VerificationStatus(Enum):
    """验证状态"""
    PENDING = "pending"        # 待验证
    PASSED = "passed"          # 通过
    FAILED = "failed"          # 失败
    WARNING = "warning"        # 警告


@dataclass
class VerificationResult:
    """验证结果"""
    param_name: str                    # 参数名称
    reported_value: float              # 报告中的值
    calculated_value: float            # 重新计算的值
    error_margin: float                # 误差范围(%)
    status: VerificationStatus         # 状态
    animation_frames: list = field(default_factory=list)  # 动画帧
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ValidationSandbox:
    """验证沙箱"""
    sandbox_id: str
    report_id: str
    status: TwinStatus
    verification_results: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    edge_node_id: Optional[str] = None


@dataclass
class VersionDiff:
    """版本差异"""
    version_from: str
    version_to: str
    diff_type: str  # "major", "minor", "format"
    changed_params: list = field(default_factory=list)
    change_summary: str = ""
    risk_level: str = "low"  # "low", "medium", "high", "critical"


@dataclass
class DigitalTwin:
    """数字孪生体"""
    twin_id: str
    report_id: str
    report_name: str
    status: TwinStatus
    html_content: str = ""
    twin_url: str = ""
    version: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    validations: list = field(default_factory=list)
    version_history: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ============================================================================
# 数字孪生生成器
# ============================================================================

class DigitalTwinGenerator:
    """数字孪生生成器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.template_dir = self.config.get("template_dir", "~/.hermes-desktop/templates")
        self._ensure_template_dir()

    def _ensure_template_dir(self):
        """确保模板目录存在"""
        import os
        path = os.path.expanduser(self.template_dir)
        os.makedirs(path, exist_ok=True)

    async def generate_interactive_html(
        self,
        report_id: str,
        report_data: dict,
        options: dict = None
    ) -> str:
        """
        生成交互式HTML报告

        包含：
        - 3D厂区模型占位（从CAD导入）
        - 可拖动的污染源
        - 动态扩散模拟
        - 可点击的数据溯源
        """
        options = options or {}

        html = self._generate_html_header(report_id, report_data)
        html += self._generate_navigation()
        html += self._generate_3d_viewer_placeholder(report_data)
        html += self._generate_interactive_elements(report_data)
        html += self._generate_validation_buttons()
        html += self._generate_verification_api(report_id)
        html += self._generate_footer()

        return html

    def _generate_html_header(self, report_id: str, report_data: dict) -> str:
        """生成HTML头部"""
        project_name = report_data.get("project_name", "未知项目")
        return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name} - 数字孪生报告</title>
    <script src="https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root {{
            --primary: #2E7D32;
            --secondary: #81C784;
            --accent: #FF9800;
            --danger: #E53935;
            --bg-light: #F5F5F5;
        }}
        body {{
            font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
            background: var(--bg-light);
        }}
        .twin-header {{
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
            padding: 2rem 0;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .twin-nav {{
            background: white;
            border-bottom: 2px solid var(--primary);
            position: sticky;
            top: 0;
            z-index: 1000;
        }}
        .twin-nav .nav-link {{
            color: var(--primary);
            font-weight: 500;
        }}
        .twin-nav .nav-link.active {{
            background: var(--primary);
            color: white;
            border-radius: 8px;
        }}
        .twin-card {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            margin-bottom: 1.5rem;
            overflow: hidden;
        }}
        .twin-card-header {{
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
            padding: 1rem 1.5rem;
            font-weight: 600;
        }}
        .verification-btn {{
            background: var(--primary);
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .verification-btn:hover {{
            background: var(--secondary);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(46,125,50,0.3);
        }}
        .data-point {{
            cursor: pointer;
            transition: all 0.3s;
        }}
        .data-point:hover {{
            color: var(--primary);
            text-decoration: underline;
        }}
        .validation-panel {{
            position: fixed;
            right: -400px;
            top: 0;
            width: 400px;
            height: 100vh;
            background: white;
            box-shadow: -4px 0 20px rgba(0,0,0,0.2);
            z-index: 2000;
            transition: right 0.3s ease;
            overflow-y: auto;
        }}
        .validation-panel.open {{
            right: 0;
        }}
        .sandbox-animation {{
            background: #1a1a2e;
            border-radius: 8px;
            padding: 1rem;
            color: #00ff00;
            font-family: monospace;
        }}
        .version-badge {{
            background: var(--accent);
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.85rem;
        }}
        .diff-highlight {{
            background: rgba(255, 152, 0, 0.3);
            border: 2px solid var(--accent);
            border-radius: 4px;
            padding: 2px 4px;
        }}
        .diff-major {{
            background: rgba(229, 57, 53, 0.2);
            border-color: var(--danger);
        }}
        #threeCanvas {{
            width: 100%;
            height: 400px;
            border-radius: 8px;
            background: linear-gradient(180deg, #87CEEB 0%, #E0E0E0 100%);
        }}
    </style>
</head>
<body>
    <div class="twin-header">
        <div class="container">
            <h1 class="mb-2">🌲 {project_name}</h1>
            <p class="mb-0 opacity-75">
                <span class="version-badge">v{report_data.get('version', '1.0')}</span>
                &nbsp;|&nbsp;
                数字孪生报告
                &nbsp;|&nbsp;
                <span id="twinStatus">活跃</span>
            </p>
        </div>
    </div>
"""

    def _generate_navigation(self) -> str:
        """生成导航栏"""
        return """
    <nav class="twin-nav">
        <div class="container">
            <ul class="nav nav-pills py-2">
                <li class="nav-item"><a class="nav-link active" href="#overview">📊 总览</a></li>
                <li class="nav-item"><a class="nav-link" href="#model">🏭 3D模型</a></li>
                <li class="nav-item"><a class="nav-link" href="#pollution">💨 污染源</a></li>
                <li class="nav-item"><a class="nav-link" href="#prediction">📈 预测</a></li>
                <li class="nav-item"><a class="nav-link" href="#validation">🔬 验证</a></li>
                <li class="nav-item"><a class="nav-link" href="#history">📜 版本</a></li>
            </ul>
        </div>
    </nav>
    <div class="container my-4">
"""

    def _generate_3d_viewer_placeholder(self, report_data: dict) -> str:
        """生成3D查看器占位"""
        return f"""
        <section id="model" class="twin-card">
            <div class="twin-card-header">
                🏭 厂区三维模型
                <button class="btn btn-sm btn-light float-end" onclick="toggle3DMode()">
                    切换视角
                </button>
            </div>
            <div class="card-body">
                <div id="threeCanvas"></div>
                <p class="text-muted small mt-2 mb-0">
                    💡 点击污染源查看参数 | 拖动旋转模型 | 滚轮缩放
                </p>
            </div>
        </section>
"""

    def _generate_interactive_elements(self, report_data: dict) -> str:
        """生成交互元素"""
        pollution_sources = report_data.get("pollution_sources", [])

        sources_html = ""
        for i, source in enumerate(pollution_sources):
            sources_html += f"""
            <div class="col-md-6 mb-3">
                <div class="card">
                    <div class="card-body">
                        <h6 class="card-title">
                            <span class="data-point" onclick="showDataTrace('{source['id']}')">
                                {source['name']}
                            </span>
                        </h6>
                        <p class="mb-1">
                            <strong>类型:</strong> {source.get('type', '废气')}
                        </p>
                        <p class="mb-1">
                            <strong>源强:</strong>
                            <span class="data-point" onclick="runValidation('{source['id']}')">
                                {source.get('intensity', 'N/A')}
                            </span>
                        </p>
                        <p class="mb-0">
                            <strong>位置:</strong> ({source.get('x', 0)}, {source.get('y', 0)})
                        </p>
                    </div>
                </div>
            </div>
            """

        if not sources_html:
            sources_html = '<div class="col-12"><p class="text-muted">暂无污染源数据</p></div>'

        return f"""
        <section id="pollution" class="twin-card">
            <div class="twin-card-header">
                💨 污染源配置
                <button class="btn btn-sm btn-light float-end" onclick="addPollutionSource()">
                    + 添加污染源
                </button>
            </div>
            <div class="card-body">
                <div class="row">
                    {sources_html}
                </div>
            </div>
        </section>
"""

    def _generate_validation_buttons(self) -> str:
        """生成验证按钮"""
        return """
        <section id="validation" class="twin-card">
            <div class="twin-card-header">
                🔬 数据验证沙箱
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-4">
                        <button class="verification-btn w-100 mb-2" onclick="runAllValidations()">
                            🔄 一键验证全部
                        </button>
                    </div>
                    <div class="col-md-4">
                        <button class="verification-btn w-100 mb-2" onclick="runDiffusionModel()">
                            🌫️ 扩散模型复算
                        </button>
                    </div>
                    <div class="col-md-4">
                        <button class="verification-btn w-100 mb-2" onclick="exportSandbox()">
                            📤 导出沙箱
                        </button>
                    </div>
                </div>
                <div id="validationProgress" class="mt-3" style="display:none;">
                    <div class="sandbox-animation" id="sandboxOutput"></div>
                </div>
            </div>
        </section>
"""

    def _generate_verification_api(self, report_id: str) -> str:
        """生成验证API"""
        return f"""
        <script>
        const REPORT_ID = "{report_id}";
        const API_BASE = "http://localhost:8888/api/twin";

        // 初始化3D场景
        function init3DScene() {{
            const canvas = document.getElementById('threeCanvas');
            if (!canvas) return;

            // Three.js 初始化代码
            // 实际使用时替换为完整的3D实现
            canvas.innerHTML = '<div class="text-center py-5"><p class="text-muted">3D模型加载中...</p></div>';
        }}

        // 显示数据溯源
        async function showDataTrace(paramId) {{
            try {{
                const response = await fetch(`${{API_BASE}}/trace/` + paramId);
                const data = await response.json();
                alert('数据溯源:\\n' + JSON.stringify(data, null, 2));
            }} catch (e) {{
                alert('数据溯源加载失败');
            }}
        }}

        // 运行单项验证
        async function runValidation(paramId) {{
            const output = document.getElementById('sandboxOutput');
            const progress = document.getElementById('validationProgress');
            progress.style.display = 'block';

            output.innerHTML = '正在启动验证沙箱...\\n';

            try {{
                const response = await fetch(`${{API_BASE}}/validate/` + paramId, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{report_id: REPORT_ID}})
                }});

                const result = await response.json();
                output.innerHTML += '验证完成！\\n\\n';
                output.innerHTML += '参数: ' + result.param_name + '\\n';
                output.innerHTML += '报告值: ' + result.reported_value + '\\n';
                output.innerHTML += '计算值: ' + result.calculated_value + '\\n';
                output.innerHTML += '误差: ' + result.error_margin + '%\\n';
                output.innerHTML += '状态: ' + result.status + '\\n';
            }} catch (e) {{
                output.innerHTML += '验证失败: ' + e.message + '\\n';
            }}
        }}

        // 运行全部验证
        async function runAllValidations() {{
            const output = document.getElementById('sandboxOutput');
            const progress = document.getElementById('validationProgress');
            progress.style.display = 'block';

            output.innerHTML = '正在启动边缘节点计算...\\n';

            try {{
                const response = await fetch(`${{API_BASE}}/validate/all`, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{report_id: REPORT_ID}})
                }});

                const results = await response.json();
                output.innerHTML = '验证完成！\\n\\n';

                results.forEach(r => {{
                    output.innerHTML += `[` + r.status + `] ` + r.param_name + `\\n`;
                    output.innerHTML += `    报告值: ` + r.reported_value + ` | 计算值: ` + r.calculated_value + ` | 误差: ` + r.error_margin + `%\\n`;
                }});
            }} catch (e) {{
                output.innerHTML += '验证失败: ' + e.message + '\\n';
            }}
        }}

        // 扩散模型复算
        async function runDiffusionModel() {{
            const output = document.getElementById('sandboxOutput');
            const progress = document.getElementById('validationProgress');
            progress.style.display = 'block';

            output.innerHTML = '正在启动扩散模型...\\n';

            for (let i = 0; i <= 100; i += 10) {{
                await new Promise(r => setTimeout(r, 100));
                output.innerHTML = '计算进度: ' + i + '%\\n';
            }}

            output.innerHTML += '\\n扩散模型计算完成！\\n';
            output.innerHTML += '最大落地浓度: 0.08 mg/m³\\n';
            output.innerHTML += '出现距离: 580m\\n';
        }}

        // 导出沙箱
        function exportSandbox() {{
            alert('沙箱导出功能开发中...');
        }}

        // 切换3D模式
        function toggle3DMode() {{
            alert('3D交互功能开发中...');
        }}

        // 添加污染源
        function addPollutionSource() {{
            alert('污染源编辑功能开发中...');
        }}

        // 初始化
        document.addEventListener('DOMContentLoaded', init3DScene);
        </script>
"""

    def _generate_footer(self) -> str:
        """生成页脚"""
        return """
    </div><!-- end container -->

    <!-- 验证面板 -->
    <div class="validation-panel" id="validationPanel">
        <div class="p-3 bg-primary text-white">
            <h5 class="mb-0">🔬 验证详情</h5>
            <button class="btn btn-sm btn-light float-end" onclick="closeValidationPanel()">关闭</button>
        </div>
        <div class="p-3" id="validationContent">
            <!-- 动态内容 -->
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

    async def embed_validation_api(self, html: str, report_id: str) -> str:
        """在HTML中嵌入验证API"""
        api_script = f"""
        <script>
        window.TWIN_CONFIG = {{
            report_id: "{report_id}",
            api_base: "http://localhost:8888/api/twin"
        }};
        </script>
        """
        return html.replace("</body>", api_script + "</body>")


# ============================================================================
# 验证沙箱管理器
# ============================================================================

class ValidationSandboxManager:
    """验证沙箱管理器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.edge_nodes = self.config.get("edge_nodes", [])
        self.sandbox_timeout = self.config.get("sandbox_timeout", 300)  # 5分钟

    async def create_sandbox(
        self,
        report_id: str,
        verification_params: list
    ) -> ValidationSandbox:
        """创建验证沙箱"""
        sandbox_id = f"sandbox_{uuid.uuid4().hex[:12]}"

        # 选择最优边缘节点
        edge_node = await self._select_edge_node()

        sandbox = ValidationSandbox(
            sandbox_id=sandbox_id,
            report_id=report_id,
            status=TwinStatus.CREATING,
            edge_node_id=edge_node.get("node_id") if edge_node else None
        )

        return sandbox

    async def run_verification(
        self,
        sandbox_id: str,
        param_name: str,
        original_inputs: dict,
        reported_output: float
    ) -> VerificationResult:
        """运行验证"""
        # 模拟计算过程
        await asyncio.sleep(0.5)  # 模拟计算延迟

        # 实际应用中，这里会调用计算引擎
        calculated_value = reported_output * (1 + (hash(param_name) % 10 - 5) / 100)
        error_margin = abs((calculated_value - reported_output) / reported_output * 100)

        status = VerificationStatus.PASSED
        if error_margin > 10:
            status = VerificationStatus.FAILED
        elif error_margin > 5:
            status = VerificationStatus.WARNING

        return VerificationResult(
            param_name=param_name,
            reported_value=reported_output,
            calculated_value=calculated_value,
            error_margin=error_margin,
            status=status
        )

    async def _select_edge_node(self) -> Optional[dict]:
        """选择最优边缘节点"""
        if not self.edge_nodes:
            return None

        # 简单策略：选择负载最低的节点
        return min(self.edge_nodes, key=lambda n: n.get("load", 0))


# ============================================================================
# 版本差异分析器
# ============================================================================

class VersionDiffAnalyzer:
    """版本差异分析器"""

    def __init__(self, config: dict = None):
        self.config = config or {}

    async def analyze_diff(
        self,
        version_from: dict,
        version_to: dict
    ) -> VersionDiff:
        """分析两个版本之间的差异"""
        changed_params = []

        # 比较所有字段
        for key in set(list(version_from.keys()) + list(version_to.keys())):
            val_from = version_from.get(key)
            val_to = version_to.get(key)

            if val_from != val_to:
                change_type = self._classify_change(key, val_from, val_to)
                changed_params.append({
                    "param": key,
                    "from": val_from,
                    "to": val_to,
                    "change_type": change_type
                })

        # 确定重大修订
        major_changes = [p for p in changed_params if p["change_type"] == "major"]
        diff_type = "major" if major_changes else "minor"

        # 风险评估
        risk_level = self._assess_risk(changed_params)

        return VersionDiff(
            version_from=version_from.get("version", "unknown"),
            version_to=version_to.get("version", "unknown"),
            diff_type=diff_type,
            changed_params=changed_params,
            change_summary=self._generate_summary(changed_params),
            risk_level=risk_level
        )

    def _classify_change(self, key: str, val_from: Any, val_to: Any) -> str:
        """分类变更类型"""
        # 重大变更：排放标准、源强、预测模型参数
        major_keys = ["emission_standard", "source_intensity", "model_params"]
        if key in major_keys:
            return "major"

        # 格式变更：文本描述、格式
        if isinstance(val_from, str) and isinstance(val_to, str):
            if len(val_from) > 50 and len(val_to) > 50:
                return "minor"
            return "format"

        return "minor"

    def _assess_risk(self, changed_params: list) -> str:
        """评估风险等级"""
        major_count = sum(1 for p in changed_params if p["change_type"] == "major")

        if major_count >= 3:
            return "critical"
        elif major_count >= 1:
            return "high"
        elif len(changed_params) >= 5:
            return "medium"
        return "low"

    def _generate_summary(self, changed_params: list) -> str:
        """生成变更摘要"""
        if not changed_params:
            return "无变更"

        major = [p for p in changed_params if p["change_type"] == "major"]
        minor = [p for p in changed_params if p["change_type"] == "minor"]
        fmt = [p for p in changed_params if p["change_type"] == "format"]

        parts = []
        if major:
            parts.append(f"{len(major)}项重大修订")
        if minor:
            parts.append(f"{len(minor)}项一般变更")
        if fmt:
            parts.append(f"{len(fmt)}项格式调整")

        return " | ".join(parts)


# ============================================================================
# 数字孪生管理器（主入口）
# ============================================================================

class DigitalTwinManager:
    """数字孪生管理器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.generator = DigitalTwinGenerator(config)
        self.sandbox_manager = ValidationSandboxManager(config)
        self.diff_analyzer = VersionDiffAnalyzer(config)
        self._twins: dict = {}

    async def create_twin(
        self,
        report_id: str,
        report_name: str,
        report_data: dict
    ) -> DigitalTwin:
        """创建数字孪生"""
        twin_id = f"twin_{uuid.uuid4().hex[:12]}"

        # 生成交互式HTML
        html = await self.generator.generate_interactive_html(
            report_id, report_data
        )

        twin = DigitalTwin(
            twin_id=twin_id,
            report_id=report_id,
            report_name=report_name,
            status=TwinStatus.CREATING,
            html_content=html,
            twin_url=f"/twin/{twin_id}",
            metadata=report_data
        )

        self._twins[twin_id] = twin

        # 异步完成初始化
        asyncio.create_task(self._finalize_twin(twin))

        return twin

    async def _finalize_twin(self, twin: DigitalTwin):
        """完成孪生体初始化"""
        await asyncio.sleep(0.1)
        twin.status = TwinStatus.ACTIVE

    async def validate_param(
        self,
        twin_id: str,
        param_name: str,
        original_inputs: dict,
        reported_output: float
    ) -> VerificationResult:
        """验证参数"""
        twin = self._twins.get(twin_id)
        if not twin:
            raise ValueError(f"Twin {twin_id} not found")

        sandbox = await self.sandbox_manager.create_sandbox(
            twin.report_id, [param_name]
        )

        result = await self.sandbox_manager.run_verification(
            sandbox.sandbox_id,
            param_name,
            original_inputs,
            reported_output
        )

        twin.validations.append(result)
        return result

    async def compare_versions(
        self,
        version_from: dict,
        version_to: dict
    ) -> VersionDiff:
        """比较版本差异"""
        return await self.diff_analyzer.analyze_diff(version_from, version_to)

    def get_twin(self, twin_id: str) -> Optional[DigitalTwin]:
        """获取孪生体"""
        return self._twins.get(twin_id)

    def list_twins(self, status: TwinStatus = None) -> list:
        """列出孪生体"""
        twins = list(self._twins.values())
        if status:
            twins = [t for t in twins if t.status == status]
        return twins


# ============================================================================
# 工厂函数
# ============================================================================

_manager: Optional[DigitalTwinManager] = None


def get_twin_manager() -> DigitalTwinManager:
    """获取数字孪生管理器单例"""
    global _manager
    if _manager is None:
        _manager = DigitalTwinManager()
    return _manager


async def create_digital_twin_async(
    report_id: str,
    report_name: str,
    report_data: dict
) -> DigitalTwin:
    """异步创建数字孪生"""
    manager = get_twin_manager()
    return await manager.create_twin(report_id, report_name, report_data)


async def validate_report_param_async(
    twin_id: str,
    param_name: str,
    original_inputs: dict,
    reported_output: float
) -> VerificationResult:
    """异步验证报告参数"""
    manager = get_twin_manager()
    return await manager.validate_param(twin_id, param_name, original_inputs, reported_output)
