"""
意图识别与动作映射器

将自然语言查询转换为具体的应用操作：
1. 双层意图识别
2. 上下文管理
3. 行动规划
4. 响应生成
"""

import re
import time
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from .models import (
    IntentType, SecondaryIntent, IntentResult,
    UserContext, ConversationContext, NavigationResult,
    UIPage, Guide, OperationPath
)
from .knowledge_graph import get_knowledge_graph


class IntentRecognizer:
    """
    AI意图识别器
    
    识别用户查询的意图，映射到具体的操作和页面
    """
    
    def __init__(self):
        self.kg = get_knowledge_graph()
        
        # 意图模式库
        self._load_intent_patterns()
    
    def _load_intent_patterns(self):
        """加载意图识别模式"""
        # 一级意图模式
        self.primary_patterns = {
            IntentType.FEATURE_QUERY: [
                r"什么是|是.*吗|介绍一下|解释.*|说明.*",
                r"怎么用|如何使用|干嘛用的|有什么用",
                r"功能|特性|特点|能力",
                r"\?$"  # 以问号结尾
            ],
            IntentType.OPERATION_GUIDE: [
                r"如何|怎么|怎样|怎么办",
                r"步骤|流程|过程",
                r"一步一步|分步",
                r"先.*再|然后|接着"
            ],
            IntentType.CONFIG_HELP: [
                r"配置|设置|调整|修改.*设置",
                r"选项|参数|偏好",
                r"怎么改|如何修改"
            ],
            IntentType.TROUBLESHOOT: [
                r"错误|问题|故障|报错",
                r"不工作|不能用|失败",
                r"修复|解决|排查",
                r"为什么.*不"
            ],
            IntentType.NAVIGATION: [
                r"打开|进入|跳转到|去.*页面",
                r"在哪|哪里|找不到",
                r"导航.*|前往"
            ],
            IntentType.SETTINGS: [
                r"开启|关闭|启用|禁用",
                r"重置|恢复默认",
                r"保存.*设置"
            ]
        }
        
        # 二级意图模式
        self.secondary_patterns = {
            SecondaryIntent.WHAT_IS: [
                r"什么是|是.*吗|介绍一下|解释.*|定义",
                r"是.*东西|是什么|叫.*"
            ],
            SecondaryIntent.HOW_WORKS: [
                r"怎么工作|如何工作|原理|工作机制",
                r".*原理|工作方式"
            ],
            SecondaryIntent.HOW_TO_DO: [
                r"如何|怎么|怎样.*做",
                r".*步骤|.*流程",
                r"请.*帮我.*"
            ],
            SecondaryIntent.HOW_TO_CONFIG: [
                r"怎么配置|如何设置|配置.*方法",
                r"设置.*选项|调整.*参数"
            ],
            SecondaryIntent.ERROR_FIX: [
                r".*错误|.*报错|.*失败",
                r"解决.*问题|修复.*",
                r".*不行|.*不能用"
            ],
            SecondaryIntent.WHERE_IS: [
                r"在哪|哪里|找不到",
                r"怎么.*找|如何.*打开"
            ],
            SecondaryIntent.OPEN_SETTINGS: [
                r"打开.*设置|进入.*设置",
                r"去.*设置|转到.*设置"
            ],
            SecondaryIntent.QUICK_ACTION: [
                r"直接|快捷|一键",
                r"帮我.*一下"
            ]
        }
        
        # 动作关键词映射
        self.action_keywords = {
            "click": ["点击", "单击", "按下", "选择"],
            "input": ["输入", "填写", "键入", "输入"],
            "select": ["选择", "选中", "下拉", "切换到"],
            "toggle": ["开启", "关闭", "启用", "禁用", "开关"],
            "navigate": ["打开", "进入", "前往", "跳转到", "去"]
        }
        
        # 页面/功能关键词
        self.feature_keywords = {
            "settings": ["设置", "配置", "偏好", "选项"],
            "model": ["模型", "AI", "语言模型", "LLM"],
            "api": ["API", "密钥", "接口", "endpoint"],
            "mcp": ["MCP", "服务器", "插件", "扩展"],
            "skill": ["Skill", "技能", "插件"],
            "chat": ["对话", "聊天", "会话"],
            "knowledge": ["知识", "知识库", "文档"]
        }
    
    def recognize(self, query: str, user_ctx: UserContext = None,
                  conv_ctx: ConversationContext = None) -> IntentResult:
        """
        识别用户意图
        
        Args:
            query: 用户查询
            user_ctx: 用户上下文
            conv_ctx: 会话上下文
            
        Returns:
            IntentResult意图识别结果
        """
        query = query.strip()
        query_lower = query.lower()
        
        # 1. 一级意图识别
        primary_intent = self._recognize_primary_intent(query, query_lower)
        
        # 2. 二级意图识别
        secondary_intent = self._recognize_secondary_intent(query, query_lower)
        
        # 3. 实体提取
        entities = self._extract_entities(query, query_lower)
        
        # 4. 查找相关页面和指引
        related_pages = self._find_related_pages(query, entities)
        related_guides = self._find_related_guides(query, entities, primary_intent)
        
        # 5. 生成建议动作
        suggested_actions = self._generate_suggested_actions(
            primary_intent, secondary_intent, entities, related_pages
        )
        
        # 6. 置信度计算
        confidence = self._calculate_confidence(
            primary_intent, secondary_intent, entities, related_pages
        )
        
        # 7. 生成响应模板
        response_template = self._generate_response_template(
            primary_intent, secondary_intent, entities
        )
        
        return IntentResult(
            primary_intent=primary_intent,
            secondary_intent=secondary_intent,
            confidence=confidence,
            entities=entities,
            related_pages=related_pages,
            related_guides=related_guides,
            suggested_actions=suggested_actions,
            response_template=response_template,
            raw_query=query
        )
    
    def _recognize_primary_intent(self, query: str, query_lower: str) -> IntentType:
        """识别一级意图"""
        scores = defaultdict(float)
        
        for intent_type, patterns in self.primary_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    scores[intent_type] += 1.0
        
        if not scores:
            return IntentType.GENERAL_HELP
        
        return max(scores.items(), key=lambda x: x[1])[0]
    
    def _recognize_secondary_intent(self, query: str, query_lower: str) -> SecondaryIntent:
        """识别二级意图"""
        scores = defaultdict(float)
        
        for intent_type, patterns in self.secondary_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    scores[intent_type] += 1.0
        
        if not scores:
            return SecondaryIntent.HOW_TO_DO
        
        return max(scores.items(), key=lambda x: x[1])[0]
    
    def _extract_entities(self, query: str, query_lower: str) -> Dict[str, Any]:
        """提取实体"""
        entities = {
            "features": [],      # 功能关键词
            "actions": [],       # 动作关键词
            "components": [],    # 组件关键词
            "settings": [],      # 设置项关键词
            "comparisons": []    # 比较对象
        }
        
        # 提取功能关键词
        for feature, keywords in self.feature_keywords.items():
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    entities["features"].append(feature)
                    break
        
        # 提取动作关键词
        for action, keywords in self.action_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    entities["actions"].append(action)
                    break
        
        # 提取"和"、"与"连接的比较对象
        if "和" in query or "与" in query or "vs" in query_lower:
            parts = re.split(r'[和与vs]', query)
            if len(parts) >= 2:
                entities["comparisons"] = [p.strip() for p in parts if p.strip()]
        
        return entities
    
    def _find_related_pages(self, query: str, entities: Dict) -> List[str]:
        """查找相关页面"""
        related = []
        
        # 基于功能关键词
        for feature in entities.get("features", []):
            if feature == "settings":
                related.append("settings")
            elif feature == "model":
                related.append("settings_model")
            elif feature == "api":
                related.append("settings_api")
            elif feature == "mcp":
                related.append("mcp_market")
            elif feature == "skill":
                related.append("skill_market")
            elif feature == "chat":
                related.append("chat")
            elif feature == "knowledge":
                related.append("knowledge_base")
        
        # 基于查询搜索
        if not related:
            pages = self.kg.find_pages(query, limit=3)
            related = [p.id for p in pages]
        
        return list(set(related))[:3]
    
    def _find_related_guides(self, query: str, entities: Dict,
                             primary_intent: IntentType) -> List[str]:
        """查找相关指引"""
        related = []
        
        # 查找指引
        tags = entities.get("features", [])
        guides = self.kg.find_guide(tags=tags if tags else None)
        
        related = [g.guide_id for g in guides[:3]]
        
        return related
    
    def _generate_suggested_actions(self, primary: IntentType,
                                     secondary: SecondaryIntent,
                                     entities: Dict,
                                     related_pages: List[str]) -> List[str]:
        """生成建议动作"""
        actions = []
        
        # 基于意图生成动作
        if primary == IntentType.NAVIGATION:
            for page_id in related_pages:
                actions.append(f"navigate:{page_id}")
        
        elif primary == IntentType.OPERATION_GUIDE:
            actions.append("show_guide")
            for page_id in related_pages:
                actions.append(f"start_tutorial:{page_id}")
        
        elif primary == IntentType.CONFIG_HELP:
            actions.append("show_config_guide")
            for page_id in related_pages:
                actions.append(f"highlight_config:{page_id}")
        
        elif primary == IntentType.TROUBLESHOOT:
            actions.append("diagnose_issue")
            actions.append("show_faq")
        
        else:
            actions.append("show_help")
        
        return actions
    
    def _calculate_confidence(self, primary: IntentType, secondary: SecondaryIntent,
                              entities: Dict, related_pages: List[str]) -> float:
        """计算置信度"""
        confidence = 0.5
        
        # 实体越多，置信度越高
        total_entities = sum(len(v) for v in entities.values())
        confidence += min(total_entities * 0.1, 0.2)
        
        # 相关页面越多，置信度越高
        confidence += min(len(related_pages) * 0.05, 0.15)
        
        # 明确的模式匹配增加置信度
        if primary != IntentType.UNKNOWN:
            confidence += 0.1
        
        if secondary != SecondaryIntent.HOW_TO_DO:
            confidence += 0.05
        
        return min(confidence, 0.95)
    
    def _generate_response_template(self, primary: IntentType,
                                     secondary: SecondaryIntent,
                                     entities: Dict) -> str:
        """生成响应模板"""
        templates = {
            (IntentType.FEATURE_QUERY, SecondaryIntent.WHAT_IS): "explain_feature",
            (IntentType.FEATURE_QUERY, SecondaryIntent.HOW_WORKS): "explain_working",
            (IntentType.OPERATION_GUIDE, SecondaryIntent.HOW_TO_DO): "guide_operation",
            (IntentType.CONFIG_HELP, SecondaryIntent.HOW_TO_CONFIG): "guide_config",
            (IntentType.TROUBLESHOOT, SecondaryIntent.ERROR_FIX): "fix_error",
            (IntentType.NAVIGATION, SecondaryIntent.WHERE_IS): "navigate_to",
            (IntentType.NAVIGATION, SecondaryIntent.OPEN_SETTINGS): "open_settings"
        }
        
        return templates.get((primary, secondary), "general_response")
    
    def generate_response(self, intent_result: IntentResult,
                          user_ctx: UserContext = None) -> Tuple[str, NavigationResult]:
        """
        基于意图结果生成响应
        
        Returns:
            (文本响应, 导航结果)
        """
        primary = intent_result.primary_intent
        secondary = intent_result.secondary_intent
        entities = intent_result.entities
        
        # 构建响应文本
        response_parts = []
        navigation = NavigationResult(success=False)
        
        # 意图识别结果说明
        intent_descriptions = {
            IntentType.FEATURE_QUERY: "功能查询",
            IntentType.OPERATION_GUIDE: "操作指导",
            IntentType.CONFIG_HELP: "配置帮助",
            IntentType.TROUBLESHOOT: "故障排查",
            IntentType.NAVIGATION: "导航跳转",
            IntentType.SETTINGS: "设置操作",
            IntentType.GENERAL_HELP: "一般帮助"
        }
        
        response_parts.append(f"📋 我理解您的问题是：**{intent_descriptions.get(primary, '一般')}**\n")
        
        # 根据意图类型生成具体响应
        if primary == IntentType.FEATURE_QUERY:
            text, nav = self._handle_feature_query(intent_result)
            response_parts.append(text)
            navigation = nav
        
        elif primary == IntentType.OPERATION_GUIDE:
            text, nav = self._handle_operation_guide(intent_result)
            response_parts.append(text)
            navigation = nav
        
        elif primary == IntentType.CONFIG_HELP:
            text, nav = self._handle_config_help(intent_result)
            response_parts.append(text)
            navigation = nav
        
        elif primary == IntentType.NAVIGATION:
            text, nav = self._handle_navigation(intent_result)
            response_parts.append(text)
            navigation = nav
        
        elif primary == IntentType.TROUBLESHOOT:
            text, nav = self._handle_troubleshoot(intent_result)
            response_parts.append(text)
            navigation = nav
        
        else:
            response_parts.append(self._handle_general_help(intent_result))
        
        # 添加建议动作
        if intent_result.suggested_actions:
            response_parts.append("\n💡 **您可以**：")
            for action in intent_result.suggested_actions[:3]:
                if action.startswith("navigate:"):
                    page_id = action.split(":")[1]
                    response_parts.append(f"- 前往「{page_id}」页面")
                elif action == "show_guide":
                    response_parts.append("- 查看操作指引")
                elif action == "show_config_guide":
                    response_parts.append("- 查看配置指南")
        
        return "".join(response_parts), navigation
    
    def _handle_feature_query(self, result: IntentResult) -> Tuple[str, NavigationResult]:
        """处理功能查询"""
        features = result.entities.get("features", [])
        
        if features:
            feature = features[0]
            pages = self.kg.find_pages(feature, limit=1)
            
            if pages:
                page = pages[0]
                text = f"\n🔍 **{page.title}**\n\n"
                text += f"{page.description}\n\n"
                text += f"📌 相关标签：{', '.join(page.tags)}\n"
                
                # 获取组件信息
                components = self.kg.components.get(page.id, {})
                if components:
                    text += f"\n⚙️ **包含 {len(components)} 个可配置项**\n"
                
                return text, NavigationResult(
                    success=True,
                    target_page=page.id,
                    message=f"已找到「{page.title}」相关信息"
                )
        
        return "\n📚 这个功能可以帮助您...\n", NavigationResult(
            success=False,
            message="未能识别具体功能"
        )
    
    def _handle_operation_guide(self, result: IntentResult) -> Tuple[str, NavigationResult]:
        """处理操作指导"""
        query = result.raw_query
        paths = self.kg.find_operation_paths(query)
        
        if paths:
            path = paths[0]
            text = f"\n📝 **「{path.name}」操作指南**\n\n"
            text += f"📖 {path.description}\n\n"
            text += f"⏱️ 预计耗时：约 {path.estimated_time} 秒\n"
            text += f"📊 难度：{'🟢 简单' if path.difficulty == 'easy' else '🟡 中等' if path.difficulty == 'medium' else '🔴 复杂'}\n\n"
            text += "**操作步骤：**\n"
            
            for i, step in enumerate(path.steps, 1):
                text += f"{i}. {step.description}\n"
            
            # 查找相关指引
            guides = self.kg.find_guide(target_page=path.to_page)
            if guides:
                text += f"\n🎯 **建议**：我为您找到了一个交互式指引，可以一步步引导您完成操作\n"
            
            return text, NavigationResult(
                success=True,
                target_page=path.to_page,
                guide_id=guides[0].guide_id if guides else "",
                message=f"已找到「{path.name}」操作指南"
            )
        
        return "\n🔧 我正在分析您的操作需求...\n", NavigationResult(
            success=False,
            message="未找到相关操作指南"
        )
    
    def _handle_config_help(self, result: IntentResult) -> Tuple[str, NavigationResult]:
        """处理配置帮助"""
        features = result.entities.get("features", [])
        
        target_page = result.related_pages[0] if result.related_pages else "settings"
        page = self.kg.get_page_by_id(target_page)
        
        text = f"\n⚙️ **配置帮助**\n\n"
        
        if page:
            text += f"当前配置页面：**{page.title}**\n\n"
            text += f"{page.description}\n\n"
        
        # 查找相关指引
        guides = self.kg.find_guide(target_page=target_page)
        if guides:
            guide = guides[0]
            text += f"🎯 **推荐**：使用「{guide.name}」指引可以更简单地完成配置\n"
        
        return text, NavigationResult(
            success=True,
            target_page=target_page,
            message="已定位到配置页面"
        )
    
    def _handle_navigation(self, result: IntentResult) -> Tuple[str, NavigationResult]:
        """处理导航请求"""
        pages = result.related_pages
        
        if pages:
            page_id = pages[0]
            page = self.kg.get_page_by_id(page_id)
            
            if page:
                route_url = self.kg.generate_route_url(page_id)
                
                text = f"\n🧭 **导航到「{page.title}」**\n\n"
                text += f"📍 路径：{page.path}\n"
                text += f"📝 {page.description}\n"
                text += f"\n🔗 路由链接：`{route_url}`\n"
                
                return text, NavigationResult(
                    success=True,
                    target_page=page_id,
                    route_url=route_url,
                    message=f"已准备好导航到「{page.title}」"
                )
        
        return "\n🔍 我正在查找您要访问的页面...\n", NavigationResult(
            success=False,
            message="未找到目标页面"
        )
    
    def _handle_troubleshoot(self, result: IntentResult) -> Tuple[str, NavigationResult]:
        """处理故障排查"""
        text = "\n🔧 **故障排查**\n\n"
        text += "让我帮您分析一下可能的问题原因：\n\n"
        text += "1. **检查网络连接** - 确保您的网络正常\n"
        text += "2. **验证配置** - 检查API密钥和端点是否正确\n"
        text += "3. **查看日志** - 查看详细错误信息\n"
        text += "4. **重启应用** - 有时重启可以解决临时问题\n\n"
        text += "💡 **建议**：您可以告诉我具体的错误信息，我可以提供更精准的帮助\n"
        
        return text, NavigationResult(
            success=True,
            message="故障排查建议已生成"
        )
    
    def _handle_general_help(self, result: IntentResult) -> str:
        """处理一般帮助"""
        text = "\n🤖 **通用帮助**\n\n"
        text += "我可以帮助您：\n\n"
        text += "- 📖 了解各个功能模块\n"
        text += "- 🔧 指导您完成操作步骤\n"
        text += "- ⚙️ 帮助您配置系统选项\n"
        text += "- 🔍 导航到指定页面\n"
        text += "- 🩺 排查和解决问题\n\n"
        text += "请告诉我您想做什么？\n"
        
        return text


# 单例
_intent_recognizer_instance = None

def get_intent_recognizer() -> IntentRecognizer:
    """获取意图识别器单例"""
    global _intent_recognizer_instance
    if _intent_recognizer_instance is None:
        _intent_recognizer_instance = IntentRecognizer()
    return _intent_recognizer_instance
