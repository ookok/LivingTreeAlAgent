"""
LLM 增强追问模块 (Phase 4)
===========================

使用 LLM 生成更智能、更个性化的追问

功能：
1. LLMGuidanceGenerator - LLM 追问生成器
2. OllamaClient - Ollama 模型调用封装
3. HybridGuidanceGenerator - 混合追问策略（规则+LLM）
4. GuidanceTrigger - 智能触发条件判断

设计原则：
- 规则优先，LLM 补充：规则能处理的用规则，复杂情况才调用 LLM
- 缓存复用：避免重复调用 LLM
- 异步执行：不阻塞主流程
- 可配置：支持多种 LLM 提供者
"""

from typing import Optional, Callable, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time
import hashlib
import json
import re

# 尝试导入 PyQt6 组件（可选）
try:
    from PyQt6.QtCore import QObject, pyqtSignal, QThread
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    QObject = object

# 导入统一配置
try:
    from core.config.unified_config import get_ollama_url, get
except ImportError:
    # 兼容旧环境
    def get_ollama_url():
        return "http://localhost:11434"
    def get(key, default=None):
        return default


# ============== 配置枚举 ==============

class LLMSource(Enum):
    """LLM 来源"""
    OLLAMA_LOCAL = "ollama_local"      # 本地 Ollama
    OLLAMA_REMOTE = "ollama_remote"    # 远程 Ollama
    OPENAI = "openai"                  # OpenAI API
    ANTHROPIC = "anthropic"            # Anthropic API
    CUSTOM = "custom"                  # 自定义 API


class GuidanceStrategy(Enum):
    """追问策略"""
    RULE_ONLY = "rule_only"           # 仅规则
    LLM_FALLBACK = "llm_fallback"      # 规则优先，LLM 补充
    LLM_FIRST = "llm_first"           # LLM 优先
    HYBRID = "hybrid"                 # 混合策略


class TriggerCondition(Enum):
    """触发条件"""
    ALWAYS = "always"                 # 始终触发
    LOW_CONFIDENCE = "low_confidence" # 低置信度时触发
    NO_RULE_RESULT = "no_rule_result" # 规则无结果时触发
    SPECIFIC_TYPES = "specific_types"   # 特定类型触发


# ============== 数据结构 ==============

@dataclass
class LLMGuidanceConfig:
    """LLM 追问配置"""
    # 模型配置
    source: LLMSource = LLMSource.OLLAMA_LOCAL
    model: str = "qwen2.5:1.5b"       # 默认模型
    api_base: str = ""                # 默认从统一配置获取
    api_key: str = ""                 # 可选
    timeout: float = 30.0             # 超时时间
    
    def __post_init__(self):
        # 默认值从统一配置获取
        if not self.api_base:
            self.api_base = get_ollama_url()
    
    # 生成配置
    max_questions: int = 3            # 最大追问数
    temperature: float = 0.7          # 温度参数
    max_tokens: int = 500             # 最大 token 数
    
    # 缓存配置
    enable_cache: bool = True         # 启用缓存
    cache_ttl: float = 3600.0         # 缓存 TTL（秒）
    
    # 策略配置
    strategy: GuidanceStrategy = GuidanceStrategy.HYBRID
    trigger_condition: TriggerCondition = TriggerCondition.LOW_CONFIDENCE
    
    # 触发阈值
    confidence_threshold: float = 0.5  # 置信度阈值


@dataclass
class LLMGuidanceResult:
    """LLM 追问结果"""
    questions: List[str]              # 生成的追问列表
    reasoning: str = ""              # 生成推理过程
    model_used: str = ""              # 使用的模型
    latency: float = 0.0             # 延迟（秒）
    cached: bool = False             # 是否来自缓存
    confidence: float = 0.0          # 置信度


@dataclass
class HybridGuidanceResult:
    """混合追问结果"""
    # 来源
    rule_questions: List[str] = field(default_factory=list)   # 规则生成
    llm_questions: List[str] = field(default_factory=list)    # LLM 生成
    
    # 合并结果
    all_questions: List[str] = field(default_factory=list)
    
    # 元数据
    strategy_used: GuidanceStrategy = GuidanceStrategy.HYBRID
    rule_confidence: float = 0.0
    llm_confidence: float = 0.0
    final_confidence: float = 0.0
    
    # 来源追踪
    question_sources: Dict[str, str] = field(default_factory=dict)  # 问题 -> 来源


# ============== Ollama 客户端 ==============

class OllamaClient:
    """
    Ollama API 客户端
    
    支持本地和远程 Ollama 服务
    """
    
    def __init__(
        self,
        base_url: str = None,
        timeout: float = 30.0,
    ):
        """
        Args:
            base_url: Ollama API 地址，默认从统一配置获取
            timeout: 超时时间（秒）
        """
        self.base_url = (base_url or get_ollama_url()).rstrip('/')
        self.timeout = timeout
        self._session = None
    
    def _get_session(self):
        """获取 requests session"""
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.timeout = self.timeout
        return self._session
    
    def list_models(self) -> List[str]:
        """列出可用模型"""
        try:
            import requests
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [m['name'] for m in data.get('models', [])]
        except Exception:
            pass
        return []
    
    def generate(
        self,
        model: str,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 500,
        stream: bool = False,
    ) -> str:
        """
        生成文本
        
        Args:
            model: 模型名称
            prompt: 提示词
            system: 系统提示
            temperature: 温度
            max_tokens: 最大 token 数
            stream: 是否流式输出
            
        Returns:
            str: 生成的文本
        """
        import requests
        
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        
        if system:
            payload["system"] = system
        
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('response', '')
            else:
                raise Exception(f"API error: {resp.status_code}")
        except Exception as e:
            raise Exception(f"Ollama generate failed: {e}")
    
    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        """
        对话生成（新版 API）
        
        Args:
            model: 模型名称
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度
            max_tokens: 最大 token 数
            
        Returns:
            str: 生成的文本
        """
        import requests
        
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('message', {}).get('content', '')
            else:
                raise Exception(f"API error: {resp.status_code}")
        except Exception as e:
            raise Exception(f"Ollama chat failed: {e}")
    
    def is_available(self) -> bool:
        """检查服务是否可用"""
        try:
            import requests
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False


# ============== LLM 追问生成器 ==============

class LLMGuidanceGenerator:
    """
    LLM 追问生成器
    
    使用 LLM 生成智能追问
    """
    
    # 默认系统提示
    DEFAULT_SYSTEM_PROMPT = """你是一个智能追问生成专家。

根据用户的问题和AI的回答，生成3个高质量的追问，帮助用户更深入地理解问题。

要求：
1. 追问应该自然、流畅，符合中文表达习惯
2. 不要简单重复已经回答过的内容
3. 追问应该引导用户深入思考或拓展相关领域
4. 避免生成过于宽泛或无意义的问题
5. 每个追问不超过25个字

直接输出追问列表，用换行分隔，不要编号，不要其他解释。
例如：
需要我详细解释一下实现原理吗？
还有其他应用场景想了解吗？
这个方案有什么优缺点？
"""
    
    # 领域特定提示
    DOMAIN_PROMPTS = {
        "code": """你是一个编程专家。根据代码回答，生成3个编程相关的追问。

关注点：
- 代码原理和实现细节
- 性能优化建议
- 最佳实践和设计模式
- 错误处理和边界情况
- 代码测试方法

生成追问时，用程序员的口吻，自然、专业。""",
        
        "data": """你是一个数据分析专家。根据数据分析回答，生成3个数据相关的追问。

关注点：
- 数据可视化和图表建议
- 进一步的数据挖掘方向
- 数据的实际应用场景
- 数据的局限性和注意事项
- 相关的其他指标

生成追问时，用数据分析师的口吻，简洁、精准。""",
        
        "tutorial": """你是一个教育专家。根据教程内容，生成3个学习相关的追问。

关注点：
- 前置知识和背景
- 实践操作细节
- 常见问题和解决方案
- 进阶学习路径
- 相关的扩展话题

生成追问时，用老师的口吻，耐心、鼓励。""",
        
        "explanation": """你是一个知识讲解专家。根据概念解释，生成3个理解相关的追问。

关注点：
- 概念的深层含义
- 与其他概念的联系
- 实际应用例子
- 理解误区和注意点
- 相关的延伸知识

生成追问时，用博学的学者口吻，深入浅出。""",
        
        "comparison": """你是一个对比分析专家。根据对比内容，生成3个分析相关的追问。

关注点：
- 对比维度的深入分析
- 选择建议和使用场景
- 各自的适用条件
- 发展趋势和未来展望
- 相关的其他选项

生成追问时，用专业的分析师口吻，客观、理性。""",
    }
    
    def __init__(self, config: Optional[LLMGuidanceConfig] = None):
        """
        Args:
            config: LLM 配置
        """
        self.config = config or LLMGuidanceConfig()
        self._client = None
        self._cache: Dict[str, Tuple[str, float]] = {}  # key -> (questions, timestamp)
    
    @property
    def client(self) -> OllamaClient:
        """获取客户端"""
        if self._client is None:
            self._client = OllamaClient(
                base_url=self.config.api_base,
                timeout=self.config.timeout,
            )
        return self._client
    
    def _get_cache_key(
        self,
        user_message: str,
        response: str,
        intent: str,
        content_type: str,
    ) -> str:
        """生成缓存 key"""
        data = f"{user_message}|{response}|{intent}|{content_type}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def _get_cached(self, cache_key: str) -> Optional[List[str]]:
        """获取缓存"""
        if not self.config.enable_cache:
            return None
        
        if cache_key in self._cache:
            questions, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self.config.cache_ttl:
                return questions
            else:
                del self._cache[cache_key]
        return None
    
    def _set_cache(self, cache_key: str, questions: List[str]):
        """设置缓存"""
        if self.config.enable_cache:
            self._cache[cache_key] = (questions, time.time())
            
            # 限制缓存大小
            if len(self._cache) > 100:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
    
    def generate(
        self,
        user_message: str,
        response: str,
        intent: str = "",
        content_type: str = "general",
        context: Dict[str, Any] = None,
    ) -> LLMGuidanceResult:
        """
        生成 LLM 追问
        
        Args:
            user_message: 用户原始消息
            response: AI 回答
            intent: 意图类型
            content_type: 内容类型
            context: 上下文信息
            
        Returns:
            LLMGuidanceResult: 追问结果
        """
        start_time = time.time()
        
        # 检查缓存
        cache_key = self._get_cache_key(user_message, response, intent, content_type)
        cached = self._get_cached(cache_key)
        if cached:
            return LLMGuidanceResult(
                questions=cached,
                reasoning="来自缓存",
                model_used=self.config.model,
                latency=0.0,
                cached=True,
                confidence=0.8,
            )
        
        # 构建提示词
        system_prompt = self.DOMAIN_PROMPTS.get(
            content_type, 
            self.DEFAULT_SYSTEM_PROMPT
        )
        
        user_prompt = self._build_prompt(user_message, response, intent, context)
        
        # 调用 LLM
        try:
            if self.config.source in [LLMSource.OLLAMA_LOCAL, LLMSource.OLLAMA_REMOTE]:
                result = self.client.generate(
                    model=self.config.model,
                    prompt=user_prompt,
                    system=system_prompt,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
            else:
                raise Exception(f"Unsupported source: {self.config.source}")
            
            # 解析结果
            questions = self._parse_questions(result)
            
            # 缓存
            self._set_cache(cache_key, questions)
            
            latency = time.time() - start_time
            
            return LLMGuidanceResult(
                questions=questions,
                reasoning="LLM 生成",
                model_used=self.config.model,
                latency=latency,
                cached=False,
                confidence=0.7,
            )
            
        except Exception as e:
            # LLM 调用失败，返回空
            return LLMGuidanceResult(
                questions=[],
                reasoning=f"LLM 调用失败: {e}",
                model_used=self.config.model,
                latency=time.time() - start_time,
                cached=False,
                confidence=0.0,
            )
    
    def _build_prompt(
        self,
        user_message: str,
        response: str,
        intent: str,
        context: Dict[str, Any],
    ) -> str:
        """构建提示词"""
        prompt_parts = [
            f"用户问题：{user_message}",
            "",
            f"AI回答：{response}",
            "",
            "请根据以上内容，生成3个追问。",
        ]
        
        if intent:
            prompt_parts.insert(0, f"意图类型：{intent}")
        
        if context:
            if 'topic' in context:
                prompt_parts.insert(1, f"当前话题：{context['topic']}")
            if 'message_count' in context:
                prompt_parts.insert(2, f"对话轮次：{context['message_count']}")
        
        return "\n".join(prompt_parts)
    
    def _parse_questions(self, result: str) -> List[str]:
        """解析追问结果"""
        questions = []
        
        for line in result.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # 去除编号（如 "1." 或 "1、"）
            line = re.sub(r'^[\d一二三四五六七八九十]+[.、)）]\s*', '', line)
            
            # 去除特殊符号开头
            line = re.sub(r'^[-*•]\s*', '', line)
            
            # 去除引号
            line = line.strip('"\'「」『』')
            
            # 验证长度
            if 5 <= len(line) <= 50:
                questions.append(line)
        
        return questions[:self.config.max_questions]
    
    def is_available(self) -> bool:
        """检查 LLM 是否可用"""
        return self.client.is_available()
    
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()


# ============== 智能触发器 ==============

class GuidanceTrigger:
    """
    追问触发器
    
    判断何时使用 LLM 生成追问
    """
    
    def __init__(
        self,
        condition: TriggerCondition = TriggerCondition.LOW_CONFIDENCE,
        confidence_threshold: float = 0.5,
        specific_types: List[str] = None,
    ):
        """
        Args:
            condition: 触发条件
            confidence_threshold: 置信度阈值
            specific_types: 特定内容类型列表
        """
        self.condition = condition
        self.confidence_threshold = confidence_threshold
        self.specific_types = specific_types or []
    
    def should_trigger_llm(
        self,
        rule_confidence: float,
        rule_questions: List[str],
        content_type: str,
        intent: str,
    ) -> Tuple[bool, str]:
        """
        判断是否应该触发 LLM
        
        Args:
            rule_confidence: 规则置信度
            rule_questions: 规则生成的追问
            content_type: 内容类型
            intent: 意图类型
            
        Returns:
            Tuple[bool, str]: (是否触发, 原因)
        """
        if self.condition == TriggerCondition.ALWAYS:
            return True, "始终触发"
        
        if self.condition == TriggerCondition.LOW_CONFIDENCE:
            if rule_confidence < self.confidence_threshold:
                return True, f"规则置信度低 ({rule_confidence:.2f} < {self.confidence_threshold})"
            if len(rule_questions) == 0:
                return True, "规则无追问生成"
        
        if self.condition == TriggerCondition.NO_RULE_RESULT:
            if len(rule_questions) == 0:
                return True, "规则无追问"
        
        if self.condition == TriggerCondition.SPECIFIC_TYPES:
            if content_type in self.specific_types:
                return True, f"内容类型 {content_type} 在特定列表中"
        
        return False, "规则足够，无需 LLM"
    
    @classmethod
    def create_adaptive_trigger(
        cls,
        message_count: int,
        followup_count: int,
        rule_confidence: float,
    ) -> 'GuidanceTrigger':
        """
        创建自适应触发器
        
        根据对话状态动态调整触发策略
        """
        # 对话初期更多使用 LLM
        if message_count <= 2:
            return cls(
                condition=TriggerCondition.ALWAYS,
                confidence_threshold=0.7,
            )
        
        # 连续追问时简化触发
        if followup_count >= 3:
            return cls(
                condition=TriggerCondition.NO_RULE_RESULT,
                confidence_threshold=0.3,
            )
        
        # 正常情况
        return cls(
            condition=TriggerCondition.LOW_CONFIDENCE,
            confidence_threshold=0.5,
        )


# ============== 混合追问生成器 ==============

class HybridGuidanceGenerator:
    """
    混合追问生成器
    
    结合规则（Phase 1-3）和 LLM（Phase 4）生成追问
    """
    
    def __init__(
        self,
        llm_config: Optional[LLMGuidanceConfig] = None,
        trigger: Optional[GuidanceTrigger] = None,
    ):
        """
        Args:
            llm_config: LLM 配置
            trigger: 触发器
        """
        self.llm_config = llm_config or LLMGuidanceConfig()
        self.llm_generator = LLMGuidanceGenerator(self.llm_config)
        self.trigger = trigger or GuidanceTrigger()
    
    def generate(
        self,
        rule_questions: List[str],
        rule_confidence: float,
        user_message: str,
        response: str,
        intent: str = "",
        content_type: str = "general",
        context: Dict[str, Any] = None,
    ) -> HybridGuidanceResult:
        """
        生成混合追问
        
        Args:
            rule_questions: 规则生成的追问
            rule_confidence: 规则置信度
            user_message: 用户消息
            response: AI 回答
            intent: 意图类型
            content_type: 内容类型
            context: 上下文
            
        Returns:
            HybridGuidanceResult: 混合结果
        """
        # 决定是否使用 LLM
        should_use_llm, reason = self.trigger.should_trigger_llm(
            rule_confidence=rule_confidence,
            rule_questions=rule_questions,
            content_type=content_type,
            intent=intent,
        )
        
        result = HybridGuidanceResult(
            rule_questions=rule_questions,
            rule_confidence=rule_confidence,
            strategy_used=self.llm_config.strategy,
            question_sources={q: "rule" for q in rule_questions},
        )
        
        if should_use_llm and self.llm_generator.is_available():
            # 调用 LLM
            llm_result = self.llm_generator.generate(
                user_message=user_message,
                response=response,
                intent=intent,
                content_type=content_type,
                context=context,
            )
            
            result.llm_questions = llm_result.questions
            result.llm_confidence = llm_result.confidence
            
            # 合并追问
            result.all_questions = self._merge_questions(
                rule_questions,
                llm_result.questions,
                result.question_sources,
            )
            
            result.final_confidence = (rule_confidence + llm_result.confidence) / 2
        else:
            # 仅使用规则
            result.all_questions = rule_questions
            result.final_confidence = rule_confidence
        
        return result
    
    def _merge_questions(
        self,
        rule_questions: List[str],
        llm_questions: List[str],
        sources: Dict[str, str],
    ) -> List[str]:
        """合并追问（去重+去冲突）"""
        all_questions = list(rule_questions)
        seen = set(q.lower().strip() for q in rule_questions)
        
        for q in llm_questions:
            normalized = q.lower().strip()
            
            # 检查是否完全相同
            if normalized not in seen:
                # 检查是否语义相似（简化版）
                is_similar = False
                for existing in seen:
                    if self._is_similar(normalized, existing):
                        is_similar = True
                        break
                
                if not is_similar:
                    all_questions.append(q)
                    sources[q] = "llm"
                    seen.add(normalized)
        
        return all_questions[:5]  # 最多5个
    
    def _is_similar(self, q1: str, q2: str) -> bool:
        """判断两个问题是否语义相似（简化版）"""
        # 关键词重叠
        words1 = set(q1.split())
        words2 = set(q2.split())
        
        if not words1 or not words2:
            return False
        
        overlap = len(words1 & words2)
        union = len(words1 | words2)
        
        # 超过 50% 重叠认为相似
        return overlap / union > 0.5


# ============== 便捷函数 ==============

def create_llm_generator(
    model: str = "qwen2.5:1.5b",
    api_base: str = None,
    strategy: GuidanceStrategy = GuidanceStrategy.HYBRID,
) -> LLMGuidanceGenerator:
    """
    创建 LLM 追问生成器
    
    Args:
        model: 模型名称
        api_base: API 地址，默认从统一配置获取
        strategy: 策略
        
    Returns:
        LLMGuidanceGenerator: 生成器实例
    """
    config = LLMGuidanceConfig(
        source=LLMSource.OLLAMA_LOCAL,
        model=model,
        api_base=api_base or get_ollama_url(),
        strategy=strategy,
    )
    return LLMGuidanceGenerator(config)


def create_hybrid_generator(
    model: str = "qwen2.5:1.5b",
    api_base: str = None,
    trigger_condition: TriggerCondition = TriggerCondition.LOW_CONFIDENCE,
) -> HybridGuidanceGenerator:
    """
    创建混合追问生成器
    
    Args:
        model: 模型名称
        api_base: API 地址，默认从统一配置获取
        trigger_condition: 触发条件
        
    Returns:
        HybridGuidanceGenerator: 生成器实例
    """
    llm_config = LLMGuidanceConfig(
        model=model,
        api_base=api_base or get_ollama_url(),
        strategy=GuidanceStrategy.HYBRID,
    )
    trigger = GuidanceTrigger(condition=trigger_condition)
    return HybridGuidanceGenerator(llm_config, trigger)


def quick_llm_guidance(
    user_message: str,
    response: str,
    intent: str = "",
    content_type: str = "general",
    model: str = "qwen2.5:1.5b",
    api_base: str = None,
) -> List[str]:
    """
    快速 LLM 追问生成
    
    Args:
        user_message: 用户消息
        response: AI 回答
        intent: 意图类型
        content_type: 内容类型
        model: 模型
        api_base: API 地址，默认从统一配置获取
        
    Returns:
        List[str]: 追问列表
    """
    generator = create_llm_generator(model=model, api_base=api_base)
    result = generator.generate(
        user_message=user_message,
        response=response,
        intent=intent,
        content_type=content_type,
    )
    return result.questions


# ============== 导出 ==============

__all__ = [
    # 配置枚举
    'LLMSource',
    'GuidanceStrategy',
    'TriggerCondition',
    # 数据结构
    'LLMGuidanceConfig',
    'LLMGuidanceResult',
    'HybridGuidanceResult',
    # 客户端
    'OllamaClient',
    # 生成器
    'LLMGuidanceGenerator',
    'GuidanceTrigger',
    'HybridGuidanceGenerator',
    # 便捷函数
    'create_llm_generator',
    'create_hybrid_generator',
    'quick_llm_guidance',
]
