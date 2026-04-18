"""
创作模式模块
Creative Mode Module

专注于创意写作的需求：
- 灵感引擎
- 沉浸写作
- 非线性写作支持
- 风格模仿
- 感官描写库
"""

import re
import random
import hashlib
from typing import Optional, Callable, Any, Generator
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json


class WritingGenre(Enum):
    """写作类型"""
    Novel = "novel"              # 小说
    ShortStory = "short_story"   # 短篇小说
    Script = "script"           # 剧本
    Poetry = "poetry"           # 诗歌
    Essay = "essay"             # 散文
    Fantasy = "fantasy"         # 奇幻
    SciFi = "scifi"             # 科幻
    Romance = "romance"         # 言情
    Mystery = "mystery"          # 悬疑
    Horror = "horror"           # 恐怖
    Literary = "literary"       # 纯文学


class NarrativeVoice(Enum):
    """叙事视角"""
    FirstPerson = "first_person"      # 第一人称
    ThirdPerson = "third_person"      # 第三人称
    Omniscient = "omniscient"         # 全知视角
    Limited = "limited"              # 有限第三人称


class EmotionalTone(Enum):
    """情感基调"""
    Tense = "tense"                 # 紧张
    Calm = "calm"                   # 平静
    Melancholy = "melancholy"       # 忧郁
    Joyful = "joyful"               # 欢快
    Mysterious = "mysterious"       # 神秘
    Romantic = "romantic"            # 浪漫
    Dark = "dark"                   # 黑暗


@dataclass
class CharacterProfile:
    """角色档案"""
    character_id: str
    name: str
    
    # 基本信息
    age: Optional[int] = None
    gender: str = ""
    occupation: str = ""
    appearance: str = ""
    
    # 性格
    personality_traits: list = field(default_factory=list)
    strengths: list = field(default_factory=list)
    weaknesses: list = field(default_factory=list)
    
    # 背景
    backstory: str = ""
    motivations: list = field(default_factory=list)
    fears: list = field(default_factory=list)
    
    # 关系
    relationships: dict = field(default_factory=dict)  # {character_id: relationship_type}
    
    # 心理
    psychology: str = ""
    speech_pattern: str = ""


@dataclass
class PlotFragment:
    """情节碎片"""
    fragment_id: str
    content: str
    genre_tags: list = field(default_factory=list)
    
    # 元数据
    position: int = 0  # 在故事中的位置
    chapter: int = 0
    scene: int = 0
    
    # 关联
    related_fragments: list = field(default_factory=list)
    characters_involved: list = field(default_factory=list)
    
    # 状态
    status: str = "draft"  # draft/completed/revised
    word_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class WorldBuilding:
    """世界观设定"""
    world_name: str
    
    # 地理
    locations: list = field(default_factory=list)
    current_location: str = ""
    
    # 历史
    history: str = ""
    key_events: list = field(default_factory=list)
    
    # 规则
    rules: list = field(default_factory=list)
    magic_system: Optional[dict] = None
    technology_level: str = ""
    
    # 文化
    cultures: list = field(default_factory=list)
    languages: dict = field(default_factory=dict)


@dataclass
class CreativeProject:
    """创作项目"""
    project_id: str
    title: str
    genre: WritingGenre
    
    # 结构
    narrative_voice: NarrativeVoice = NarrativeVoice.ThirdPerson
    emotional_tone: EmotionalTone = EmotionalTone.Calm
    
    # 内容
    synopsis: str = ""
    characters: list[CharacterProfile] = field(default_factory=list)
    fragments: list[PlotFragment] = field(default_factory=list)
    world: Optional[WorldBuilding] = None
    
    # 元数据
    target_word_count: int = 50000
    current_word_count: int = 0
    status: str = "planning"  # planning/writing/revising/completed
    
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class InspirationEngine:
    """
    灵感引擎
    
    提供创意激发功能：
    - 随机词组合
    - 意象联想
    - 情节冲突生成
    - 人物关系图谱
    """
    
    # 感官描写词库
    SENSORY_LIBRARIES = {
        "visual": [
            "微光", "深邃", "斑驳", "璀璨", "朦胧", "耀眼", "黯淡",
            "流转", "闪烁", "柔和", "刺眼", "柔和", "流动", "静谧",
            "光影", "色彩", "层次", "质感", "轮廓", "纹理"
        ],
        "auditory": [
            "低语", "轰鸣", "回响", "寂静", "嘈杂", "清脆", "沙哑",
            "悠扬", "刺耳", "轻柔", "轰鸣", "窸窣", "轰鸣", "呢喃",
            "滴答", "呼啸", "拍打", "流淌", "震颤"
        ],
        "olfactory": [
            "芬芳", "腐朽", "清新", "浓郁", "刺鼻", "幽香", "甜腻",
            "苦涩", "木质", "花香", "泥土", "烟熏", "金属", "海风"
        ],
        "tactile": [
            "粗糙", "光滑", "温热", "冰凉", "柔软", "坚硬", "黏腻",
            "干燥", "湿润", "细腻", "粗粝", "温暖", "刺痛", "麻木"
        ],
        "gustatory": [
            "甘甜", "苦涩", "酸涩", "辛辣", "咸鲜", "清淡", "浓郁",
            "醇厚", "爽口", "油腻", "绵密", "爽脆", "柔滑"
        ],
    }
    
    # 情节元素
    PLOT_ELEMENTS = {
        "conflict": [
            "内心挣扎", "人际冲突", "生死抉择", "理想与现实",
            "过去与现在的对立", "真相与谎言", "爱与责任", "自由与束缚"
        ],
        "transformation": [
            "性格转变", "能力觉醒", "关系深化", "世界观重塑",
            "命运转折", "认知突破", "情感升华", "身份认同"
        ],
        "mystery": [
            "消失的证人", "隐藏的遗嘱", "秘密的身份", "失落的记忆",
            "可疑的行为", "矛盾的时间线", "遗失的物品", "假死"
        ],
        "tension": [
            "倒计时", "秘密监视", "身份暴露危机", "最后通牒",
            "信任危机", "资源枯竭", "规则打破", "背叛边缘"
        ],
    }
    
    # 角色原型
    CHARACTER_ARCHETYPES = [
        {"name": "英雄", "traits": ["勇敢", "正直", "成长"], "arc": "成长型"},
        {"name": "导师", "traits": ["智慧", "引导", "牺牲"], "arc": "牺牲型"},
        {"name": "阴影", "traits": ["黑暗", "诱惑", "对抗"], "arc": "对立型"},
        {"name": "伙伴", "traits": ["忠诚", "幽默", "支持"], "arc": "辅助型"},
        {"name": "变形者", "traits": ["神秘", "欺骗", "真相"], "arc": "揭示型"},
        {"name": "愚者", "traits": ["天真", "乐观", "意外"], "arc": "成长型"},
    ]
    
    def __init__(self):
        self._random = random.Random()
        self._seed()
    
    def _seed(self, seed_value: int = None):
        """设置随机种子"""
        if seed_value is None:
            seed_value = int(datetime.now().timestamp())
        self._random.seed(seed_value)
    
    def random_word_combination(
        self,
        num_words: int = 3,
        categories: list[str] = None,
    ) -> list[str]:
        """
        随机词组合生成器
        
        Args:
            num_words: 词语数量
            categories: 感官类别列表
            
        Returns:
            随机选中的词语
        """
        if categories is None:
            categories = list(self.SENSORY_LIBRARIES.keys())
        
        words = []
        for cat in categories[:num_words]:
            if cat in self.SENSORY_LIBRARIES:
                word = self._random.choice(self.SENSORY_LIBRARIES[cat])
                words.append(word)
        
        return words
    
    def generate_imagery(
        self,
        tone: EmotionalTone = None,
        setting: str = "",
    ) -> str:
        """
        生成意象描写
        
        Args:
            tone: 情感基调
            setting: 场景设定
            
        Returns:
            生成的意象描写
        """
        if tone is None:
            tone = self._random.choice(list(EmotionalTone))
        
        # 根据基调选择感官词汇
        tone_mapping = {
            EmotionalTone.Tense: ["auditory", "tactile"],
            EmotionalTone.Calm: ["visual", "olfactory"],
            EmotionalTone.Melancholy: ["visual", "auditory", "gustatory"],
            EmotionalTone.Joyful: ["visual", "auditory"],
            EmotionalTone.Mysterious: ["visual", "olfactory"],
            EmotionalTone.Romantic: ["tactile", "gustatory", "olfactory"],
            EmotionalTone.Dark: ["auditory", "tactile"],
        }
        
        categories = tone_mapping.get(tone, ["visual"])
        words = self.random_word_combination(4, categories)
        
        # 构建描写
        imagery = f"{self._random.choice(words)}的{setting}" if setting else ""
        imagery += f"，{words[0]}与{words[1]}交织"
        
        return imagery
    
    def generate_conflict(
        self,
        conflict_type: str = None,
        characters: list[CharacterProfile] = None,
    ) -> dict:
        """
        生成情节冲突
        
        Returns:
            冲突描述
        """
        if conflict_type is None:
            conflict_type = self._random.choice(list(self.PLOT_ELEMENTS.keys()))
        
        base_conflict = self._random.choice(self.PLOT_ELEMENTS.get(conflict_type, []))
        
        result = {
            "type": conflict_type,
            "description": base_conflict,
            "elements": [],
            "suggestions": [],
        }
        
        # 如果有角色，生成更具体的冲突
        if characters and len(characters) >= 2:
            char1 = characters[0]
            char2 = characters[1]
            
            result["elements"] = [
                f"{char1.name}与{char2.name}之间",
                f"涉及{char1.name}的{char1.personality_traits[0] if char1.personality_traits else '内心'}",
                f"以及{char2.name}的{char2.motivations[0] if char2.motivations else '目标'}",
            ]
            
            result["suggestions"] = [
                f"让{char1.name}在关键时刻面临艰难抉择",
                f"揭示{char2.name}隐藏的秘密",
                "制造信息不对称增加张力",
            ]
        
        return result
    
    def generate_character_hook(self, archetype: dict = None) -> str:
        """
        生成角色钩子
        
        Args:
            archetype: 角色原型
            
        Returns:
            角色设定钩子
        """
        if archetype is None:
            archetype = self._random.choice(self.CHARACTER_ARCHETYPES)
        
        hooks = [
            f"一个{archetype['name']}，他的{self._random.choice(archetype['traits'])}既是优点也是弱点",
            f"{archetype['name']}的道路注定不平坦——{self._random.choice(archetype['traits'])}将成为他最大的软肋",
            f"没有人知道这个{archetype['name']}的过去，但每个人都能感受到他的{archetype['traits'][0]}",
            f"{archetype['name']}的{archetype['arc']}轨迹将如何展开？答案藏在他的内心深处",
        ]
        
        return self._random.choice(hooks)
    
    def suggest_sensory_detail(
        self,
        sense: str,
        context: str = "",
    ) -> str:
        """
        根据情境建议感官细节
        
        Args:
            sense: 感官类型
            context: 使用情境
            
        Returns:
            建议的感官描写
        """
        library = self.SENSORY_LIBRARIES.get(sense, [])
        if not library:
            return ""
        
        word = self._random.choice(library)
        
        # 根据情境构建描写
        context_hooks = {
            "紧张": f"心跳声中夹杂着{word}",
            "平静": f"一切都沉浸在{word}之中",
            "悲伤": f"那{word}的感觉挥之不去",
            "喜悦": f"空气中弥漫着{word}",
        }
        
        # 根据关键词匹配
        for key, template in context_hooks.items():
            if key in context:
                return template
        
        return f"那{word}的感觉"


class CreativeMode:
    """
    创作模式引擎
    
    提供创意写作的专用功能
    """
    
    def __init__(self, agent=None):
        self.agent = agent
        
        # 灵感引擎
        self.inspiration = InspirationEngine()
        
        # 当前项目
        self.current_project: Optional[CreativeProject] = None
        
        # 版本管理
        self._versions: list[dict] = []
        self._current_version_index: int = -1
    
    # ==================== 项目管理 ====================
    
    def create_project(
        self,
        title: str,
        genre: WritingGenre,
        target_word_count: int = 50000,
    ) -> CreativeProject:
        """创建创作项目"""
        project = CreativeProject(
            project_id=self._generate_id(),
            title=title,
            genre=genre,
            target_word_count=target_word_count,
        )
        
        self.current_project = project
        return project
    
    def _generate_id(self) -> str:
        """生成项目ID"""
        return f"CP-{int(datetime.now().timestamp())}"
    
    def get_project_status(self) -> dict:
        """获取项目状态"""
        if not self.current_project:
            return {"status": "no_project"}
        
        p = self.current_project
        return {
            "title": p.title,
            "genre": p.genre.value,
            "progress": f"{p.current_word_count}/{p.target_word_count}",
            "progress_percent": p.current_word_count / p.target_word_count if p.target_word_count else 0,
            "status": p.status,
            "fragments": len(p.fragments),
            "characters": len(p.characters),
        }
    
    # ==================== 角色管理 ====================
    
    def create_character(
        self,
        name: str,
        archetype: dict = None,
        **kwargs,
    ) -> CharacterProfile:
        """创建角色"""
        if archetype is None:
            archetype = self.inspiration.CHARACTER_ARCHETYPES[0]
        
        character = CharacterProfile(
            character_id=self._generate_id(),
            name=name,
            personality_traits=archetype.get("traits", []),
            **kwargs,
        )
        
        if self.current_project:
            self.current_project.characters.append(character)
        
        return character
    
    def get_character(self, character_id: str) -> Optional[CharacterProfile]:
        """获取角色"""
        if not self.current_project:
            return None
        
        for char in self.current_project.characters:
            if char.character_id == character_id:
                return char
        return None
    
    def generate_character_profile(
        self,
        name: str,
        genre: WritingGenre = WritingGenre.Novel,
    ) -> CharacterProfile:
        """AI生成角色档案"""
        hook = self.inspiration.generate_character_hook()
        
        character = CharacterProfile(
            character_id=self._generate_id(),
            name=name,
            backstory=hook,
            personality_traits=self.inspiration.random_word_combination(
                3, ["visual", "tactile", "auditory"]
            ),
        )
        
        if self.current_project:
            self.current_project.characters.append(character)
        
        return character
    
    def get_relationship_map(self) -> dict:
        """获取人物关系图谱"""
        if not self.current_project:
            return {"nodes": [], "edges": []}
        
        nodes = []
        edges = []
        
        # 节点
        for char in self.current_project.characters:
            nodes.append({
                "id": char.character_id,
                "label": char.name,
                "traits": char.personality_traits[:2],
            })
        
        # 边
        for char in self.current_project.characters:
            for other_id, rel_type in char.relationships.items():
                edges.append({
                    "source": char.character_id,
                    "target": other_id,
                    "label": rel_type,
                })
        
        return {"nodes": nodes, "edges": edges}
    
    # ==================== 碎片写作 ====================
    
    def add_fragment(
        self,
        content: str,
        position: int = -1,
        **kwargs,
    ) -> PlotFragment:
        """添加情节碎片"""
        fragment = PlotFragment(
            fragment_id=self._generate_id(),
            content=content,
            word_count=len(content),
            position=position if position >= 0 else len(self.current_project.fragments),
            **kwargs,
        )
        
        if self.current_project:
            if position < 0:
                self.current_project.fragments.append(fragment)
            else:
                self.current_project.fragments.insert(position, fragment)
            
            self.current_project.current_word_count += fragment.word_count
        
        return fragment
    
    def get_fragment(self, fragment_id: str) -> Optional[PlotFragment]:
        """获取碎片"""
        if not self.current_project:
            return None
        
        for f in self.current_project.fragments:
            if f.fragment_id == fragment_id:
                return f
        return None
    
    def reorganize_fragments(
        self,
        fragment_ids: list[str],
    ) -> bool:
        """重新组织碎片顺序"""
        if not self.current_project:
            return False
        
        id_to_fragment = {f.fragment_id: f for f in self.current_project.fragments}
        
        new_order = []
        for fid in fragment_ids:
            if fid in id_to_fragment:
                new_order.append(id_to_fragment[fid])
        
        if len(new_order) != len(self.current_project.fragments):
            return False
        
        self.current_project.fragments = new_order
        return True
    
    def suggest_fragment_connection(
        self,
        fragment1: PlotFragment,
        fragment2: PlotFragment,
    ) -> str:
        """
        建议两个碎片之间的连接方式
        
        Returns:
            连接建议
        """
        suggestions = [
            f"使用时间跳转：从\"{fragment1.content[:30]}...\"直接过渡到\"{fragment2.content[:30]}...\"",
            "添加过渡场景，桥接两个情节",
            "使用蒙太奇手法，简洁连接",
            "在结尾留下悬念，自然过渡到下一段",
        ]
        
        # 如果有角色，可以更具体
        if fragment1.characters_involved and fragment2.characters_involved:
            common_chars = set(fragment1.characters_involved) & set(fragment2.characters_involved)
            if common_chars:
                suggestions.insert(
                    0,
                    f"通过共同角色{list(common_chars)[0]}串联两个场景"
                )
        
        return "\n".join(suggestions)
    
    # ==================== 时间线管理 ====================
    
    def get_timeline(self) -> list[dict]:
        """获取故事时间线"""
        if not self.current_project:
            return []
        
        events = []
        
        # 收集所有碎片的时间信息
        for i, fragment in enumerate(self.current_project.fragments):
            events.append({
                "position": fragment.position,
                "chapter": fragment.chapter,
                "scene": fragment.scene,
                "preview": fragment.content[:50] + "...",
                "characters": fragment.characters_involved,
            })
        
        return sorted(events, key=lambda x: (x["chapter"], x["scene"], x["position"]))
    
    def generate_timeline(self) -> str:
        """生成时间线文本"""
        timeline = self.get_timeline()
        
        if not timeline:
            return "[尚无时间线数据]"
        
        result = "## 故事时间线\n\n"
        
        current_chapter = -1
        for event in timeline:
            if event["chapter"] != current_chapter:
                current_chapter = event["chapter"]
                result += f"\n### 第{current_chapter}章\n"
            
            result += f"- 场景{event['scene']}: {event['preview']}\n"
        
        return result
    
    # ==================== 版本管理 ====================
    
    def save_version(self, content: str, note: str = ""):
        """保存版本"""
        version = {
            "content": content,
            "note": note,
            "timestamp": datetime.now().isoformat(),
            "word_count": len(content),
        }
        
        self._versions.append(version)
        self._current_version_index = len(self._versions) - 1
    
    def get_versions(self) -> list[dict]:
        """获取版本列表"""
        return [
            {
                "index": i,
                "timestamp": v["timestamp"],
                "note": v["note"],
                "word_count": v["word_count"],
            }
            for i, v in enumerate(self._versions)
        ]
    
    def load_version(self, index: int) -> Optional[str]:
        """加载指定版本"""
        if 0 <= index < len(self._versions):
            self._current_version_index = index
            return self._versions[index]["content"]
        return None
    
    def diff_versions(
        self,
        index1: int,
        index2: int,
    ) -> dict:
        """对比两个版本"""
        if not (0 <= index1 < len(self._versions) and 0 <= index2 < len(self._versions)):
            return {"error": "版本索引无效"}
        
        v1 = self._versions[index1]
        v2 = self._versions[index2]
        
        return {
            "version1": {
                "timestamp": v1["timestamp"],
                "word_count": v1["word_count"],
            },
            "version2": {
                "timestamp": v2["timestamp"],
                "word_count": v2["word_count"],
            },
            "word_diff": v2["word_count"] - v1["word_count"],
        }
    
    # ==================== 沉浸写作 ====================
    
    def get_immersion_settings(self) -> dict:
        """获取沉浸写作设置"""
        if not self.current_project:
            return {}
        
        genre = self.current_project.genre
        tone = self.current_project.emotional_tone
        
        # 根据类型设置默认主题
        theme_mapping = {
            WritingGenre.Novel: "专注阅读",
            WritingGenre.ShortStory: "精简创作",
            WritingGenre.Script: "剧本写作",
            WritingGenre.Poetry: "诗意创作",
        }
        
        return {
            "font": "等线",
            "font_size": 14,
            "line_height": 1.8,
            "theme": "dark" if tone == EmotionalTone.Dark else "light",
            "show_word_count": True,
            "auto_save": True,
            "focus_mode": True,
        }
    
    # ==================== 风格模仿 ====================
    
    def analyze_style(self, text: str) -> dict:
        """
        分析文本风格
        
        Returns:
            风格分析结果
        """
        # 简单的风格分析
        sentences = re.split(r"[。！？]", text)
        avg_sentence_len = sum(len(s) for s in sentences) / max(len(sentences), 1)
        
        # 词汇多样性
        words = re.findall(r"[\w]+", text)
        unique_words = len(set(words))
        vocabulary_richness = unique_words / max(len(words), 1)
        
        # 情感词汇检测
        positive_words = ["美", "好", "快乐", "幸福", "爱", "希望"]
        negative_words = ["痛苦", "悲伤", "黑暗", "恐惧", "绝望"]
        
        positive_count = sum(1 for w in words if any(p in w for p in positive_words))
        negative_count = sum(1 for w in words if any(n in w for n in negative_words))
        
        return {
            "avg_sentence_length": round(avg_sentence_len, 1),
            "vocabulary_richness": round(vocabulary_richness, 2),
            "emotional_tone": "positive" if positive_count > negative_count else "negative",
            "suggestions": self._get_style_suggestions(avg_sentence_len, vocabulary_richness),
        }
    
    def _get_style_suggestions(
        self,
        avg_sentence_len: float,
        vocabulary_richness: float,
    ) -> list[str]:
        """获取风格建议"""
        suggestions = []
        
        if avg_sentence_len > 50:
            suggestions.append("句子较长，可适当断句增加节奏感")
        elif avg_sentence_len < 10:
            suggestions.append("句子较短，可适当合并增加流畅度")
        
        if vocabulary_richness < 0.3:
            suggestions.append("词汇重复较多，可适当使用同义词替换")
        elif vocabulary_richness > 0.6:
            suggestions.append("词汇丰富，注意保持整体协调")
        
        return suggestions
    
    def adapt_style(
        self,
        source_text: str,
        target_style: str,
    ) -> str:
        """
        风格适配（使用AI）
        
        Args:
            source_text: 源文本
            target_style: 目标风格描述
            
        Returns:
            适配后的文本
        """
        # 这里应该调用AI进行风格转换
        prompt = f"""请将以下文本改写成"{target_style}"风格：

原文：
{source_text}

要求：
1. 保持原文的核心内容和情节
2. 调整语言风格以匹配目标风格
3. 保持段落结构

改写后的文本："""
        
        return f"[风格转换提示]\n{prompt}"
    
    # ==================== 导出 ====================
    
    def assemble_manuscript(self) -> str:
        """组装手稿"""
        if not self.current_project:
            return ""
        
        sections = []
        
        # 标题
        sections.append(f"# {self.current_project.title}\n")
        
        # 元信息
        sections.append(f"类型: {self.current_project.genre.value}\n")
        sections.append(f"视角: {self.current_project.narrative_voice.value}\n")
        sections.append("---\n")
        
        # 大纲/Synopsis
        if self.current_project.synopsis:
            sections.append(f"## 故事梗概\n\n{self.current_project.synopsis}\n\n")
        
        # 正文碎片（按顺序）
        for fragment in self.current_project.fragments:
            sections.append(fragment.content)
            sections.append("\n\n---\n\n")
        
        return "".join(sections)
    
    def export_to_format(
        self,
        format_type: str = "markdown",
    ) -> str:
        """导出为指定格式"""
        manuscript = self.assemble_manuscript()
        
        if format_type == "markdown":
            return manuscript
        elif format_type == "plain":
            # 移除markdown格式
            return re.sub(r"#+ ", "", manuscript)
        else:
            return manuscript
