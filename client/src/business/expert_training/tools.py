"""
专家训练工具函数 - 提供便捷的API供其他模块调用
"""

import json
from typing import Dict, List, Optional
from pathlib import Path

from client.src.business.expert_training import (
    get_expert_training_system,
    get_industry_classifier,
    get_notification_system
)
from client.src.business.expert_training.industry_classification import (
    INDUSTRY_CATEGORIES,
    OCCUPATION_CATEGORIES
)
import logging

logger = logging.getLogger(__name__)


def train_expert_from_text(text: str, expert_name: Optional[str] = None) -> Dict:
    """
    从文本训练专家（便捷函数）
    
    Args:
        text: 训练文本
        expert_name: 专家名称（可选）
        
    Returns:
        训练结果
    """
    try:
        system = get_expert_training_system()
        return system.train_expert(
            training_content=text,
            expert_name=expert_name,
            auto_notify=True
        )
    except Exception as e:
        logger.error(f"训练专家失败：{e}")
        return {"success": False, "error": str(e)}


def train_expert_from_file(file_path: str) -> Dict:
    """
    从文件训练专家（便捷函数）
    
    Args:
        file_path: 文件路径
        
    Returns:
        训练结果
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": f"文件不存在：{file_path}"}
        
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        return train_expert_from_text(
            text=content,
            expert_name=path.stem
        )
        
    except Exception as e:
        logger.error(f"从文件训练专家失败：{e}")
        return {"success": False, "error": str(e)}


def batch_train_from_directory(directory: str, progress_callback=None) -> Dict:
    """
    批量从目录训练专家（便捷函数）
    
    Args:
        directory: 目录路径
        progress_callback: 进度回调函数
        
    Returns:
        批量训练结果
    """
    try:
        system = get_expert_training_system()
        return system.batch_train(
            directory=directory,
            auto_notify=True,
            progress_callback=progress_callback
        )
    except Exception as e:
        logger.error(f"批量训练失败：{e}")
        return {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "error": str(e)
        }


def reorganize_experts_by_industry() -> Dict:
    """
    按行业重新整理专家（便捷函数）
    
    Returns:
        整理结果
    """
    try:
        system = get_expert_training_system()
        return system.reorganize_experts(auto_notify=True)
    except Exception as e:
        logger.error(f"整理专家失败：{e}")
        return {}


def get_expert_industry(expert_description: str, expert_name: str = "") -> Dict:
    """
    获取专家的行业分类（便捷函数）
    
    Args:
        expert_description: 专家描述
        expert_name: 专家名称
        
    Returns:
        行业分类结果
    """
    try:
        classifier = get_industry_classifier()
        return classifier.classify_expert(expert_description, expert_name)
    except Exception as e:
        logger.error(f"获取专家行业分类失败：{e}")
        return {}


def notify_expert_change(expert_name: str, expert_path: str, action: str) -> bool:
    """
    通知专家变更（便捷函数）
    
    Args:
        expert_name: 专家名称
        expert_path: 专家路径
        action: 动作（created/updated/deleted）
        
    Returns:
        是否通知成功
    """
    try:
        from client.src.business.expert_training.notification_system import (
            notify_expert_created,
            notify_expert_updated,
            notify_expert_deleted
        )
        
        if action == "created":
            return notify_expert_created(expert_name, expert_path)
        elif action == "updated":
            return notify_expert_updated(expert_name, expert_path)
        elif action == "deleted":
            return notify_expert_deleted(expert_name, expert_path)
        else:
            logger.warning(f"未知的动作：{action}")
            return False
            
    except Exception as e:
        logger.error(f"通知专家变更失败：{e}")
        return False


def get_industry_tree() -> Dict:
    """
    获取行业分类树（便捷函数）
    
    Returns:
        行业分类树
    """
    try:
        classifier = get_industry_classifier()
        return classifier.get_industry_tree()
    except Exception as e:
        logger.error(f"获取行业分类树失败：{e}")
        return {}


def check_industry_update() -> Dict:
    """
    检查行业分类更新（便捷函数）
    
    Returns:
        检查结果
    """
    try:
        from client.src.business.expert_training.industry_updater import get_industry_updater
        
        updater = get_industry_updater()
        return updater.check_and_update(force=False)
    except Exception as e:
        logger.error(f"检查行业分类更新失败：{e}")
        return {"need_update": False, "error": str(e)}


def get_notification_history(limit: int = 50) -> List[Dict]:
    """
    获取通知历史（便捷函数）
    
    Args:
        limit: 返回数量限制
        
    Returns:
        通知历史列表
    """
    try:
        system = get_notification_system()
        notifications = system.get_pending_notifications()
        return notifications[:limit]
    except Exception as e:
        logger.error(f"获取通知历史失败：{e}")
        return []


def export_experts_by_industry(output_file: Optional[str] = None) -> Dict:
    """
    按行业导出专家列表
    
    Args:
        output_file: 输出文件路径（可选）
        
    Returns:
        导出结果
    """
    try:
        system = get_expert_training_system()
        status = system.get_system_status()
        
        # 获取行业分类
        industry_tree = get_industry_tree()
        
        # 构建导出数据
        export_data = {
            "export_time": None,  # 由调用处添加
            "total_experts": status.get("expert_count", 0),
            "industry_count": status.get("industry_count", 0),
            "industries": []
        }
        
        # TODO: 填充每个行业的专家列表
        
        # 保存到文件
        if output_file:
            Path(output_file).write_text(
                json.dumps(export_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        
        return export_data
        
    except Exception as e:
        logger.error(f"导出专家列表失败：{e}")
        return {}


if __name__ == "__main__":
    # 测试代码
    print("=== 测试专家训练工具函数 ===\n")
    
    # 测试训练专家
    test_content = "我是数据分析专家，擅长Python、R、SQL等工具，能够进行统计分析、机器学习建模。"
    result = train_expert_from_text(test_content, "数据分析专家")
    print(f"训练结果：{json.dumps(result, ensure_ascii=False, indent=2)}")
    
    # 测试获取行业分类
    industry = get_expert_industry("数据分析专家", "数据分析专家")
    print(f"\n行业分类：{json.dumps(industry, ensure_ascii=False, indent=2)}")
    
    # 测试获取行业树
    tree = get_industry_tree()
    print(f"\n行业分类树门类数量：{len(tree.get('categories', {}))}")
    
    print("\n=== 测试完成 ===")
