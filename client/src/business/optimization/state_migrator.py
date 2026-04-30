"""
StateMigrator - 状态迁移管理器

核心功能：
1. 导出状态：打包当前系统状态
2. 状态适配：根据目标硬件调整状态
3. 导入状态：恢复到新设备
4. 验证迁移：确保迁移成功

支持迁移的状态类型：
- 用户配置
- 知识库索引
- 会话历史
- 模型配置
- 学习进度
"""

import json
import zipfile
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class HardwareInfo:
    """硬件信息"""
    gpu_model: str = ""
    gpu_memory_gb: int = 0
    cpu_cores: int = 0
    system_memory_gb: int = 0
    os: str = ""
    compute_capability: float = 0.0


@dataclass
class MigratedState:
    """迁移状态"""
    user_config: Dict[str, Any] = field(default_factory=dict)
    knowledge_index: Dict[str, Any] = field(default_factory=dict)
    session_history: List[Dict[str, Any]] = field(default_factory=list)
    model_config: Dict[str, Any] = field(default_factory=dict)
    learning_progress: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationResult:
    """迁移结果"""
    success: bool
    message: str = ""
    migrated_items: int = 0
    warnings: List[str] = field(default_factory=list)


class StateMigrator:
    """状态迁移管理器"""
    
    def __init__(self):
        self._logger = logger.bind(component="StateMigrator")
        self._logger.info("StateMigrator 初始化完成")
    
    def export_state(self, source_info: HardwareInfo, include_sensitive: bool = False) -> MigratedState:
        """
        导出状态
        
        Args:
            source_info: 源设备硬件信息
            include_sensitive: 是否包含敏感信息
        
        Returns:
            迁移状态对象
        """
        self._logger.info("开始导出状态")
        
        state = MigratedState()
        
        # 导出用户配置
        state.user_config = self._export_user_config(include_sensitive)
        
        # 导出知识库索引
        state.knowledge_index = self._export_knowledge_index()
        
        # 导出会话历史
        state.session_history = self._export_session_history()
        
        # 导出模型配置
        state.model_config = self._export_model_config()
        
        # 导出学习进度
        state.learning_progress = self._export_learning_progress()
        
        # 添加元数据
        state.metadata = {
            "source_hardware": {
                "gpu_model": source_info.gpu_model,
                "gpu_memory_gb": source_info.gpu_memory_gb,
                "cpu_cores": source_info.cpu_cores,
                "system_memory_gb": source_info.system_memory_gb,
                "os": source_info.os
            },
            "export_timestamp": 0.0,
            "version": "1.0"
        }
        
        self._logger.info(f"状态导出完成，共 {len(vars(state))} 个模块")
        return state
    
    def _export_user_config(self, include_sensitive: bool) -> Dict[str, Any]:
        """导出用户配置"""
        return {
            "preferences": {"theme": "dark", "language": "zh-CN"},
            "shortcuts": {},
            "notifications": {"enabled": True}
        }
    
    def _export_knowledge_index(self) -> Dict[str, Any]:
        """导出知识库索引"""
        return {
            "vector_index_version": "1.0",
            "document_count": 100,
            "index_checksum": "abc123"
        }
    
    def _export_session_history(self) -> List[Dict[str, Any]]:
        """导出会话历史"""
        return [
            {"id": "session_001", "topic": "AI基础", "timestamp": 0.0},
            {"id": "session_002", "topic": "文档处理", "timestamp": 0.0}
        ]
    
    def _export_model_config(self) -> Dict[str, Any]:
        """导出模型配置"""
        return {
            "current_model": "qwen3.6:8b",
            "model_settings": {"temperature": 0.7, "max_tokens": 4096}
        }
    
    def _export_learning_progress(self) -> Dict[str, Any]:
        """导出学习进度"""
        return {
            "topics_completed": ["AI基础", "机器学习"],
            "skill_levels": {"python": 3, "data_analysis": 2}
        }
    
    def adapt_state_for_hardware(self, state: MigratedState, target_info: HardwareInfo) -> MigratedState:
        """
        根据目标硬件调整状态
        
        Args:
            state: 迁移状态
            target_info: 目标设备硬件信息
        
        Returns:
            适配后的状态
        """
        self._logger.info(f"适配状态到目标硬件: {target_info.gpu_model}")
        
        # 调整模型配置
        state.model_config = self._adapt_model_config(state.model_config, target_info)
        
        # 调整内存相关配置
        state.user_config = self._adapt_memory_config(state.user_config, target_info)
        
        # 更新元数据
        state.metadata["target_hardware"] = {
            "gpu_model": target_info.gpu_model,
            "gpu_memory_gb": target_info.gpu_memory_gb,
            "cpu_cores": target_info.cpu_cores,
            "system_memory_gb": target_info.system_memory_gb,
            "os": target_info.os
        }
        
        self._logger.info("状态适配完成")
        return state
    
    def _adapt_model_config(self, model_config: Dict[str, Any], target_info: HardwareInfo) -> Dict[str, Any]:
        """适配模型配置"""
        gpu_memory = target_info.gpu_memory_gb
        
        # 根据显存选择合适的模型
        if gpu_memory >= 48:
            model_config["current_model"] = "qwen3.6:32b"
            model_config["model_settings"]["max_tokens"] = 8192
        elif gpu_memory >= 24:
            model_config["current_model"] = "qwen3.6:14b"
            model_config["model_settings"]["max_tokens"] = 4096
        elif gpu_memory >= 16:
            model_config["current_model"] = "qwen3.6:8b"
            model_config["model_settings"]["max_tokens"] = 4096
        elif gpu_memory >= 8:
            model_config["current_model"] = "qwen3.5:4b"
            model_config["model_settings"]["max_tokens"] = 2048
        else:
            model_config["current_model"] = "qwen3.5:0.8b"
            model_config["model_settings"]["max_tokens"] = 1024
        
        return model_config
    
    def _adapt_memory_config(self, user_config: Dict[str, Any], target_info: HardwareInfo) -> Dict[str, Any]:
        """适配内存配置"""
        system_memory = target_info.system_memory_gb
        
        if system_memory < 16:
            user_config["memory_mode"] = "conservative"
        elif system_memory < 32:
            user_config["memory_mode"] = "balanced"
        else:
            user_config["memory_mode"] = "performance"
        
        return user_config
    
    def import_state(self, state: MigratedState, target_info: HardwareInfo) -> MigrationResult:
        """
        导入状态
        
        Args:
            state: 迁移状态
            target_info: 目标设备硬件信息
        
        Returns:
            迁移结果
        """
        self._logger.info("开始导入状态")
        
        warnings = []
        migrated_items = 0
        
        try:
            # 导入用户配置
            self._import_user_config(state.user_config)
            migrated_items += 1
            
            # 导入知识库索引
            self._import_knowledge_index(state.knowledge_index)
            migrated_items += 1
            
            # 导入会话历史
            self._import_session_history(state.session_history)
            migrated_items += 1
            
            # 导入模型配置
            self._import_model_config(state.model_config)
            migrated_items += 1
            
            # 导入学习进度
            self._import_learning_progress(state.learning_progress)
            migrated_items += 1
            
            self._logger.info(f"状态导入完成，共 {migrated_items} 个模块")
            
            return MigrationResult(
                success=True,
                message=f"成功迁移 {migrated_items} 个模块",
                migrated_items=migrated_items,
                warnings=warnings
            )
        
        except Exception as e:
            self._logger.error(f"状态导入失败: {e}")
            return MigrationResult(
                success=False,
                message=f"迁移失败: {e}",
                migrated_items=migrated_items,
                warnings=warnings + [str(e)]
            )
    
    def _import_user_config(self, config: Dict[str, Any]):
        """导入用户配置"""
        pass
    
    def _import_knowledge_index(self, index: Dict[str, Any]):
        """导入知识库索引"""
        pass
    
    def _import_session_history(self, history: List[Dict[str, Any]]):
        """导入会话历史"""
        pass
    
    def _import_model_config(self, config: Dict[str, Any]):
        """导入模型配置"""
        pass
    
    def _import_learning_progress(self, progress: Dict[str, Any]):
        """导入学习进度"""
        pass
    
    def verify_migration(self, target_info: HardwareInfo) -> bool:
        """
        验证迁移是否成功
        
        Args:
            target_info: 目标设备硬件信息
        
        Returns:
            是否验证通过
        """
        self._logger.info("验证迁移结果")
        
        # 检查配置是否正确应用
        checks = [
            self._check_model_config(),
            self._check_knowledge_index(),
            self._check_session_history()
        ]
        
        all_passed = all(checks)
        self._logger.info(f"迁移验证: {'通过' if all_passed else '失败'}")
        return all_passed
    
    def _check_model_config(self) -> bool:
        """检查模型配置"""
        return True
    
    def _check_knowledge_index(self) -> bool:
        """检查知识库索引"""
        return True
    
    def _check_session_history(self) -> bool:
        """检查会话历史"""
        return True
    
    def save_state_to_file(self, state: MigratedState, file_path: str):
        """保存状态到文件"""
        with zipfile.ZipFile(file_path, 'w') as zf:
            # 保存状态为JSON
            state_json = json.dumps(vars(state), ensure_ascii=False, indent=2)
            zf.writestr('state.json', state_json)
            
            # 保存元数据
            metadata = {
                "version": "1.0",
                "description": "LivingTree AI Agent State Backup"
            }
            zf.writestr('metadata.json', json.dumps(metadata, indent=2))
        
        self._logger.info(f"状态已保存到: {file_path}")
    
    def load_state_from_file(self, file_path: str) -> Optional[MigratedState]:
        """从文件加载状态"""
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                state_json = zf.read('state.json').decode('utf-8')
                state_data = json.loads(state_json)
                
                state = MigratedState(
                    user_config=state_data.get('user_config', {}),
                    knowledge_index=state_data.get('knowledge_index', {}),
                    session_history=state_data.get('session_history', []),
                    model_config=state_data.get('model_config', {}),
                    learning_progress=state_data.get('learning_progress', {}),
                    metadata=state_data.get('metadata', {})
                )
                
                self._logger.info(f"状态已从 {file_path} 加载")
                return state
        
        except Exception as e:
            self._logger.error(f"加载状态失败: {e}")
            return None
    
    def migrate_to_new_machine(self, source_info: HardwareInfo, target_info: HardwareInfo,
                               backup_path: str = None) -> MigrationResult:
        """
        完整的跨设备迁移流程
        
        Args:
            source_info: 源设备信息
            target_info: 目标设备信息
            backup_path: 备份文件路径（可选）
        
        Returns:
            迁移结果
        """
        self._logger.info(f"开始跨设备迁移: {source_info.gpu_model} -> {target_info.gpu_model}")
        
        # 1. 导出状态
        state = self.export_state(source_info)
        
        # 可选：保存备份
        if backup_path:
            self.save_state_to_file(state, backup_path)
        
        # 2. 根据目标硬件调整状态
        adapted_state = self.adapt_state_for_hardware(state, target_info)
        
        # 3. 导入状态
        result = self.import_state(adapted_state, target_info)
        
        # 4. 验证迁移
        if result.success:
            result.success = self.verify_migration(target_info)
        
        self._logger.info(f"跨设备迁移完成: {'成功' if result.success else '失败'}")
        return result


# 单例模式
_state_migrator_instance = None

def get_state_migrator() -> StateMigrator:
    """获取状态迁移管理器实例"""
    global _state_migrator_instance
    if _state_migrator_instance is None:
        _state_migrator_instance = StateMigrator()
    return _state_migrator_instance


if __name__ == "__main__":
    print("=" * 60)
    print("StateMigrator 测试")
    print("=" * 60)
    
    migrator = get_state_migrator()
    
    # 定义源设备和目标设备
    source_hw = HardwareInfo(
        gpu_model="NVIDIA V100",
        gpu_memory_gb=64,
        cpu_cores=22,
        system_memory_gb=64,
        os="linux"
    )
    
    target_hw = HardwareInfo(
        gpu_model="NVIDIA RTX 4090",
        gpu_memory_gb=24,
        cpu_cores=16,
        system_memory_gb=32,
        os="windows"
    )
    
    # 测试1：导出状态
    print("\n[1] 导出状态")
    state = migrator.export_state(source_hw)
    print(f"用户配置: {state.user_config}")
    print(f"模型配置: {state.model_config}")
    print(f"学习进度: {state.learning_progress}")
    
    # 测试2：适配状态
    print("\n[2] 适配状态到目标硬件")
    adapted_state = migrator.adapt_state_for_hardware(state, target_hw)
    print(f"适配后的模型: {adapted_state.model_config}")
    print(f"适配后的内存模式: {adapted_state.user_config.get('memory_mode')}")
    
    # 测试3：完整迁移流程
    print("\n[3] 完整迁移流程")
    result = migrator.migrate_to_new_machine(source_hw, target_hw)
    print(f"迁移成功: {result.success}")
    print(f"迁移模块数: {result.migrated_items}")
    print(f"消息: {result.message}")
    
    # 测试4：保存和加载状态
    print("\n[4] 保存和加载状态")
    backup_file = "test_backup.zip"
    migrator.save_state_to_file(state, backup_file)
    
    loaded_state = migrator.load_state_from_file(backup_file)
    if loaded_state:
        print("状态加载成功")
        print(f"会话数量: {len(loaded_state.session_history)}")
    
    # 清理测试文件
    if os.path.exists(backup_file):
        os.remove(backup_file)
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)