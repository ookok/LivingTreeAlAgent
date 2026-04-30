"""
🌐 环评专家思考模式控制器（动态版）

自动扫描 .livingtree/skills/ 加载专家角色，无需手动注册。
支持：
1. 沉浸式思考模式 - 专家第一人称内心独白
2. 分析式思考模式 - 纯逻辑分析
3. 引导式思考模式 - 分步骤引导
4. 自动匹配专家 - 根据用户输入自动选择合适的专家

Author: LivingTreeAI Agent
Date: 2026-04-27
Version: 2.0 (动态加载版)
"""

import logging
import re
from typing import Dict, List, Optional, Any
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

# 延迟导入，避免循环导入
_emotion_perception = None


def _get_emotion_perception():
    """获取情绪感知器（延迟加载）"""
    global _emotion_perception
    if _emotion_perception is None:
        try:
            from business.emotion_perception import (
                get_emotion_perception, EmotionType as EPEmotionType
            )
            _emotion_perception = get_emotion_perception()
        except ImportError as e:
            logger.warning(f"情绪感知模块导入失败: {e}")
            return None
    return _emotion_perception


# ============= 思考模式枚举（保留） =============

class ThinkingMode(Enum):
    """思考模式"""
    DEFAULT = "default"           # 默认模式（模型自动选择）
    IMMERSIVE = "immersive"       # 沉浸式（专家内心独白）
    ANALYTICAL = "analytical"     # 分析式（纯逻辑分析）
    GUIDED = "guided"             # 引导式（注重引导和建议，适合困惑用户）


# ============= 动态专家加载器 =============

class ExpertSkillLoader:
    """
    自动扫描 .livingtree/skills/ 加载专家角色

    扫描规则：
    1. 递归扫描所有子目录中的 SKILL.md 文件
    2. 解析 frontmatter（YAML 格式，--- 包裹）
    3. 提取核心能力列表
    4. 建立专家名称 → 元数据的映射
    """

    def __init__(self, skills_root: str = ".livingtree/skills"):
        # 解析为绝对路径（相对于项目根目录）
        self.skills_root = Path(skills_root)
        if not self.skills_root.is_absolute():
            # 尝试找到项目根目录（包含 client/ 目录的父目录）
            p = Path(__file__).resolve().parents[4]
            self.skills_root = p / skills_root

        self.experts: Dict[str, Dict[str, Any]] = {}  # name -> metadata
        self._load_all_experts()

    def _load_all_experts(self):
        """扫描所有 SKILL.md 文件并加载"""
        if not self.skills_root.exists():
            logger.warning(f"[ExpertSkillLoader] 技能目录不存在: {self.skills_root}")
            return

        for skill_md in self.skills_root.rglob("SKILL.md"):
            try:
                metadata = self._parse_skill_file(skill_md)
                if metadata and metadata.get("name"):
                    self.experts[metadata["name"]] = metadata
                    logger.info(f"[ExpertSkillLoader] 加载专家: {metadata['name']}")
            except Exception as e:
                logger.warning(f"[ExpertSkillLoader] 加载失败 {skill_md}: {e}")

        logger.info(f"[ExpertSkillLoader] 共加载 {len(self.experts)} 个专家角色")

    def _parse_skill_file(self, skill_md: Path) -> Optional[Dict[str, Any]]:
        """
        解析 SKILL.md 文件

        提取：
        1. frontmatter（--- 之间的 YAML）
        2. 核心能力列表（## 核心能力 章节）
        3. 工作流程摘要（## 工作流程 章节）
        """
        try:
            content = skill_md.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"[ExpertSkillLoader] 读取失败 {skill_md}: {e}")
            return None

        metadata = {
            "name": "",
            "description": "",
            "location": "",
            "domain": "",
            "industry_code": "",
            "capabilities": [],
            "workflow": [],
            "content": content,
            "path": str(skill_md),
        }

        # ── 解析 frontmatter ─────────────────────────────
        fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL | re.MULTILINE)
        if fm_match:
            for line in fm_match.group(1).split("\n"):
                line = line.strip()
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip()
                    val = val.strip()
                    if key in metadata:
                        metadata[key] = val

        # ── 解析核心能力 ───────────────────────────────
        cap_section = self._extract_section(content, "核心能力", ["工作流程", "常见问题", "输出模板"])
        if cap_section:
            for line in cap_section.split("\n"):
                line = line.strip()
                if line.startswith("- **"):
                    # 格式：- **能力名称** - 能力描述
                    m = re.match(r"-\s+\*\*(.+?)\*\*\s*-\s*(.+)", line)
                    if m:
                        metadata["capabilities"].append(m.group(1))
                    else:
                        # 格式：- **能力名称**
                        m2 = re.match(r"-\s+\*\*(.+?)\*\*", line)
                        if m2:
                            metadata["capabilities"].append(m2.group(1))
                elif line.startswith("- "):
                    metadata["capabilities"].append(line[2:].strip())

        # ── 解析工作流程 ───────────────────────────────
        wf_section = self._extract_section(content, "工作流程", ["常见问题", "输出模板", "行业分类"])
        if wf_section:
            for line in wf_section.split("\n"):
                line = line.strip()
                if re.match(r"^\d+\.", line):
                    metadata["workflow"].append(line.split(".", 1)[1].strip())

        return metadata if metadata["name"] else None

    def _extract_section(self, content: str, section_name: str, stop_sections: List[str]) -> Optional[str]:
        """
        提取 Markdown 中指定章节的内容

        Args:
            content: 文件内容
            section_name: 章节名称（如 "核心能力"）
            stop_sections: 遇到这些章节名时停止提取

        Returns:
            章节内容字符串，未找到返回 None
        """
        pattern = rf"##\s+{re.escape(section_name)}\s*\n(.*?)(?=\n##|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return None

        section = match.group(1).strip()

        # 遇到停止章节时截断
        for stop in stop_sections:
            stop_pattern = rf"\n##\s+{re.escape(stop)}\s*\n"
            m = re.search(stop_pattern, section)
            if m:
                section = section[:m.start()]
                break

        return section.strip()

    def match_expert(self, user_query: str) -> Optional[str]:
        """
        根据用户输入自动匹配最合适的专家

        匹配策略（按优先级）：
        1. 专家名称直接出现在查询中（权重 +10）
        2. domain 出现在查询中（权重 +5）
        3. description 中的关键词匹配（权重 +3）
        4. 核心能力关键词匹配（权重 +1）

        Args:
            user_query: 用户输入

        Returns:
            匹配的专家名称，未匹配返回 None
        """
        query_lower = user_query.lower()
        best_match = None
        best_score = 0

        for name, expert in self.experts.items():
            score = 0
            name_lower = name.lower()
            domain = expert.get("domain", "")
            description = expert.get("description", "")

            # 1. 专家名称直接匹配（权重最高）
            if name_lower in query_lower:
                score += 10

            # 2. domain 匹配
            if domain and domain.lower() in query_lower:
                score += 5

            # 3. description 关键词匹配
            if description:
                for word in re.findall(r"[\w\u4e00-\u9fff]+", description.lower()):
                    if len(word) > 1 and word in query_lower:
                        score += 3

            # 4. 核心能力关键词匹配
            for cap in expert.get("capabilities", []):
                cap_words = re.findall(r"[\w\u4e00-\u9fff]+", cap.lower())
                for word in cap_words:
                    if len(word) > 1 and word in query_lower:
                        score += 1
                        break

            if score > best_score:
                best_score = score
                best_match = name

        if best_match:
            logger.info(f"[ExpertSkillLoader] 匹配专家: {best_match} (score={best_score})")
        else:
            logger.info(f"[ExpertSkillLoader] 未找到匹配专家，查询: {user_query[:50]}...")

        return best_match

    def get_expert(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定专家的信息"""
        return self.experts.get(name)

    def list_experts(self) -> List[str]:
        """列出所有已加载的专家名称"""
        return list(self.experts.keys())

    def reload(self):
        """重新扫描加载所有专家（热更新）"""
        self.experts.clear()
        self._load_all_experts()


# ============= 动态思考指令生成器 =============

class DynamicThinkingInstructionGenerator:
    """
    根据专家 SKILL.md 动态生成思考指令

    不再硬编码指令字符串，而是根据专家的：
    1. name（专家名称）
    2. domain（专业领域）
    3. capabilities（核心能力列表）
    4. workflow（工作流程）

    动态填充指令模板，实现完全解耦。
    """

    @classmethod
    def generate(cls, expert: Dict[str, Any], mode: ThinkingMode) -> str:
        """
        根据专家信息和思考模式生成指令

        Args:
            expert: 专家信息字典（来自 ExpertSkillLoader）
            mode: 思考模式

        Returns:
            指令字符串（注入到 system prompt）
        """
        name = expert.get("name", "专家")
        domain = expert.get("domain", "相关")
        capabilities = expert.get("capabilities", [])

        # 将核心能力格式化为简短描述
        cap_desc = "、".join(capabilities[:4]) if capabilities else "专业分析"

        if mode == ThinkingMode.IMMERSIVE:
            return cls._template_immersive(name, domain, cap_desc)
        elif mode == ThinkingMode.ANALYTICAL:
            return cls._template_analytical(name, domain, cap_desc)
        elif mode == ThinkingMode.GUIDED:
            return cls._template_guided(name, domain)
        return ""

    @classmethod
    def _template_immersive(cls, name: str, domain: str, cap_desc: str) -> str:
        return f"""【{name}思考模式】
在你的思考过程（thinking字段）中，请以{name}的第一人称视角进行专业思考：

1. **内心专业独白**：用"我需要..."、"根据{domain}规范..."、"需要注意..."等第一人称表达
2. **展现专业判断过程**：体现{name}的谨慎性和专业性
3. **思考要素**：
   - {cap_desc}
   - 数据/信息完整性检查
   - 标准/规范适用性判断
   - 不确定性评估
4. **示例思考风格**：
   "我需要先核实相关信息...根据{domain}规范...需要确认关键参数...这个方案的合理性需要评估..."

请严格按照上述风格进行思考，让思考过程展现{name}的专业判断过程。
"""

    @classmethod
    def _template_analytical(cls, name: str, domain: str, cap_desc: str) -> str:
        return f"""【{name}分析模式】
在你的思考过程（thinking字段）中，请进行纯逻辑的专业分析，避免第一人称内心独白：

1. **禁止第一人称表达**：不使用"我觉得"、"我需要"等表达
2. **结构化分析**：按照{domain}技术路线进行逻辑分析
3. **分析要素（按序）**：
   - 信息完整性评估
   - {cap_desc}
   - 结论/建议的可行性判断
   - 不确定性分析
4. **示例分析风格**：
   "信息完整性评估：需确认...规范适用性：执行{domain}相关标准...分析：首先...其次...最后..."

请严格按照上述风格进行思考，确保分析过程严谨、逻辑清晰。
"""

    @classmethod
    def _template_guided(cls, name: str, domain: str) -> str:
        return f"""【{name}引导模式】
在你的思考过程（thinking字段）中，请注重引导和建议，帮助用户理解和决策：

1. **引导式思考**：用"建议..."、"可以考虑..."、"下一步..."等引导性表达
2. **分步骤规划**：将复杂问题分解为简单步骤
3. **思考要素**：
   - 用户当前困惑点识别
   - 分步骤解决方案设计
   - 每个步骤的具体操作指引
   - {domain}相关的注意事项
4. **示例思考风格**：
   "用户不清楚如何操作...我需要引导他：第一步，先了解基本情况；第二步，分析关键问题；第三步，给出可行建议...我应该给出一个清晰的步骤说明，让用户一目了然..."

请严格按照上述风格进行思考，让思考过程体现引导性和帮助性。
"""


# ============= 专家思考模式控制器（重构版） =============

class ExpertThinkingModeController:
    """
    专家思考模式控制器（动态版）

    功能：
    1. 自动扫描 .livingtree/skills/ 加载专家（无需手动注册）
    2. 自动匹配用户问题到合适专家
    3. 动态生成思考风格指令（基于 SKILL.md 内容）
    4. 支持情绪感知自动调整思考模式
    5. 支持手动指定专家名称和思考模式
    """

    def __init__(self, skills_root: str = ".livingtree/skills"):
        self._loader = ExpertSkillLoader(skills_root)
        self._current_expert_name: Optional[str] = None
        self._current_mode: ThinkingMode = ThinkingMode.DEFAULT
        self._emotional_state: Optional[Dict] = None
        self._auto_adjust_by_emotion: bool = True

        expert_count = len(self._loader.list_experts())
        logger.info(f"[ExpertThinkingModeController] 初始化完成，已加载 {expert_count} 个专家")

    # ── 专家设置 ─────────────────────────────────────

    def set_expert_by_name(self, expert_name: str) -> bool:
        """
        设置专家（按名称精确匹配）

        Args:
            expert_name: 专家名称（需与 SKILL.md 中的 name 字段一致）

        Returns:
            是否设置成功
        """
        if expert_name in self._loader.experts:
            self._current_expert_name = expert_name
            logger.info(f"[ExpertThinkingModeController] 专家设置为: {expert_name}")
            return True
        else:
            logger.warning(f"[ExpertThinkingModeController] 未找到专家: {expert_name}")
            return False

    def set_expert_by_query(self, user_query: str) -> Optional[str]:
        """
        根据用户输入自动匹配并设置专家

        Args:
            user_query: 用户输入

        Returns:
            匹配的专家名称，未匹配返回 None
        """
        matched = self._loader.match_expert(user_query)
        if matched:
            self._current_expert_name = matched
            logger.info(f"[ExpertThinkingModeController] 自动匹配专家: {matched}")
        else:
            logger.info("[ExpertThinkingModeController] 未找到匹配专家，保持当前专家")
        return matched

    def get_current_expert(self) -> Optional[Dict[str, Any]]:
        """获取当前专家信息"""
        if self._current_expert_name:
            return self._loader.get_expert(self._current_expert_name)
        return None

    # ── 思考模式设置 ─────────────────────────────────

    def set_thinking_mode(self, mode: ThinkingMode):
        """设置思考模式"""
        self._current_mode = mode
        logger.info(f"[ExpertThinkingModeController] 思考模式设置为: {mode.value}")

    def set_thinking_mode_by_name(self, mode_name: str) -> bool:
        """
        按名称设置思考模式

        Args:
            mode_name: "default" / "immersive" / "analytical" / "guided"

        Returns:
            是否设置成功
        """
        try:
            self._current_mode = ThinkingMode(mode_name)
            logger.info(f"[ExpertThinkingModeController] 思考模式设置为: {mode_name}")
            return True
        except ValueError:
            logger.warning(f"[ExpertThinkingModeController] 未知的思考模式: {mode_name}")
            return False

    # ── 情绪感知 ─────────────────────────────────────

    def set_emotional_state(self, emotion_type: str, intensity: float = 0.5):
        """设置用户情绪状态，自动调整思考模式"""
        self._emotional_state = {
            "emotion_type": emotion_type,
            "intensity": intensity
        }

        if self._auto_adjust_by_emotion:
            self._adjust_thinking_mode_by_emotion()

        logger.info(f"[ExpertThinkingModeController] 情绪状态设置为: {emotion_type} (强度: {intensity})")

    def set_auto_adjust_by_emotion(self, enabled: bool):
        """设置是否根据情绪自动调整思考模式"""
        self._auto_adjust_by_emotion = enabled
        logger.info(f"[ExpertThinkingModeController] 情绪自动调整: {'启用' if enabled else '禁用'}")

    def _adjust_thinking_mode_by_emotion(self):
        """根据情绪自动调整思考模式"""
        if self._emotional_state is None:
            return

        emotion_type = self._emotional_state["emotion_type"]
        intensity = self._emotional_state["intensity"]

        # 负面情绪 + 高强度 → 分析式
        if emotion_type in ["anger", "anxious", "frustrated", "disappointed", "worried"]:
            if intensity > 0.7:
                self._current_mode = ThinkingMode.ANALYTICAL
                logger.info(f"[情绪感知] 检测到高强度负面情绪({emotion_type})，切换到分析式思考")
            else:
                self._current_mode = ThinkingMode.GUIDED
                logger.info(f"[情绪感知] 检测到低强度负面情绪({emotion_type})，切换到引导式思考")

        # 困惑情绪 → 引导式
        elif emotion_type in ["confused", "lost", "helpless"]:
            self._current_mode = ThinkingMode.GUIDED
            logger.info(f"[情绪感知] 检测到困惑情绪({emotion_type})，切换到引导式思考")

        # 正面情绪 → 沉浸式
        elif emotion_type in ["joy", "happy", "satisfied", "excited", "relieved"]:
            self._current_mode = ThinkingMode.IMMERSIVE
            logger.info(f"[情绪感知] 检测到正面情绪({emotion_type})，切换到沉浸式思考")

        # 中性情绪 → 保持当前模式或默认使用沉浸式
        else:
            if self._current_mode == ThinkingMode.DEFAULT:
                self._current_mode = ThinkingMode.IMMERSIVE
            logger.info(f"[情绪感知] 检测到中性情绪({emotion_type})，保持当前模式: {self._current_mode.value}")

    def _generate_emotion_instruction(self) -> str:
        """生成情绪适配指令"""
        if self._emotional_state is None:
            return ""

        emotion_type = self._emotional_state["emotion_type"]
        intensity = self._emotional_state["intensity"]

        emotion_instructions = {
            "anger": f"用户当前情绪：愤怒（强度{intensity}）。请保持冷静、专业，避免激化情绪。先倾听，再给出解决方案。",
            "anxious": f"用户当前情绪：焦虑（强度{intensity}）。请提供清晰、确定的信息，避免模糊表述。给出具体步骤。",
            "frustrated": f"用户当前情绪：沮丧（强度{intensity}）。请给予鼓励和支持，提供可行的解决方案。",
            "disappointed": f"用户当前情绪：失望（强度{intensity}）。请承认问题，提供补救措施。",
            "worried": f"用户当前情绪：担忧（强度{intensity}）。请提供客观数据和事实，缓解不必要的担心。",
            "confused": f"用户当前情绪：困惑（强度{intensity}）。请使用引导式回复，分步骤解释，避免使用专业术语。",
            "lost": f"用户当前情绪：迷茫（强度{intensity}）。请提供清晰的指引和方向建议。",
            "helpless": f"用户当前情绪：无助（强度{intensity}）。请提供具体的、可操作的建议，给予支持。",
            "joy": f"用户当前情绪：喜悦（强度{intensity}）。可以使用轻松、亲切的语气，适当使用表情符号。",
            "happy": f"用户当前情绪：开心（强度{intensity}）。可以使用亲切、友好的语气。",
            "satisfied": f"用户当前情绪：满意（强度{intensity}）。可以保持专业且友好的语气。",
            "excited": f"用户当前情绪：兴奋（强度{intensity}）。可以分享用户的兴奋，使用积极的语气。",
            "relieved": f"用户当前情绪：释然（强度{intensity}）。可以轻松交流的语气。",
        }

        return emotion_instructions.get(emotion_type, "")

    # ── 指令生成与注入 ─────────────────────────────

    def get_enhanced_system_prompt(self, base_system_prompt: str) -> str:
        """
        获取增强后的 System Prompt（注入思考风格指令 + 情绪适配指令）

        Args:
            base_system_prompt: 基础 System Prompt

        Returns:
            增强后的 System Prompt
        """
        # 默认模式，不注入指令
        if self._current_mode == ThinkingMode.DEFAULT:
            return base_system_prompt

        # 如果没有设置专家，尝试自动匹配
        if self._current_expert_name is None:
            logger.info("[ExpertThinkingModeController] 未设置专家，尝试自动匹配...")
            self.set_expert_by_query(base_system_prompt[:200])

        # 如果还是没有专家，使用默认（不注入）
        if self._current_expert_name is None:
            logger.warning("[ExpertThinkingModeController] 未找到合适专家，不注入思考指令")
            return base_system_prompt

        # 获取专家信息
        expert = self._loader.get_expert(self._current_expert_name)
        if not expert:
            logger.warning(f"[ExpertThinkingModeController] 专家信息丢失: {self._current_expert_name}")
            return base_system_prompt

        # 生成思考风格指令
        thinking_instruction = DynamicThinkingInstructionGenerator.generate(
            expert, self._current_mode
        )

        if not thinking_instruction:
            return base_system_prompt

        # 获取情绪适配指令
        emotion_instruction = self._generate_emotion_instruction()

        # 注入到 System Prompt 末尾
        enhanced_prompt = f"{base_system_prompt}\n\n{thinking_instruction}"
        if emotion_instruction:
            enhanced_prompt += f"\n\n{emotion_instruction}"

        logger.info(
            f"[ExpertThinkingModeController] 已注入思考指令: "
            f"expert={self._current_expert_name}, mode={self._current_mode.value}, "
            f"emotion={self._emotional_state['emotion_type'] if self._emotional_state else 'none'}"
        )

        return enhanced_prompt

    def inject_to_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        将思考指令和情绪适配指令注入到消息列表中

        Args:
            messages: 消息列表

        Returns:
            注入后的消息列表（新列表，不修改原列表）
        """
        if self._current_mode == ThinkingMode.DEFAULT:
            return messages

        # 如果没有设置专家，尝试从第一条用户消息自动匹配
        if self._current_expert_name is None:
            for msg in messages:
                if msg.get("role") == "user":
                    self.set_expert_by_query(msg.get("content", ""))
                    break

        if self._current_expert_name is None:
            return messages

        expert = self._loader.get_expert(self._current_expert_name)
        if not expert:
            return messages

        thinking_instruction = DynamicThinkingInstructionGenerator.generate(
            expert, self._current_mode
        )

        if not thinking_instruction:
            return messages

        emotion_instruction = self._generate_emotion_instruction()
        full_instruction = thinking_instruction
        if emotion_instruction:
            full_instruction += f"\n\n{emotion_instruction}"

        # 复制到新列表（避免修改原列表）
        new_messages = [msg.copy() for msg in messages]

        # 策略1：注入到 system prompt
        has_system = False
        for msg in new_messages:
            if msg.get("role") == "system":
                msg["content"] = f"{msg['content']}\n\n{full_instruction}"
                has_system = True
                logger.info("[ExpertThinkingModeController] 思考指令+情绪指令已注入到system prompt")
                break

        # 策略2：如果没有 system prompt，注入到首条用户消息
        if not has_system:
            for msg in new_messages:
                if msg.get("role") == "user":
                    msg["content"] = f"{msg['content']}\n\n{full_instruction}"
                    logger.info("[ExpertThinkingModeController] 思考指令+情绪指令已注入到首条用户消息")
                    break

        return new_messages

    # ── 配置查询 ─────────────────────────────────────

    def get_current_config(self) -> Dict[str, str]:
        """获取当前配置"""
        return {
            "expert_name": self._current_expert_name or "none",
            "thinking_mode": self._current_mode.value,
            "auto_adjust_by_emotion": str(self._auto_adjust_by_emotion),
        }

    def list_available_experts(self) -> List[str]:
        """列出所有可用专家名称"""
        return self._loader.list_experts()

    def reload_experts(self):
        """重新加载所有专家（热更新）"""
        self._loader.reload()
        logger.info(f"[ExpertThinkingModeController] 已重新加载专家，当前共 {len(self._loader.list_experts())} 个")


# ============= 全局单例 =============

_default_controller: Optional[ExpertThinkingModeController] = None


def get_expert_thinking_controller() -> ExpertThinkingModeController:
    """
    获取专家思考模式控制器（单例）

    Returns:
        ExpertThinkingModeController 实例
    """
    global _default_controller

    if _default_controller is None:
        _default_controller = ExpertThinkingModeController()

    return _default_controller


# ============= 便捷函数 =============

def set_expert_thinking_mode(expert_name: str, mode_name: str = "immersive"):
    """
    便捷函数：设置专家思考模式

    Args:
        expert_name: 专家名称（与 SKILL.md 中的 name 字段一致，
                      也接受 "auto" 表示自动匹配）
        mode_name: 思考模式名称（"default" / "immersive" / "analytical" / "guided"）
    """
    controller = get_expert_thinking_controller()

    # 设置思考模式
    controller.set_thinking_mode_by_name(mode_name)

    # 设置专家（auto 表示下次调用时自动匹配）
    if expert_name != "auto":
        controller.set_expert_by_name(expert_name)


def enhance_messages_with_thinking_mode(messages: List[Dict[str, str]],
                                        expert_name: str = "auto",
                                        mode_name: str = "immersive") -> List[Dict[str, str]]:
    """
    便捷函数：为消息列表注入思考模式指令

    Args:
        messages: 原始消息列表
        expert_name: 专家名称（"auto" 表示自动匹配）
        mode_name: 思考模式名称

    Returns:
        注入后的消息列表
    """
    controller = get_expert_thinking_controller()

    # 设置模式和专家
    controller.set_thinking_mode_by_name(mode_name)
    if expert_name != "auto":
        controller.set_expert_by_name(expert_name)
    else:
        # 从消息中自动匹配
        for msg in messages:
            if msg.get("role") == "user":
                controller.set_expert_by_query(msg.get("content", ""))
                break

    return controller.inject_to_messages(messages)


def auto_match_and_enhance(prompt: str, base_system_prompt: str = "") -> str:
    """
    便捷函数：自动匹配专家并增强 System Prompt

    Args:
        prompt: 用户输入（用于匹配专家）
        base_system_prompt: 基础 System Prompt

    Returns:
        增强后的 System Prompt
    """
    controller = get_expert_thinking_controller()
    controller.set_expert_by_query(prompt)
    return controller.get_enhanced_system_prompt(base_system_prompt or "你是一个专业的AI助手。")


# ============= 测试代码 =============

if __name__ == "__main__":
    print("=" * 60)
    print("专家思考模式控制器测试（动态版 v2.0）")
    print("=" * 60)

    # 初始化控制器
    controller = get_expert_thinking_controller()

    # 列出所有已加载的专家
    experts = controller.list_available_experts()
    print(f"\n已加载 {len(experts)} 个专家:")
    for i, name in enumerate(experts, 1):
        print(f"  {i}. {name}")

    # 测试自动匹配
    test_queries = [
        "帮我分析这个化工项目的环境影响",
        "生产工艺流程怎么优化？",
        "设备选型要注意什么？",
        "应急预案怎么编制？",
    ]

    print(f"\n{'─' * 60}")
    print("测试自动匹配:")
    print(f"{'─' * 60}")
    for query in test_queries:
        matched = controller.set_expert_by_query(query)
        config = controller.get_current_config()
        print(f"查询: {query[:30]}...")
        print(f"  匹配专家: {config['expert_name']}, 模式: {config['thinking_mode']}")
        print()

    # 测试注入 System Prompt
    print(f"{'─' * 60}")
    print("测试注入 System Prompt:")
    print(f"{'─' * 60}")
    base_prompt = "你是一个专业的AI助手，擅长环保领域的问题。"

    # 测试1：自动匹配 + 沉浸式
    controller.set_thinking_mode_by_name("immersive")
    controller.set_expert_by_query("化工项目的废水怎么处理？")
    enhanced = controller.get_enhanced_system_prompt(base_prompt)
    print(f"增强后 System Prompt (前300字符):")
    print(enhanced[:300] + "...")
    print()

    # 测试2：引导式
    controller.set_thinking_mode_by_name("guided")
    enhanced2 = controller.get_enhanced_system_prompt(base_prompt)
    print(f"引导式 (前200字符):")
    print(enhanced2[:200] + "...")
    print()

    print("=" * 60)
    print("✅ 测试完成")
    print("=" * 60)
