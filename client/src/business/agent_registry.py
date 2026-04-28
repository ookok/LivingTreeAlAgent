"""
智能体注册中心 (Agent Registry)
实现架构设计：技能/专家角色变化 → 通知各个智能体，而非UI组件

设计原则：
1. 各个智能体主动注册自己
2. 技能或专家角色变化时，通知所有已注册的智能体
3. 智能体实现 on_skills_changed() / on_agents_changed() 回调来响应变化
"""

from typing import Dict, List, Set, Callable, Optional, Any
from pathlib import Path
import json
import threading


class AgentRegistry:
    """
    智能体注册中心（单例模式）
    
    职责：
    1. 管理所有已注册的智能体实例
    2. 当技能或专家角色启用状态变化时，通知所有智能体
    3. 提供智能体查询接口
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        # 注册的智能体: {agent_id: agent_instance}
        self._agents: Dict[str, Any] = {}
        
        # 智能体元数据: {agent_id: metadata}
        self._metadata: Dict[str, Dict] = {}
        
        # 当前已启用的技能列表（缓存）
        self._active_skills: Set[str] = set()
        
        # 当前已启用的专家角色列表（缓存）
        self._active_agents: Set[str] = set()
        
        # 加载已启用的技能列表和专家角色列表
        self._load_active_skills()
        self._load_active_agents()
        
        print(f"[AgentRegistry] 初始化完成，已加载 {len(self._active_skills)} 个启用技能，{len(self._active_agents)} 个启用专家角色")
    
    def _load_active_skills(self):
        """从磁盘加载已启用的技能列表"""
        active_file = Path.home() / ".workbuddy" / "active_skills.json"
        if active_file.exists():
            try:
                data = json.loads(active_file.read_text(encoding="utf-8"))
                self._active_skills = set(data.get("active", []))
            except Exception as e:
                print(f"[AgentRegistry] 加载技能列表失败: {e}")
                self._active_skills = set()
    
    def _load_active_agents(self):
        """从磁盘加载已启用的专家角色列表"""
        active_file = Path.home() / ".workbuddy" / "active_agents.json"
        if active_file.exists():
            try:
                data = json.loads(active_file.read_text(encoding="utf-8"))
                self._active_agents = set(data.get("active", []))
            except Exception as e:
                print(f"[AgentRegistry] 加载专家角色列表失败: {e}")
                self._active_agents = set()
    
    def register(self, agent_id: str, agent_instance: Any, metadata: Optional[Dict] = None):
        """
        注册智能体
        
        Args:
            agent_id: 智能体唯一标识符（如 "hermes", "ei_agent", "ide_agent"）
            agent_instance: 智能体实例（必须实现 on_skills_changed / on_agents_changed 方法）
            metadata: 智能体元数据（如类型、描述等）
        """
        self._agents[agent_id] = agent_instance
        self._metadata[agent_id] = metadata or {}
        print(f"[AgentRegistry] 注册智能体: {agent_id}")
        
        # 立即通知新注册的智能体当前技能状态
        if hasattr(agent_instance, 'on_skills_changed'):
            try:
                agent_instance.on_skills_changed(self._active_skills)
            except Exception as e:
                print(f"[AgentRegistry] 通知智能体 {agent_id} 初始技能状态失败: {e}")
        
        # 立即通知新注册的智能体当前专家角色状态
        if hasattr(agent_instance, 'on_agents_changed'):
            try:
                agent_instance.on_agents_changed(self._active_agents)
            except Exception as e:
                print(f"[AgentRegistry] 通知智能体 {agent_id} 初始专家角色状态失败: {e}")
    
    def unregister(self, agent_id: str):
        """取消注册智能体"""
        if agent_id in self._agents:
            del self._agents[agent_id]
            del self._metadata[agent_id]
            print(f"[AgentRegistry] 取消注册智能体: {agent_id}")
    
    def get_agent(self, agent_id: str) -> Optional[Any]:
        """获取指定智能体实例"""
        return self._agents.get(agent_id)
    
    def get_all_agents(self) -> Dict[str, Any]:
        """获取所有已注册的智能体"""
        return self._agents.copy()
    
    def notify_skill_change(self, active_skills: Set[str]):
        """
        通知所有智能体技能变化（核心方法）
        
        由 SkillsPanel 或技能管理模块调用
        
        Args:
            active_skills: 新的已启用技能集合
        """
        old_skills = self._active_skills.copy()
        self._active_skills = active_skills
        
        # 计算变化
        added = active_skills - old_skills
        removed = old_skills - active_skills
        
        if added:
            print(f"[AgentRegistry] 新增技能: {added}")
        if removed:
            print(f"[AgentRegistry] 移除技能: {removed}")
        
        # 通知所有已注册的智能体
        for agent_id, agent in self._agents.items():
            if hasattr(agent, 'on_skills_changed'):
                try:
                    agent.on_skills_changed(active_skills)
                    print(f"[AgentRegistry] 已通知智能体: {agent_id}")
                except Exception as e:
                    print(f"[AgentRegistry] 通知智能体 {agent_id} 失败: {e}")
    
    def notify_agent_change(self, active_agents: Set[str]):
        """
        通知所有智能体专家角色变化（核心方法）
        
        由 SkillsPanel 或专家角色管理模块调用
        
        Args:
            active_agents: 新的已启用专家角色集合
        """
        old_agents = self._active_agents.copy()
        self._active_agents = active_agents
        
        # 计算变化
        added = active_agents - old_agents
        removed = old_agents - active_agents
        
        if added:
            print(f"[AgentRegistry] 新增专家角色: {added}")
        if removed:
            print(f"[AgentRegistry] 移除专家角色: {removed}")
        
        # 通知所有已注册的智能体
        for agent_id, agent in self._agents.items():
            if hasattr(agent, 'on_agents_changed'):
                try:
                    agent.on_agents_changed(active_agents)
                    print(f"[AgentRegistry] 已通知智能体（专家角色）: {agent_id}")
                except Exception as e:
                    print(f"[AgentRegistry] 通知智能体 {agent_id} 专家角色变化失败: {e}")
    
    def get_active_skills(self) -> Set[str]:
        """获取当前已启用的技能列表"""
        return self._active_skills.copy()
    
    def get_active_agents(self) -> Set[str]:
        """获取当前已启用的专家角色列表"""
        return self._active_agents.copy()
    
    def load_content(self, name: str, content_type: str = "skill") -> Optional[str]:
        """
        加载技能或专家角色内容（支持拆分大文件）
        
        支持的文件结构：
        - name/SKILL.md          (主文件，必需)
        - name/DETAILS.md        (详细信息，可选)
        - name/EXAMPLES.md       (示例，可选)
        - name/NOTES.md          (注意事项，可选)
        - name/*.md              (其他 .md 文件，可选)
        
        Args:
            name: 技能或专家角色名称
            content_type: "skill" 或 "agent"
        
        Returns:
            合并后的内容字符串，如果找不到返回 None
        """
        # 搜索路径（优先级顺序）--- 不要兼容旧的路径
        search_dirs = [
            Path.home() / ".workbuddy" / "skills",                   # 用户级（最高优先级）
            Path("d:/mhzyapp/LivingTreeAlAgent/.livingtree/skills"),  # 项目内置
        ]
        
        for skills_dir in search_dirs:
            if not skills_dir.exists():
                continue
            
            # 在 mattpocock 子目录中查找（技能）
            mattpocock_dir = skills_dir / "mattpocock"
            if mattpocock_dir.exists():
                skill_dir_path = mattpocock_dir / name
                if skill_dir_path.exists():
                    return self._load_skill_directory(skill_dir_path, name)
            
            # 在 agency-agents-zh 子目录中查找（技能或专家角色）
            agency_dir = skills_dir / "agency-agents-zh"
            if agency_dir.exists():
                skill_dir_path = agency_dir / name
                if skill_dir_path.exists():
                    return self._load_skill_directory(skill_dir_path, name)
            
            # 直接在技能目录中查找（如果名称就是目录名）
            skill_dir_path = skills_dir / name
            if skill_dir_path.exists():
                return self._load_skill_directory(skill_dir_path, name)
        
        print(f"[AgentRegistry] 找不到{content_type}: {name}")
        return None
    
    def _load_skill_directory(self, skill_dir: Path, skill_name: str) -> str:
        """
        加载技能/专家角色目录下的所有 .md 文件，合并为一个字符串
        
        加载顺序：
        1. SKILL.md (必需，主文件)
        2. DETAILS.md (可选，详细说明）
        3. EXAMPLES.md (可选，示例）
        4. NOTES.md (可选，注意事项）
        5. 其他 *.md 文件（按文件名排序）
        
        Args:
            skill_dir: 技能目录路径
            skill_name: 技能名称（用于日志）
        
        Returns:
            合并后的内容字符串
        """
        if not skill_dir.is_dir():
            return ""
        
        # 定义加载顺序
        priority_files = ["SKILL.md", "DETAILS.md", "EXAMPLES.md", "NOTES.md"]
        
        md_files = []
        other_md_files = []
        
        # 遍历目录下的所有 .md 文件
        for md_file in skill_dir.glob("*.md"):
            if md_file.name in priority_files:
                md_files.append(md_file)
            else:
                other_md_files.append(md_file)
        
        # 按优先级排序
        sorted_md_files = []
        for priority_name in priority_files:
            for md_file in md_files:
                if md_file.name == priority_name:
                    sorted_md_files.append(md_file)
                    break
        
        # 添加其他 .md 文件（按文件名排序）
        other_md_files.sort(key=lambda x: x.name)
        sorted_md_files.extend(other_md_files)
        
        # 如果没有找到任何 .md 文件，返回空字符串
        if not sorted_md_files:
            print(f"[AgentRegistry] 目录中没有 .md 文件: {skill_dir}")
            return ""
        
        # 合并所有文件内容
        parts = []
        for md_file in sorted_md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                parts.append(f"\n\n## 文件: {md_file.name}\n\n")
                parts.append(content)
            except Exception as e:
                print(f"[AgentRegistry] 读取文件失败 {md_file}: {e}")
        
        print(f"[AgentRegistry] 已加载 {skill_name} ({len(sorted_md_files)} 个文件)")
        return "\n".join(parts)
    
    # 兼容旧代码（已废弃，保留仅用于过渡）
    def load_skill_content(self, skill_name: str) -> Optional[str]:
        """兼容旧代码：加载技能内容"""
        return self.load_content(skill_name, content_type="skill")


def get_agent_registry() -> AgentRegistry:
    """获取 AgentRegistry 单例"""
    return AgentRegistry()
