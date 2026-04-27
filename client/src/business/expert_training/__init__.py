"""
专家训练模块 - 根据训练内容自主创建专家角色
支持自动按照行业和职业重新整理专家角色
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# 版本信息
__version__ = "1.0.0"
__author__ = "LivingTree AI Agent System"

# 导出核心类
from client.src.business.expert_training.industry_classification import (
    IndustryClassifier,
    get_industry_classifier,
    INDUSTRY_CATEGORIES,
    OCCUPATION_CATEGORIES,
    EXPERT_INDUSTRY_MAPPING
)

from client.src.business.expert_training.expert_trainer import (
    ExpertTrainer,
    get_expert_trainer
)

from client.src.business.expert_training.notification_system import (
    AgentNotificationSystem,
    get_notification_system,
    notify_expert_created,
    notify_expert_updated,
    notify_expert_deleted
)


class ExpertTrainingSystem:
    """
    专家训练系统 - 统一入口
    
    整合行业分类、专家训练、通知系统的完整工作流程
    """
    
    def __init__(self):
        self.industry_classifier = get_industry_classifier()
        self.expert_trainer = get_expert_trainer()
        self.notification_system = get_notification_system()
        
        logger.info("专家训练系统初始化完成")
    
    def train_expert(self,
                     training_content: str,
                     expert_name: Optional[str] = None,
                     auto_notify: bool = True) -> Dict:
        """
        训练单个专家
        
        Args:
            training_content: 训练内容
            expert_name: 专家名称（可选）
            auto_notify: 是否自动通知其他智能体
            
        Returns:
            训练结果
        """
        try:
            result = self.expert_trainer.train_from_content(
                training_content=training_content,
                expert_name=expert_name
            )
            
            if result.get("success") and auto_notify:
                # 发送通知
                notification = result.get("notification")
                if notification:
                    self.notification_system.send_notification(notification)
            
            return result
            
        except Exception as e:
            logger.error(f"训练专家失败：{e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def batch_train(self,
                    directory: str,
                    auto_notify: bool = True,
                    progress_callback=None) -> Dict:
        """
        批量训练
        
        Args:
            directory: 训练文件目录
            auto_notify: 是否自动通知
            progress_callback: 进度回调函数
            
        Returns:
            批量训练结果
        """
        try:
            result = self.expert_trainer.batch_train_from_directory(
                directory=directory,
                progress_callback=progress_callback
            )
            
            if result.get("success", 0) > 0 and auto_notify:
                # 发送批量训练完成通知
                notification = self.notification_system.create_expert_notification(
                    expert_name="批量训练",
                    expert_path=directory,
                    action="batch_created",
                    details=result
                )
                self.notification_system.send_notification(notification)
            
            return result
            
        except Exception as e:
            logger.error(f"批量训练失败：{e}")
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "error": str(e)
            }
    
    def reorganize_experts(self, auto_notify: bool = True) -> Dict:
        """
        按行业和职业重新整理专家
        
        Args:
            auto_notify: 是否自动通知
            
        Returns:
            整理结果
        """
        try:
            result = self.expert_trainer.reorganize_by_industry()
            
            if auto_notify:
                # 发送整理完成通知
                notification = {
                    "type": "experts_reorganized",
                    "timestamp": None,  # 由notification_system添加
                    "message": f"专家角色已按行业重新整理，共 {result.get('total_experts', 0)} 个专家",
                    "details": result
                }
                self.notification_system.send_notification(notification)
            
            return result
            
        except Exception as e:
            logger.error(f"整理专家失败：{e}")
            return {}
    
    def check_industry_updates(self) -> bool:
        """
        检查行业分类更新（从政府网站）
        
        Returns:
            是否有更新
        """
        try:
            return self.industry_classifier.check_for_updates()
        except Exception as e:
            logger.error(f"检查行业分类更新失败：{e}")
            return False
    
    def get_system_status(self) -> Dict:
        """
        获取系统状态
        
        Returns:
            状态字典
        """
        try:
            # 统计专家数量
            experts_dir = self.expert_trainer.skills_base_dir
            expert_count = len([d for d in experts_dir.iterdir() if d.is_dir()])
            
            # 获取行业分类数量
            industry_count = len(INDUSTRY_CATEGORIES)
            
            return {
                "expert_count": expert_count,
                "industry_count": industry_count,
                "notification_dir": str(self.notification_system.notification_dir),
                "listener_count": len(self.notification_system._listeners),
                "version": __version__
            }
            
        except Exception as e:
            logger.error(f"获取系统状态失败：{e}")
            return {}


# 全局系统实例
_system_instance = None

def get_expert_training_system() -> ExpertTrainingSystem:
    """获取专家训练系统单例"""
    global _system_instance
    
    if _system_instance is None:
        _system_instance = ExpertTrainingSystem()
    
    return _system_instance


if __name__ == "__main__":
    # 测试代码
    import json
    
    system = get_expert_training_system()
    
    # 测试训练专家
    test_content = """
    我是环境影响评价专家，专注于建设项目环境影响评价报告的编制和审查。
    熟悉《环境影响评价法》、《建设项目环境保护管理条例》等法律法规。
    擅长大气环境影响预测、水环境影响分析、噪声影响评价等技术工作。
    能够使用AERMOD、ADMS等大气扩散模型进行模拟预测。
    """
    
    print("=== 测试专家训练 ===")
    result = system.train_expert(test_content, "环评专家")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 获取系统状态
    print("\n=== 系统状态 ===")
    status = system.get_system_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))
