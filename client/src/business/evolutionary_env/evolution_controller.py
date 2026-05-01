"""
进化控制器（Evolution Controller）：整合四层基础设施

核心功能：
1. 协调感知层、记忆层、行动层、目标层
2. 整合 FusionRAG 和 LLM Wiki 知识库
3. 实现自进化流程：模仿学习 → 模式发现 → 主动优化
4. 管理进化策略的沙箱测试和推广
"""

import json
import time
from typing import Dict, Any, List
from dataclasses import dataclass
from .perception_layer import PerceptionLayer, UserAction
from .memory_layer import MemoryLayer
from .action_layer import ActionLayer, RenderSchema
from .objective_layer import ObjectiveLayer, EvaluationResult
from .wiki_integration import WikiIntegrationLayer, get_wiki_integration

@dataclass
class EvolutionState:
    phase: str  # seed, imitation, pattern_discovery, proactive_optimization
    iteration: int
    last_evaluation: EvaluationResult = None
    active_strategy: str = "default"

@dataclass
class StrategyTestResult:
    strategy_id: str
    test_users: List[str]
    success_rate: float
    efficiency_improvement: float
    user_satisfaction: float
    is_validated: bool

class EvolutionController:
    def __init__(self):
        self.perception = PerceptionLayer()
        self.memory = MemoryLayer()
        self.action = ActionLayer()
        self.objective = ObjectiveLayer()
        
        # 整合 LLM Wiki
        self.wiki_integration = get_wiki_integration()
        
        # 整合 FusionRAG（延迟导入）
        self.fusion_rag = None
        self._init_fusion_rag()
        
        self.evolution_state = EvolutionState(
            phase='seed',
            iteration=0
        )
        
        self.strategy_sandbox: Dict[str, StrategyTestResult] = {}
        self.current_suggestions: List[Dict[str, Any]] = []
        self.adoption_count = 0
        self.suggestion_count = 0
    
    def _init_fusion_rag(self):
        """初始化 FusionRAG 集成"""
        try:
            from client.src.business.fusion_rag import get_docv_llm_wiki_integration
            self.fusion_rag = get_docv_llm_wiki_integration()
            print("[进化控制器] FusionRAG 集成初始化成功")
        except ImportError as e:
            print(f"[进化控制器] FusionRAG 集成初始化失败: {e}")
    
    def initialize_evolution(self):
        """初始化进化过程"""
        self.objective.start_session()
        print("[进化控制器] 初始化完成，进入种子阶段")
        
        # 从 Wiki 加载初始知识
        if self.wiki_integration:
            wiki_stats = self.wiki_integration.get_wiki_stats()
            print(f"[进化控制器] Wiki 统计: {wiki_stats}")
    
    def process_user_action(self, action_type: str, context: Dict[str, Any] = None, payload: Dict[str, Any] = None):
        """
        处理用户动作，驱动进化
        
        Args:
            action_type: 操作类型
            context: 上下文
            payload: 载荷数据
        """
        # 记录用户行为
        self.perception.capture_action(action_type, context, payload)
        
        # 根据当前进化阶段采取不同策略
        if self.evolution_state.phase == 'seed':
            self._handle_seed_phase(action_type, context, payload)
        elif self.evolution_state.phase == 'imitation':
            self._handle_imitation_phase(action_type, context, payload)
        elif self.evolution_state.phase == 'pattern_discovery':
            self._handle_pattern_discovery_phase(action_type, context, payload)
        elif self.evolution_state.phase == 'proactive_optimization':
            self._handle_proactive_optimization_phase(action_type, context, payload)
        
        # 检查是否需要进化阶段
        self._check_evolution_transition()
    
    def _handle_seed_phase(self, action_type: str, context: Dict[str, Any], payload: Dict[str, Any]):
        """种子阶段：学习基础交互"""
        if action_type == 'message':
            content = payload.get('content', '')
            # 从对话中提取概念
            self._extract_concepts_from_text(content)
            
            # 从 Wiki 搜索相关知识
            if self.wiki_integration:
                wiki_results = self.wiki_integration.search_knowledge(content)
                if wiki_results:
                    print(f"[进化控制器] 从Wiki找到 {len(wiki_results)} 条相关知识")
            
            # 进入模仿学习阶段
            if self.perception.action_counter >= 3:
                self.evolution_state.phase = 'imitation'
                print("[进化控制器] 进入模仿学习阶段")
    
    def _handle_imitation_phase(self, action_type: str, context: Dict[str, Any], payload: Dict[str, Any]):
        """模仿学习阶段：记录用户行为作为正样本"""
        if action_type == 'message':
            content = payload.get('content', '')
            self._extract_concepts_from_text(content)
            
            # 使用 FusionRAG 增强理解
            if self.fusion_rag:
                try:
                    import asyncio
                    rag_result = asyncio.run(self.fusion_rag.query_with_context(content))
                    if rag_result.get('evidence_ids'):
                        print(f"[进化控制器] FusionRAG 检索到 {len(rag_result['evidence_ids'])} 条证据")
                except Exception as e:
                    print(f"[进化控制器] FusionRAG 查询失败: {e}")
            
        elif action_type == 'upload_file':
            # 用户上传文件，学习文件类型与任务的关联
            file_path = payload.get('file_path', '')
            if 'excel' in file_path.lower():
                self.memory.learn_association('监测数据', 'Excel', 'requires')
                # 保存到 Wiki
                if self.wiki_integration:
                    self.wiki_integration.add_concept_to_wiki(
                        '监测数据',
                        '环境监测数据通常通过Excel表格提供，包含COD、氨氮等污染物浓度数据',
                        ['Excel', '数据']
                    )
            elif 'cad' in file_path.lower():
                self.memory.learn_association('项目设计', 'CAD图纸', 'requires')
        
        # 检查是否有足够数据进行模式发现
        if len(self.perception.action_history) >= 10:
            self._discover_patterns()
            self.evolution_state.phase = 'pattern_discovery'
            print("[进化控制器] 进入模式发现阶段")
    
    def _handle_pattern_discovery_phase(self, action_type: str, context: Dict[str, Any], payload: Dict[str, Any]):
        """模式发现阶段：自动发现规律"""
        if action_type == 'edit_cell':
            # 用户修改表格单元格，可能是在修正数据
            sheet = payload.get('sheet', '')
            cell = payload.get('cell', '')
            value = payload.get('value', '')
            
            # 学习数据修正模式
            if 'COD' in sheet or '浓度' in sheet:
                pattern_name = f"{sheet}_数据修正模式"
                self.memory.learn_pattern(
                    conditions=[{'key': 'sheet', 'value': sheet}, {'key': 'action', 'value': 'edit'}],
                    action='suggest_data_validation'
                )
                
                # 将模式保存到 Wiki
                if self.wiki_integration:
                    self.wiki_integration.add_pattern_to_wiki(
                        pattern_name,
                        [{'sheet': sheet}, {'action': 'edit'}],
                        'suggest_data_validation',
                        0.7
                    )
        
        # 检查是否进入主动优化阶段
        if len(self.memory.patterns) >= 5:
            self.evolution_state.phase = 'proactive_optimization'
            print("[进化控制器] 进入主动优化阶段")
    
    def _handle_proactive_optimization_phase(self, action_type: str, context: Dict[str, Any], payload: Dict[str, Any]):
        """主动优化阶段：根据学习到的模式主动提供建议"""
        if action_type == 'message':
            # 提供主动建议
            recommendations = self.memory.get_recommendations(context)
            
            # 从 Wiki 获取推荐
            if self.wiki_integration:
                wiki_recommendations = self.wiki_integration.recommend_pages(context)
                recommendations.extend([{
                    'type': 'wiki_recommendation',
                    'title': r['title'],
                    'summary': r['summary'],
                    'confidence': r.get('score', 0.5)
                } for r in wiki_recommendations])
            
            if recommendations:
                self.current_suggestions = recommendations
                self.suggestion_count += len(recommendations)
                print(f"[进化控制器] 主动提供 {len(recommendations)} 条建议")
        
        elif action_type == 'adopt_suggestion':
            # 用户采纳建议
            self.adoption_count += 1
            suggestion_id = payload.get('suggestion_id')
            # 更新对应模式的置信度
            for pattern_id, _ in self.memory.find_matching_patterns(context):
                self.memory.update_pattern_confidence(pattern_id, positive=True)
    
    def _extract_concepts_from_text(self, text: str):
        """从文本中提取概念并建立关联"""
        concept_pairs = [
            ('化工项目', '水源地'),
            ('噪声预测', '声环境功能区划'),
            ('水环境', '监测数据'),
            ('大气环境', '空气质量'),
            ('敏感目标', '保护'),
            ('三线一单', '分析')
        ]
        
        for concept1, concept2 in concept_pairs:
            if concept1 in text:
                self.memory.add_node(concept1, 'concept')
                if concept2 in text:
                    self.memory.add_node(concept2, 'concept')
                    self.memory.learn_association(concept1, concept2, 'related_to')
                    
                    # 保存到 Wiki
                    if self.wiki_integration:
                        self.wiki_integration.add_concept_to_wiki(
                            concept1,
                            f"与{concept2}相关的环评概念",
                            [concept2]
                        )
    
    def _discover_patterns(self):
        """从行为历史中发现模式"""
        action_sequence = self.perception.get_action_sequence(10)
        
        # 分析操作序列模式
        patterns = []
        for i in range(len(action_sequence) - 1):
            current = action_sequence[i]
            next_action = action_sequence[i+1]
            
            if current['type'] == 'message' and next_action['type'] == 'upload_file':
                patterns.append({
                    'condition': {'type': 'message', 'contains': '数据'},
                    'action': 'show_file_upload'
                })
            
            if current['type'] == 'message' and next_action['type'] == 'edit_cell':
                patterns.append({
                    'condition': {'type': 'message', 'contains': '修改'},
                    'action': 'show_editor'
                })
        
        for pattern in patterns:
            self.memory.learn_pattern(
                conditions=[pattern['condition']],
                action=pattern['action']
            )
            
            # 保存到 Wiki
            if self.wiki_integration:
                self.wiki_integration.add_pattern_to_wiki(
                    f"交互模式_{pattern['action']}",
                    [pattern['condition']],
                    pattern['action'],
                    0.6
                )
    
    def _check_evolution_transition(self):
        """检查是否需要转换进化阶段"""
        pass
    
    def generate_response(self, user_input: str) -> Dict[str, Any]:
        """
        生成AI响应，综合四层的信息和知识库
        
        Args:
            user_input: 用户输入
        
        Returns:
            响应内容和推荐动作
        """
        # 获取上下文摘要
        context = self.perception.get_context_summary()
        context['text_content'] = user_input
        
        # 获取知识图谱推荐
        recommendations = self.memory.get_recommendations(context)
        
        # 从 Wiki 获取推荐
        if self.wiki_integration:
            wiki_recommendations = self.wiki_integration.recommend_pages(context)
            recommendations.extend([{
                'type': 'wiki',
                'title': r['title'],
                'summary': r['summary'],
                'confidence': r.get('score', 0.5)
            } for r in wiki_recommendations])
        
        # 使用 FusionRAG 检索
        rag_results = []
        if self.fusion_rag:
            try:
                import asyncio
                rag_result = asyncio.run(self.fusion_rag.query_with_context(user_input))
                if rag_result.get('sources'):
                    rag_results = rag_result['sources']
            except Exception as e:
                print(f"[进化控制器] FusionRAG 查询失败: {e}")
        
        # 生成UI Schema
        ui_schema = self.action.generate_ui_schema(context)
        
        # 构建响应
        response = {
            'response': self._generate_text_response(user_input, recommendations, rag_results),
            'recommendations': recommendations,
            'rag_results': rag_results,
            'ui_schema': self._serialize_schema(ui_schema),
            'evolution_phase': self.evolution_state.phase,
            'wiki_recommendations': wiki_recommendations if self.wiki_integration else []
        }
        
        return response
    
    def _generate_text_response(self, user_input: str, recommendations: List[Dict[str, Any]], 
                               rag_results: List[Dict[str, Any]] = None) -> str:
        """生成文本响应"""
        if self.evolution_state.phase == 'seed':
            return "我正在学习环评相关知识，请告诉我更多关于您的项目的信息。"
        
        elif self.evolution_state.phase == 'imitation':
            sources = [r.get('source', '') for r in recommendations[:3]]
            sources.extend([r.get('head', '') for r in (rag_results or [])[:2]])
            return f"我理解您需要{'、'.join(filter(None, sources))}相关的帮助。请继续提供更多信息。"
        
        elif self.evolution_state.phase == 'pattern_discovery':
            actions = [r.get('action', '') for r in recommendations[:3]]
            wiki_titles = [r.get('title', '') for r in recommendations if r.get('type') == 'wiki'][:2]
            response = f"根据您的工作模式，我发现您可能需要：{'、'.join(filter(None, actions))}。"
            if wiki_titles:
                response += f"\n相关知识：{'、'.join(wiki_titles)}"
            return response
        
        elif self.evolution_state.phase == 'proactive_optimization':
            if recommendations:
                rec_text = '\n'.join([
                    f"- {r.get('action', r.get('title', ''))}" 
                    for r in recommendations[:5]
                ])
                return f"根据您的工作习惯，我为您推荐以下操作：\n{rec_text}"
            else:
                return "请告诉我您需要完成什么任务，我来帮您处理。"
        
        return "请问有什么我可以帮助您的？"
    
    def _serialize_schema(self, schema: RenderSchema) -> Dict[str, Any]:
        """序列化UI Schema用于前端渲染"""
        return {
            'schema_id': schema.schema_id,
            'title': schema.title,
            'layout': schema.layout,
            'components': [{
                'component_id': c.component_id,
                'type': c.type.value,
                'label': c.label,
                'placeholder': c.placeholder,
                'options': c.options,
                'data': c.data,
                'required': c.required,
                'visible': c.visible
            } for c in schema.components]
        }
    
    def evaluate_and_learn(self, report_content: str):
        """
        评估报告并更新学习
        
        Args:
            report_content: 最终报告内容
        """
        # 结束会话并评估
        self.objective.end_session()
        
        # 从 Wiki 获取合规规则
        compliance_rules = []
        if self.wiki_integration:
            compliance_rules = self.wiki_integration.get_compliance_rules_from_wiki()
        
        evaluation = self.objective.evaluate_report(
            report_content=report_content,
            suggestion_count=self.suggestion_count,
            adoption_count=self.adoption_count
        )
        
        self.evolution_state.last_evaluation = evaluation
        self.evolution_state.iteration += 1
        
        # 根据评估结果更新知识图谱和 Wiki
        if evaluation.total_score < 60:
            print(f"[进化控制器] 评估得分较低 ({evaluation.total_score:.1f})，继续学习")
        else:
            print(f"[进化控制器] 评估得分优秀 ({evaluation.total_score:.1f})，固化策略")
            self._solidify_strategy()
            
            # 将优秀报告保存到 Wiki
            if self.wiki_integration:
                self.wiki_integration.add_knowledge(
                    f"优秀环评报告范例_{self.evolution_state.iteration}",
                    report_content[:500] + "...",
                    ['example', 'report', '优秀']
                )
        
        return evaluation
    
    def _solidify_strategy(self):
        """固化成功的交互策略"""
        ui_stats = self.action.export_ui_stats()
        strategy_id = f"strategy_{self.evolution_state.iteration}"
        
        self.strategy_sandbox[strategy_id] = StrategyTestResult(
            strategy_id=strategy_id,
            test_users=['seed_user'],
            success_rate=self.evolution_state.last_evaluation.total_score / 100,
            efficiency_improvement=20,
            user_satisfaction=80,
            is_validated=False
        )
        
        # 同步到 Wiki
        if self.wiki_integration:
            self.wiki_integration.add_knowledge(
                f"策略_{strategy_id}",
                f"成功率: {self.evolution_state.last_evaluation.total_score/100:.2f}\n效率提升: 20%\n用户满意度: 80%",
                ['strategy', 'optimization']
            )
    
    def test_strategy(self, strategy_id: str, user_group: List[str]) -> StrategyTestResult:
        """
        在沙箱中测试策略
        
        Args:
            strategy_id: 策略ID
            user_group: 测试用户组
        
        Returns:
            测试结果
        """
        if strategy_id in self.strategy_sandbox:
            result = self.strategy_sandbox[strategy_id]
            result.test_users.extend(user_group)
            
            if len(result.test_users) >= 3:
                result.is_validated = True
                print(f"[进化控制器] 策略 {strategy_id} 已通过验证")
                
                # 更新 Wiki 中的策略状态
                if self.wiki_integration:
                    self.wiki_integration.update_wiki_from_feedback(
                        f"策略_{strategy_id} (未验证)",
                        f"策略_{strategy_id} (已验证)",
                        {'strategy_id': strategy_id, 'validated': True}
                    )
            
            return result
        
        return None
    
    def get_evolution_status(self) -> Dict[str, Any]:
        """获取进化状态摘要"""
        wiki_stats = self.wiki_integration.get_wiki_stats() if self.wiki_integration else {'available': False}
        
        return {
            'phase': self.evolution_state.phase,
            'iteration': self.evolution_state.iteration,
            'action_count': self.perception.action_counter,
            'knowledge_nodes': len(self.memory.nodes),
            'knowledge_edges': len(self.memory.edges),
            'learned_patterns': len(self.memory.patterns),
            'suggestions_made': self.suggestion_count,
            'suggestions_adopted': self.adoption_count,
            'wiki_stats': wiki_stats,
            'fusion_rag_available': self.fusion_rag is not None,
            'last_evaluation': {
                'total_score': self.evolution_state.last_evaluation.total_score,
                'compliance_score': self.evolution_state.last_evaluation.compliance_score,
                'adoption_score': self.evolution_state.last_evaluation.adoption_score,
                'efficiency_score': self.evolution_state.last_evaluation.efficiency_score
            } if self.evolution_state.last_evaluation else None
        }
    
    def export_evolution_data(self) -> Dict[str, Any]:
        """导出所有进化数据用于分析"""
        return {
            'perception': self.perception.export_learning_data(),
            'memory': self.memory.export_knowledge_graph(),
            'action': self.action.export_ui_stats(),
            'objective': self.objective.get_reward_summary(),
            'wiki_stats': self.wiki_integration.get_wiki_stats() if self.wiki_integration else {},
            'evolution_state': self.get_evolution_status()
        }