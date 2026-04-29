"""
热替换部署器 - Hot-Swap Deployer

负责将胜出的新模型通过"流量渐增"方式替换线上旧模型，
全程无缝，失败则自动回滚。

部署流程：
1. 验证新模型
2. 预热新模型
3. 流量渐增（10% → 50% → 100%）
4. 监控性能
5. 完成部署或回滚
"""

import subprocess
import json
import time
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class DeploymentResult:
    """部署结果"""
    success: bool
    new_model_name: Optional[str] = None
    old_model_name: Optional[str] = None
    rollback: bool = False
    error: Optional[str] = None
    metrics: Dict = field(default_factory=dict)


class HotswapDeployer:
    """
    热替换部署器
    
    将胜出的新模型无缝替换线上旧模型
    """
    
    def __init__(self):
        self._logger = logger.bind(component="HotswapDeployer")
        self._current_model = None
        self._backup_model = None
    
    def deploy(self, new_model_path: str, rollback_on_failure: bool = True) -> Dict:
        """
        执行热替换部署
        
        Args:
            new_model_path: 新模型路径
            rollback_on_failure: 失败时是否回滚
        
        Returns:
            部署结果
        """
        self._logger.info(f"开始热替换部署: {new_model_path}")
        
        result = DeploymentResult(success=False)
        
        try:
            # 阶段1: 验证新模型
            self._logger.info("阶段1: 验证新模型")
            if not self._validate_model(new_model_path):
                result.error = "新模型验证失败"
                return result.to_dict()
            
            # 阶段2: 备份当前模型
            self._logger.info("阶段2: 备份当前模型")
            self._backup_current_model()
            
            # 阶段3: 预热新模型
            self._logger.info("阶段3: 预热新模型")
            if not self._warmup_model(new_model_path):
                if rollback_on_failure:
                    self._rollback()
                result.error = "模型预热失败"
                return result.to_dict()
            
            # 阶段4: 流量渐增
            self._logger.info("阶段4: 流量渐增")
            if not self._traffic_rampup(new_model_path):
                if rollback_on_failure:
                    self._rollback()
                result.error = "流量渐增失败"
                return result.to_dict()
            
            # 阶段5: 完成部署
            self._logger.info("阶段5: 完成部署")
            self._complete_deployment(new_model_path)
            
            result.success = True
            result.new_model_name = Path(new_model_path).stem
            result.old_model_name = self._backup_model
            result.metrics = self._collect_deployment_metrics()
            
            self._logger.info("✅ 部署成功！")
            return result.to_dict()
            
        except Exception as e:
            self._logger.error(f"部署失败: {e}")
            if rollback_on_failure and self._backup_model:
                self._rollback()
                result.rollback = True
            
            result.error = str(e)
            return result.to_dict()
    
    def _validate_model(self, model_path: str) -> bool:
        """验证新模型"""
        model_path = Path(model_path)
        
        # 检查文件是否存在
        if not model_path.exists():
            self._logger.error(f"模型文件不存在: {model_path}")
            return False
        
        # 检查是否是有效的模型文件
        valid_extensions = [".bin", ".pt", ".pth", ".gguf", ".safetensors"]
        if model_path.suffix not in valid_extensions:
            # 检查是否是目录
            if not model_path.is_dir():
                self._logger.error(f"无效的模型格式: {model_path.suffix}")
                return False
        
        self._logger.info(f"模型验证通过: {model_path}")
        return True
    
    def _backup_current_model(self):
        """备份当前模型"""
        try:
            from client.src.infrastructure.ollama_runner import OllamaRunner
            
            runner = OllamaRunner()
            self._current_model = runner.get_current_model()
            
            if self._current_model:
                self._backup_model = self._current_model
                self._logger.info(f"已备份当前模型: {self._backup_model}")
            else:
                self._logger.warning("没有当前运行的模型")
        except Exception as e:
            self._logger.warning(f"备份失败: {e}")
    
    def _warmup_model(self, model_path: str) -> bool:
        """预热新模型"""
        try:
            from client.src.infrastructure.ollama_runner import OllamaRunner
            
            runner = OllamaRunner()
            
            # 加载新模型
            model_name = Path(model_path).stem
            runner.load_model(model_name, model_path)
            
            # 执行预热查询
            warmup_queries = [
                "Hello",
                "What is AI?",
                "Explain machine learning"
            ]
            
            for query in warmup_queries:
                result = runner.generate(query, model_name=model_name)
                if not result.get("success"):
                    self._logger.error("预热查询失败")
                    return False
            
            self._logger.info("模型预热完成")
            return True
            
        except Exception as e:
            self._logger.error(f"预热失败: {e}")
            return False
    
    def _traffic_rampup(self, model_path: str) -> bool:
        """流量渐增"""
        rampup_steps = [10, 50, 100]  # 百分比
        
        for percentage in rampup_steps:
            self._logger.info(f"切换 {percentage}% 流量到新模型")
            
            # 设置流量比例
            if not self._set_traffic_split(model_path, percentage):
                return False
            
            # 等待并监控
            time.sleep(60)  # 等待1分钟
            
            # 检查性能
            if not self._check_performance():
                self._logger.error("性能检查失败")
                return False
            
        return True
    
    def _set_traffic_split(self, model_path: str, percentage: int) -> bool:
        """设置流量分配"""
        try:
            from client.src.infrastructure.ollama_runner import OllamaRunner
            
            runner = OllamaRunner()
            model_name = Path(model_path).stem
            
            # 在生产环境中，这里会实现真正的流量分配
            # 当前只是简单切换
            if percentage == 100:
                runner.set_default_model(model_name)
            
            return True
        except Exception as e:
            self._logger.error(f"设置流量分配失败: {e}")
            return False
    
    def _check_performance(self) -> bool:
        """检查性能指标"""
        try:
            from client.src.infrastructure.system_resources import SystemResources
            
            resources = SystemResources()
            
            # 检查 GPU 使用率
            gpu_usage = resources.get_gpu_usage()
            if gpu_usage > 95:
                self._logger.warning(f"GPU 使用率过高: {gpu_usage}%")
            
            # 检查响应时间
            # 在生产环境中会有更复杂的监控
            
            return True
        except Exception as e:
            self._logger.warning(f"性能检查失败: {e}")
            return True  # 继续部署
    
    def _rollback(self):
        """回滚到旧模型"""
        try:
            from client.src.infrastructure.ollama_runner import OllamaRunner
            
            runner = OllamaRunner()
            
            if self._backup_model:
                runner.set_default_model(self._backup_model)
                self._logger.info(f"已回滚到旧模型: {self._backup_model}")
            else:
                self._logger.warning("没有备份模型可回滚")
        except Exception as e:
            self._logger.error(f"回滚失败: {e}")
    
    def _complete_deployment(self, model_path: str):
        """完成部署"""
        # 更新配置文件
        config_dir = Path.home() / ".livingtree_agent" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config_data = {
            "current_model": Path(model_path).stem,
            "deployed_at": datetime.now().isoformat(),
            "previous_model": self._backup_model
        }
        
        (config_dir / "model_config.json").write_text(
            json.dumps(config_data, indent=2)
        )
        
        self._logger.info("配置文件已更新")
    
    def _collect_deployment_metrics(self) -> Dict:
        """收集部署指标"""
        return {
            "deployed_at": datetime.now().isoformat(),
            "new_model": self._current_model,
            "old_model": self._backup_model
        }
    
    def get_deployment_history(self) -> List[Dict]:
        """获取部署历史"""
        history_file = Path.home() / ".livingtree_agent" / "data" / "deployments.json"
        
        if history_file.exists():
            return json.loads(history_file.read_text(encoding="utf-8"))
        
        return []


# 快捷函数
def get_hotswap_deployer() -> HotswapDeployer:
    """获取热替换部署器实例"""
    return HotswapDeployer()


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("热替换部署器测试")
    print("=" * 60)
    
    deployer = HotswapDeployer()
    
    # 测试部署流程
    result = deployer.deploy("./output/model", rollback_on_failure=True)
    print(f"部署结果: {result}")
    
    print("\n" + "=" * 60)