# -*- coding: utf-8 -*-
"""
Persona Skill 注册表
角色技能注册与管理中心
"""

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

from .models import (
    PersonaSkill, PersonaSession, PersonaCategory, 
    PersonaTier, PersonaInvokeResult
)
from .persona_loader import PersonaLoader


class PersonaRegistry:
    """Persona 注册表 - 角色技能管理中心"""

    def __init__(self, data_dir: Optional[Path] = None):
        # 数据目录
        self.data_dir = data_dir or Path(__file__).parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 注册表文件
        self.registry_file = self.data_dir / "registry.json"

        # 加载器
        self.loader = PersonaLoader()

        # 内存中的注册表
        self._personas: Dict[str, PersonaSkill] = {}
        self._sessions: Dict[str, PersonaSession] = {}
        self._active_persona: Optional[str] = None

        # 初始化
        self._load_registry()
        self._ensure_builtin_personas()

    def _load_registry(self):
        """从磁盘加载注册表"""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # 加载 personas
                for p_data in data.get("personas", []):
                    persona = PersonaSkill.from_dict(p_data)
                    self._personas[persona.id] = persona
                
                # 恢复激活状态
                self._active_persona = data.get("active_persona")
            except Exception as e:
                print(f"加载注册表失败: {e}")

    def _save_registry(self):
        """保存注册表到磁盘"""
        try:
            data = {
                "personas": [p.to_dict() for p in self._personas.values()],
                "active_persona": self._active_persona,
                "updated_at": datetime.now().isoformat()
            }
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存注册表失败: {e}")

    def _ensure_builtin_personas(self):
        """确保内置角色已加载"""
        builtin = self.loader.load_builtin_personas()
        for pid, persona in builtin.items():
            if pid not in self._personas:
                self._personas[pid] = persona
        
        # 标记内置角色
        for persona in self._personas.values():
            persona.is_builtin = True

    # ==================== CRUD 操作 ====================

    def register(self, persona: PersonaSkill) -> bool:
        """注册新角色"""
        if persona.id in self._personas:
            return False
        
        self._personas[persona.id] = persona
        self._save_registry()
        return True

    def unregister(self, persona_id: str) -> bool:
        """取消注册角色"""
        if persona_id not in self._personas:
            return False
        
        persona = self._personas[persona_id]
        if persona.is_builtin:
            return False  # 内置角色不可删除
        
        del self._personas[persona_id]
        
        # 清理相关会话
        self._sessions = {k: v for k, v in self._sessions.items() 
                         if v.persona_id != persona_id}
        
        self._save_registry()
        return True

    def get(self, persona_id: str) -> Optional[PersonaSkill]:
        """获取角色"""
        return self._personas.get(persona_id)

    def list_all(self) -> List[PersonaSkill]:
        """列出所有角色"""
        return list(self._personas.values())

    def list_by_category(self, category: PersonaCategory) -> List[PersonaSkill]:
        """按类别列出角色"""
        return [p for p in self._personas.values() if p.category == category]

    def list_by_tier(self, tier: PersonaTier) -> List[PersonaSkill]:
        """按等级列出角色"""
        return [p for p in self._personas.values() if p.tier == tier]

    def search(self, keyword: str) -> List[PersonaSkill]:
        """搜索角色"""
        kw = keyword.lower()
        results = []
        for p in self._personas.values():
            if (kw in p.name.lower() or 
                kw in p.description.lower() or 
                kw in " ".join(p.tags).lower()):
                results.append(p)
        return results

    def update(self, persona_id: str, updates: Dict[str, Any]) -> bool:
        """更新角色"""
        if persona_id not in self._personas:
            return False
        
        persona = self._personas[persona_id]
        
        # 可更新的字段
        updatable = ["name", "description", "icon", "system_prompt", 
                     "user_prompt_template", "is_active", "tags"]
        
        for key, value in updates.items():
            if key in updatable and hasattr(persona, key):
                setattr(persona, key, value)
        
        persona.version = str(float(persona.version) + 0.1)
        self._save_registry()
        return True

    # ==================== 激活与会话 ====================

    def activate(self, persona_id: str) -> bool:
        """激活角色"""
        if persona_id not in self._personas:
            return False
        
        self._active_persona = persona_id
        self._save_registry()
        return True

    def deactivate(self):
        """停用当前角色"""
        self._active_persona = None
        self._save_registry()

    def get_active(self) -> Optional[PersonaSkill]:
        """获取当前激活的角色"""
        if not self._active_persona:
            return None
        return self._personas.get(self._active_persona)

    def create_session(self, persona_id: Optional[str] = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())[:8]
        persona_id = persona_id or self._active_persona
        
        if not persona_id:
            persona_id = "nuwa"  # 默认使用女娲
        
        self._sessions[session_id] = PersonaSession(
            id=session_id,
            persona_id=persona_id
        )
        return session_id

    def get_session(self, session_id: str) -> Optional[PersonaSession]:
        """获取会话"""
        return self._sessions.get(session_id)

    def add_to_session(self, session_id: str, role: str, content: str):
        """向会话添加消息"""
        if session_id in self._sessions:
            self._sessions[session_id].add_message(role, content)

    # ==================== 使用统计 ====================

    def record_usage(self, persona_id: str):
        """记录角色使用"""
        if persona_id in self._personas:
            self._personas[persona_id].usage_count += 1
            self._personas[persona_id].last_used = datetime.now()
            self._save_registry()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        personas = list(self._personas.values())
        
        # 按类别统计
        by_category = {}
        for cat in PersonaCategory:
            by_category[cat.value] = len([p for p in personas if p.category == cat])
        
        # 按等级统计
        by_tier = {}
        for tier in PersonaTier:
            by_tier[tier.value] = len([p for p in personas if p.tier == tier])
        
        # 使用排行
        top_used = sorted(personas, key=lambda x: x.usage_count, reverse=True)[:5]
        
        return {
            "total": len(personas),
            "builtin": len([p for p in personas if p.is_builtin]),
            "custom": len([p for p in personas if not p.is_builtin]),
            "active": self._active_persona,
            "by_category": by_category,
            "by_tier": by_tier,
            "top_used": [{"id": p.id, "name": p.name, "icon": p.icon, "count": p.usage_count} 
                        for p in top_used],
            "total_sessions": len(self._sessions)
        }

    # ==================== 导入导出 ====================

    def export_persona(self, persona_id: str) -> Optional[Dict]:
        """导出角色配置"""
        persona = self.get(persona_id)
        if persona:
            return persona.to_dict()
        return None

    def import_persona(self, data: Dict) -> bool:
        """导入角色配置"""
        try:
            persona = PersonaSkill.from_dict(data)
            persona.is_builtin = False  # 导入的都是自定义
            return self.register(persona)
        except Exception as e:
            print(f"导入角色失败: {e}")
            return False

    def export_all(self) -> List[Dict]:
        """导出所有角色"""
        return [p.to_dict() for p in self._personas.values() if not p.is_builtin]

    def import_from_github(self, repo_name: str, persona_ids: List[str]) -> Dict[str, bool]:
        """从 GitHub 导入角色"""
        import asyncio
        
        results = {}
        for pid in persona_ids:
            persona = asyncio.run(self.loader.download_from_github(repo_name, pid))
            if persona:
                results[pid] = self.register(persona)
            else:
                results[pid] = False
        return results