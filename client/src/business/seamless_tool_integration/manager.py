"""
Seamless Integration Manager - 无缝集成管理器

统一管理所有外部工具的：
- 部署
- 执行
- 结果处理
- 可视化
"""

import os
import tempfile
import shutil
from typing import Optional, Dict, List, Any, Callable
from pathlib import Path

# 导入核心组件
from .model_deployer import ModelDeployer, ToolInfo, ToolType, DeploymentProgress
from .input_generator import InputGenerator, ProjectData, AermodInputGenerator
from .tool_executor import ToolExecutor, ExecutionResult, ExecutionStatus, ExecutionStep
from .result_parser import ResultParser, PredictionResult, ReportGenerator
from .result_visualizer import ResultVisualizer
from .cloud_bridge import CloudBridge, CloudExecutionMode, LocalCapabilityDetector


class SeamlessIntegrationManager:
    """
    无缝集成管理器

    提供一键式外部工具使用体验

    使用示例：
    ```python
    manager = SeamlessIntegrationManager.get_instance()

    # 初始化（只需一次）
    manager.initialize()

    # 创建项目数据
    project = ProjectData(
        project_name="南京XX化工厂",
        latitude=32.04,
        longitude=118.78,
        pollutants=["SO2", "NO2", "PM25"]
    )
    # ... 设置更多参数

    # 一键运行预测
    result = manager.run_prediction(
        project_data=project,
        tool_type="aermod",
        progress_callback=lambda step: print(f"{step.name}: {step.progress}%")
    )

    # 获取可视化
    viz = manager.get_visualization(result)
    contour_fig = viz.get_contour_map("PM25")

    # 生成报告
    report = manager.generate_report(result, "text")
    ```
    """

    _instance: Optional["SeamlessIntegrationManager"] = None

    @classmethod
    def get_instance(cls) -> "SeamlessIntegrationManager":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置实例（用于测试）"""
        cls._instance = None

    def __init__(self):
        # 核心组件
        self.deployer = ModelDeployer()
        self.cloud_bridge = CloudBridge()

        # 工作目录
        self.work_dir = tempfile.mkdtemp(prefix="hermes_air_")

        # 回调
        self._progress_callback: Optional[Callable] = None
        self._log_callback: Optional[Callable] = None

        # 缓存
        self._current_result: Optional[PredictionResult] = None
        self._current_project: Optional[ProjectData] = None

        # 状态
        self._initialized = False

    def initialize(self, tools_dir: Optional[str] = None):
        """
        初始化管理器

        Args:
            tools_dir: 工具安装目录
        """
        if tools_dir:
            self.deployer = ModelDeployer(tools_dir=tools_dir)

        self._initialized = True

    def set_progress_callback(self, callback: Callable):
        """设置进度回调"""
        self._progress_callback = callback

    def set_log_callback(self, callback: Callable):
        """设置日志回调"""
        self._log_callback = callback

    def _log(self, message: str, level: str = "INFO"):
        """内部日志"""
        if self._log_callback:
            self._log_callback(f"[{level}] {message}")

    def check_tool_ready(self, tool_type: str = "aermod") -> bool:
        """
        检查工具是否就绪

        Args:
            tool_type: 工具类型

        Returns:
            是否就绪
        """
        return self.deployer.is_tool_ready(tool_type)

    def ensure_tool_ready(
        self,
        tool_type: str = "aermod",
        force_reinstall: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        确保工具已安装

        Args:
            tool_type: 工具类型
            force_reinstall: 是否强制重装
            progress_callback: 进度回调

        Returns:
            是否成功
        """
        if self.check_tool_ready(tool_type) and not force_reinstall:
            return True

        self._log(f"正在部署 {tool_type}...")

        def on_progress(progress: DeploymentProgress):
            if progress_callback:
                progress_callback(progress)

        return self.deployer.deploy(tool_type, force_reinstall, on_progress)

    def run_prediction(
        self,
        project_data: ProjectData,
        tool_type: str = "aermod",
        use_cloud: CloudExecutionMode = CloudExecutionMode.AUTO,
        force_local: bool = False,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> PredictionResult:
        """
        运行预测

        一键完成：部署 -> 生成输入 -> 执行 -> 解析结果

        Args:
            project_data: 项目数据
            tool_type: 工具类型
            use_cloud: 云端执行模式
            force_local: 强制本地执行
            progress_callback: 进度回调

        Returns:
            PredictionResult
        """
        self._current_project = project_data
        self._log(f"开始预测任务: {project_data.project_name}")

        # 步骤1：决定执行方式
        if force_local:
            execution_mode = CloudExecutionMode.OFF
        else:
            execution_mode = use_cloud

        # 检测本地能力
        local_cap = self.cloud_bridge.detect_local_capability()
        should_cloud = self.cloud_bridge.should_use_cloud(
            tool_type, execution_mode, 30
        )

        if should_cloud and not force_local:
            self._log("将使用云端计算")
            return self._run_cloud_prediction(project_data, tool_type, progress_callback)
        else:
            self._log("将使用本地计算")
            return self._run_local_prediction(project_data, tool_type, progress_callback)

    def _run_local_prediction(
        self,
        project_data: ProjectData,
        tool_type: str,
        progress_callback: Optional[Callable]
    ) -> PredictionResult:
        """本地预测"""

        # 创建临时工作目录
        task_dir = os.path.join(self.work_dir, f"task_{project_data.project_name}")
        os.makedirs(task_dir, exist_ok=True)

        try:
            # 步骤1：部署工具
            self._log("步骤 1/4: 检查工具部署...")
            if progress_callback:
                progress_callback(ExecutionStep(
                    step_id="deploy",
                    name="检查工具部署",
                    status=ExecutionStatus.RUNNING,
                    progress=0
                ))

            if not self.ensure_tool_ready(tool_type):
                raise Exception(f"工具部署失败: {tool_type}")

            tool_info = self.deployer.get_tool_info(tool_type)
            if not tool_info:
                raise Exception(f"未知工具: {tool_type}")

            if progress_callback:
                progress_callback(ExecutionStep(
                    step_id="deploy",
                    name="检查工具部署",
                    status=ExecutionStatus.COMPLETED,
                    progress=100
                ))

            # 步骤2：生成输入文件
            self._log("步骤 2/4: 生成输入文件...")
            if progress_callback:
                progress_callback(ExecutionStep(
                    step_id="input",
                    name="生成输入文件",
                    status=ExecutionStatus.RUNNING,
                    progress=0
                ))

            generator = InputGenerator.create(tool_type, project_data)
            files = generator.generate(task_dir)

            if progress_callback:
                progress_callback(ExecutionStep(
                    step_id="input",
                    name="生成输入文件",
                    status=ExecutionStatus.COMPLETED,
                    progress=100
                ))

            # 步骤3：执行模型
            self._log("步骤 3/4: 运行模型...")
            if progress_callback:
                progress_callback(ExecutionStep(
                    step_id="run",
                    name="运行模型",
                    status=ExecutionStatus.RUNNING,
                    progress=0
                ))

            executor = ToolExecutor()
            if self._log_callback:
                executor.set_log_callback(lambda e: self._log(e.to_string()))

            input_file = files.get('input', os.path.join(task_dir, f"{tool_type}.inp"))
            exe_path = tool_info.executable_path

            result = executor.execute(
                tool_path=exe_path,
                args=[input_file],
                work_dir=task_dir,
                timeout=kwargs.get('timeout', 7200)
            )

            if not result.success:
                raise Exception(f"模型运行失败: {result.error_message}")

            if progress_callback:
                progress_callback(ExecutionStep(
                    step_id="run",
                    name="运行模型",
                    status=ExecutionStatus.COMPLETED,
                    progress=100
                ))

            # 步骤4：解析结果
            self._log("步骤 4/4: 解析结果...")
            if progress_callback:
                progress_callback(ExecutionStep(
                    step_id="parse",
                    name="解析结果",
                    status=ExecutionStatus.RUNNING,
                    progress=0
                ))

            output_file = result.output_files.get('output')
            if not output_file:
                output_file = os.path.join(task_dir, f"{project_data.project_name}.out")

            prediction_result = ResultParser.parse_auto(output_file, tool_type)
            prediction_result.project_name = project_data.project_name
            prediction_result.metadata = {
                "tool_path": exe_path,
                "work_dir": task_dir,
                "execution_time": result.execution_time,
                "local_capability": self.cloud_bridge.local_capability
            }

            if progress_callback:
                progress_callback(ExecutionStep(
                    step_id="parse",
                    name="解析结果",
                    status=ExecutionStatus.COMPLETED,
                    progress=100
                ))

            self._current_result = prediction_result
            self._log(f"预测完成！最大浓度: {prediction_result.max_concentration:.2f}")

            return prediction_result

        except Exception as e:
            self._log(f"预测失败: {str(e)}", "ERROR")
            raise

    def _run_cloud_prediction(
        self,
        project_data: ProjectData,
        tool_type: str,
        progress_callback: Optional[Callable]
    ) -> PredictionResult:
        """云端预测"""
        self._log("云端计算暂未实现，将回退到本地计算")

        # 回退到本地
        return self._run_local_prediction(project_data, tool_type, progress_callback)

    def get_visualization(self, result: Optional[PredictionResult] = None) -> ResultVisualizer:
        """
        获取可视化工具

        Args:
            result: 预测结果，如果为None则使用当前结果

        Returns:
            ResultVisualizer
        """
        target_result = result or self._current_result
        if target_result is None:
            raise ValueError("没有可用的预测结果")
        return ResultVisualizer(target_result)

    def generate_report(
        self,
        result: Optional[PredictionResult] = None,
        format: str = "text"
    ) -> str:
        """
        生成报告

        Args:
            result: 预测结果
            format: 报告格式 (text/json/html)

        Returns:
            报告内容
        """
        target_result = result or self._current_result
        if target_result is None:
            raise ValueError("没有可用的预测结果")

        generator = ReportGenerator(target_result)

        if format == "json":
            return json.dumps(generator.generate_json_report(), ensure_ascii=False, indent=2)
        elif format == "html":
            return self.get_visualization(target_result).get_summary_html()
        else:
            return generator.generate_text_report()

    def export_results(
        self,
        result: Optional[PredictionResult] = None,
        output_dir: Optional[str] = None,
        include_figures: bool = True
    ) -> str:
        """
        导出所有结果

        Args:
            result: 预测结果
            output_dir: 输出目录
            include_figures: 是否包含图表

        Returns:
            输出目录路径
        """
        target_result = result or self._current_result
        if target_result is None:
            raise ValueError("没有可用的预测结果")

        if output_dir is None:
            output_dir = os.path.join(self.work_dir, f"export_{target_result.project_name}")

        os.makedirs(output_dir, exist_ok=True)

        # 保存图表
        if include_figures:
            viz = self.get_visualization(target_result)
            viz.save_all(output_dir, dpi=200)

        # 保存报告
        report = self.generate_report(target_result, "text")
        with open(os.path.join(output_dir, "report.txt"), 'w', encoding='utf-8') as f:
            f.write(report)

        # 保存JSON
        import json
        with open(os.path.join(output_dir, "result.json"), 'w', encoding='utf-8') as f:
            json.dump(target_result.to_dict(), f, ensure_ascii=False, indent=2)

        self._log(f"结果已导出到: {output_dir}")

        return output_dir

    def cleanup(self):
        """清理临时文件"""
        if os.path.exists(self.work_dir):
            shutil.rmtree(self.work_dir, ignore_errors=True)

    def get_local_capability(self) -> Dict:
        """获取本地计算能力"""
        return self.cloud_bridge.detect_local_capability()

    def plan_execution(
        self,
        project_data: ProjectData,
        tool_type: str = "aermod",
        mode: CloudExecutionMode = CloudExecutionMode.AUTO
    ) -> Dict:
        """
        规划执行方案

        Args:
            project_data: 项目数据
            tool_type: 工具类型
            mode: 执行模式

        Returns:
            执行方案
        """
        from .cloud_bridge import CloudExecutionPlanner

        planner = CloudExecutionPlanner()
        return planner.plan(tool_type, project_data, mode)


# 便捷函数
def get_manager() -> SeamlessIntegrationManager:
    """获取管理器实例"""
    return SeamlessIntegrationManager.get_instance()
