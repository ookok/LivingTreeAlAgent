"""
训练工具 - 系统工具注册

将 MS-SWIFT 训练框架注册为系统工具，供决策层调度使用
"""

from typing import Dict, Optional
from loguru import logger

# 导入 MS-SWIFT 集成
from ..training.ms_swift_integration import (
    MSSwiftIntegration,
    TrainingScheduler,
    TrainingConfig,
    TrainingResult,
    get_swift_integration,
    get_training_scheduler
)


class TrainingTool:
    """
    训练工具 - 系统工具封装
    
    提供模型训练相关功能，由决策层调度
    """
    
    # 工具元数据
    NAME = "training"
    DESCRIPTION = "训练工具 - 基于 MS-SWIFT 的模型训练框架，支持 LoRA、全参微调、知识蒸馏"
    DESCRIPTION_EN = "Training Tool - Model training framework based on MS-SWIFT, supports LoRA, full fine-tuning, and knowledge distillation"
    
    @classmethod
    def get_tool_info(cls) -> Dict:
        """获取工具信息"""
        swift = MSSwiftIntegration()
        
        return {
            "name": cls.NAME,
            "description": cls.DESCRIPTION,
            "description_en": cls.DESCRIPTION_EN,
            "version": "1.0.0",
            "author": "LivingTreeAlAgent",
            "capabilities": [
                "train",
                "fine_tune_lora",
                "fine_tune_full",
                "distill",
                "schedule_training",
                "check_status",
                "list_models",
                "install_swift"
            ],
            "supported_models": swift.get_supported_models(),
            "training_types": swift.get_training_types(),
            "swift_available": swift.is_available()
        }
    
    @classmethod
    def train(cls, config: TrainingConfig) -> Dict:
        """
        执行训练任务
        
        Args:
            config: 训练配置
        
        Returns:
            结果字典
        """
        swift = MSSwiftIntegration()
        
        if not swift.is_available():
            return {
                "success": False,
                "message": "MS-SWIFT 不可用，请先安装",
                "message_en": "MS-SWIFT not available, please install first"
            }
        
        try:
            result = swift.train(config)
            
            if result.success:
                return {
                    "success": True,
                    "message": "训练成功",
                    "message_en": "Training successful",
                    "model_path": result.model_path,
                    "training_time": result.training_time,
                    "loss": result.loss,
                    "eval_loss": result.eval_loss,
                    "metrics": result.metrics
                }
            else:
                return {
                    "success": False,
                    "message": f"训练失败: {result.error}",
                    "message_en": f"Training failed: {result.error}"
                }
        except Exception as e:
            logger.error(f"训练异常: {e}")
            return {
                "success": False,
                "message": f"训练异常: {str(e)}",
                "message_en": f"Training error: {str(e)}"
            }
    
    @classmethod
    def fine_tune_lora(cls, model_name: str, dataset_name: str, output_dir: str) -> Dict:
        """
        执行 LoRA 微调
        
        Args:
            model_name: 模型名称
            dataset_name: 数据集名称
            output_dir: 输出目录
        
        Returns:
            结果字典
        """
        swift = MSSwiftIntegration()
        
        if not swift.is_available():
            return {
                "success": False,
                "message": "MS-SWIFT 不可用",
                "message_en": "MS-SWIFT not available"
            }
        
        result = swift.fine_tune_lora(model_name, dataset_name, output_dir)
        
        if result.success:
            return {
                "success": True,
                "message": "LoRA 微调成功",
                "message_en": "LoRA fine-tuning successful",
                "model_path": result.model_path
            }
        else:
            return {
                "success": False,
                "message": f"LoRA 微调失败: {result.error}",
                "message_en": f"LoRA fine-tuning failed: {result.error}"
            }
    
    @classmethod
    def fine_tune_full(cls, model_name: str, dataset_name: str, output_dir: str) -> Dict:
        """
        执行全参微调
        
        Args:
            model_name: 模型名称
            dataset_name: 数据集名称
            output_dir: 输出目录
        
        Returns:
            结果字典
        """
        swift = MSSwiftIntegration()
        
        if not swift.is_available():
            return {
                "success": False,
                "message": "MS-SWIFT 不可用",
                "message_en": "MS-SWIFT not available"
            }
        
        result = swift.fine_tune_full(model_name, dataset_name, output_dir)
        
        if result.success:
            return {
                "success": True,
                "message": "全参微调成功",
                "message_en": "Full fine-tuning successful",
                "model_path": result.model_path
            }
        else:
            return {
                "success": False,
                "message": f"全参微调失败: {result.error}",
                "message_en": f"Full fine-tuning failed: {result.error}"
            }
    
    @classmethod
    def distill(cls, teacher_model: str, student_model: str, dataset_name: str, output_dir: str) -> Dict:
        """
        执行知识蒸馏
        
        Args:
            teacher_model: 教师模型
            student_model: 学生模型
            dataset_name: 数据集名称
            output_dir: 输出目录
        
        Returns:
            结果字典
        """
        swift = MSSwiftIntegration()
        
        if not swift.is_available():
            return {
                "success": False,
                "message": "MS-SWIFT 不可用",
                "message_en": "MS-SWIFT not available"
            }
        
        result = swift.distill(teacher_model, student_model, dataset_name, output_dir)
        
        if result.success:
            return {
                "success": True,
                "message": "知识蒸馏成功",
                "message_en": "Knowledge distillation successful",
                "model_path": result.model_path
            }
        else:
            return {
                "success": False,
                "message": f"知识蒸馏失败: {result.error}",
                "message_en": f"Knowledge distillation failed: {result.error}"
            }
    
    @classmethod
    def schedule_training(cls, config: TrainingConfig) -> Dict:
        """
        调度训练任务（由决策层调用）
        
        Args:
            config: 训练配置
        
        Returns:
            结果字典
        """
        scheduler = get_training_scheduler()
        success = scheduler.schedule_training(config)
        
        if success:
            return {
                "success": True,
                "message": "训练任务已调度",
                "message_en": "Training task scheduled",
                "is_running": scheduler.is_training(),
                "pending_tasks": len(scheduler.get_pending_tasks())
            }
        else:
            return {
                "success": False,
                "message": "训练任务调度失败",
                "message_en": "Failed to schedule training task"
            }
    
    @classmethod
    def check_status(cls) -> Dict:
        """
        检查训练状态
        
        Returns:
            状态字典
        """
        scheduler = get_training_scheduler()
        swift = MSSwiftIntegration()
        
        return {
            "swift_available": swift.is_available(),
            "is_training": scheduler.is_training(),
            "pending_tasks": len(scheduler.get_pending_tasks()),
            "supported_models": swift.get_supported_models(),
            "training_types": swift.get_training_types()
        }
    
    @classmethod
    def list_models(cls) -> Dict:
        """
        获取支持的模型列表
        
        Returns:
            模型列表字典
        """
        swift = MSSwiftIntegration()
        
        return {
            "success": True,
            "models": swift.get_supported_models(),
            "count": len(swift.get_supported_models())
        }
    
    @classmethod
    def install_swift(cls) -> Dict:
        """
        安装 MS-SWIFT
        
        Returns:
            安装结果
        """
        swift = MSSwiftIntegration()
        success = swift.install_swift()
        
        if success:
            return {
                "success": True,
                "message": "MS-SWIFT 安装成功",
                "message_en": "MS-SWIFT installed successfully"
            }
        else:
            return {
                "success": False,
                "message": "MS-SWIFT 安装失败",
                "message_en": "Failed to install MS-SWIFT"
            }


# 工具注册函数
def register_training_tool():
    """注册训练工具到系统工具注册表"""
    try:
        from client.src.business.tools.tool_registry import ToolRegistry, ToolDefinition
        
        tool_info = TrainingTool.get_tool_info()
        
        # 创建工具定义
        tool_def = ToolDefinition(
            name=tool_info["name"],
            description=tool_info["description"],
            handler=TrainingTool,
            parameters={
                "train": "config: TrainingConfig",
                "fine_tune_lora": "model_name, dataset_name, output_dir",
                "fine_tune_full": "model_name, dataset_name, output_dir",
                "distill": "teacher_model, student_model, dataset_name, output_dir",
                "schedule_training": "config: TrainingConfig",
                "check_status": "",
                "list_models": "",
                "install_swift": ""
            },
            returns="Dict[str, Any]",
            category="training",
            version=tool_info["version"],
            author=tool_info["author"]
        )
        
        # 注册工具
        registry = ToolRegistry.get_instance()
        registry.register(tool_def)
        
        logger.info(f"训练工具已注册: {tool_info['name']}")
        return True
    except Exception as e:
        logger.warning(f"训练工具注册失败: {e}")
        return False


# 快捷函数
def get_training_tool() -> TrainingTool:
    """获取训练工具实例"""
    return TrainingTool()


# 自动注册
register_training_tool()


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("训练工具测试")
    print("=" * 60)
    
    tool = TrainingTool()
    
    # 获取工具信息
    info = tool.get_tool_info()
    print(f"工具名称: {info['name']}")
    print(f"工具描述: {info['description']}")
    print(f"MS-SWIFT 可用: {'是' if info['swift_available'] else '否'}")
    print(f"支持模型数量: {len(info['supported_models'])}")
    print(f"支持训练类型: {list(info['training_types'].items())}")
    
    # 检查状态
    status = tool.check_status()
    print(f"\n训练状态:")
    print(f"  正在训练: {status['is_training']}")
    print(f"  待执行任务: {status['pending_tasks']}")
    
    print("\n" + "=" * 60)