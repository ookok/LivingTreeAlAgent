"""
专家训练模块 - 根据训练内容自主创建专家角色
支持从训练内容中提取专家特征，自动生成SKILL.md
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from client.src.business.expert_training.industry_classification import (
    get_industry_classifier,
    INDUSTRY_CATEGORIES,
    OCCUPATION_CATEGORIES
)
from client.src.business.nanochat_config import config as nano_config

# 使用 GlobalModelRouter（遵守系统架构设定）
try:
    from client.src.business.global_model_router import (
        get_global_router,
        ModelCapability,
        RoutingStrategy,
        call_model_sync
    )
    GLOBAL_ROUTER_AVAILABLE = True
except ImportError:
    GLOBAL_ROUTER_AVAILABLE = False
    get_global_router = None
    ModelCapability = None
    RoutingStrategy = None
    call_model_sync = None

# 导入 AI 科学家模块（用于知识发现）
try:
    from client.src.business.ai_scientist import (
        get_ai_scientist,
        get_domain_engine,
        list_registered_domains,
        KnowledgeDiscovery,
        KnowledgeDiscoveryEngine
    )
    AI_SCIENTIST_AVAILABLE = True
except ImportError:
    AI_SCIENTIST_AVAILABLE = False
    get_ai_scientist = None
    get_domain_engine = None
    list_registered_domains = None
    KnowledgeDiscovery = None
    KnowledgeDiscoveryEngine = None

logger = logging.getLogger(__name__)


class ExpertTrainer:
    """
    专家训练器 - 从训练内容中自动创建专家角色
    
    工作流程：
    1. 接收训练内容（文本、文档、对话记录等）
    2. 提取专家特征（专业领域、技能、知识范围）
    3. 匹配行业分类
    4. 生成SKILL.md文件
    5. 通知其他智能体
    """
    
    def __init__(self, skills_base_dir: Optional[str] = None):
        """
        初始化专家训练器
        
        Args:
            skills_base_dir: 技能存储基础目录，默认为 .livingtree/skills/agency-agents-zh/
        """
        if skills_base_dir is None:
            # 使用默认路径
            project_root = Path(__file__).parent.parent.parent.parent
            skills_base_dir = project_root / ".livingtree" / "skills" / "agency-agents-zh"
        
        self.skills_base_dir = Path(skills_base_dir)
        self.skills_base_dir.mkdir(parents=True, exist_ok=True)
        
        # 行业分类器
        self.industry_classifier = get_industry_classifier()
        
        # 使用 GlobalModelRouter（遵守系统架构设定）
        self.global_router = None
        if GLOBAL_ROUTER_AVAILABLE:
            try:
                self.global_router = get_global_router()
                print(f"[专家训练] GlobalModelRouter 加载成功")
            except Exception as e:
                print(f"[专家训练] 警告：GlobalModelRouter 初始化失败：{e}")
        
        # 知识发现引擎（延迟初始化，根据领域动态选择）
        self._domain_engine_cache = {}  # 缓存已创建的引擎实例
        if AI_SCIENTIST_AVAILABLE:
            print(f"[专家训练] AI科学家模块可用，支持领域：{list_registered_domains()}")
        else:
            print(f"[专家训练] 警告：AI科学家模块不可用")
        
        # 已存在的专家缓存
        self._expert_cache = None
        self._cache_mtime = 0
        
    def train_from_content(self, 
                           training_content: str,
                           expert_name: Optional[str] = None,
                           metadata: Optional[Dict] = None) -> Dict:
        """
        从训练内容中创建或更新专家角色
        
        Args:
            training_content: 训练内容（可以是对话记录、文档、知识库等）
            expert_name: 指定的专家名称（可选，自动生成）
            metadata: 额外的元数据（来源、创建者、标签等）
            
        Returns:
            创建结果字典，包含专家名称、路径、分类等信息
        """
        print(f"[专家训练] 开始分析训练内容 ({len(training_content)} 字符)...")
        
        # 1. 使用LLM分析训练内容，提取专家特征
        expert_profile = self._analyze_training_content(training_content, expert_name)
        
        if not expert_profile:
            return {
                "success": False,
                "error": "无法从训练内容中提取有效的专家特征"
            }
        
        print(f"[专家训练] 提取到专家特征：{expert_profile.get('name', '未知')}")
        print(f"[专家训练] 专业领域：{expert_profile.get('domain', '未知')}")
        
        # 2. 知识发现（集成 ai_scientist）
        if self.ai_scientist:
            knowledge_discoveries = self._discover_knowledge(training_content, expert_profile)
            if knowledge_discoveries:
                expert_profile["knowledge_discoveries"] = knowledge_discoveries
                print(f"[专家训练] 知识发现：发现 {len(knowledge_discoveries)} 条相关知识")
        
        # 3. 行业分类
        classification = self.industry_classifier.classify_expert(
            expert_description=expert_profile.get("description", ""),
            expert_name=expert_profile.get("name", "")
        )
        
        expert_profile["industry_classification"] = classification
        
        # 4. 生成专家目录名称和路径
        expert_dir_name = self._generate_expert_dir_name(expert_profile)
        expert_dir = self.skills_base_dir / expert_dir_name
        
        # 检查是否已存在
        is_update = expert_dir.exists()
        
        # 4. 生成SKILL.md
        skill_content = self._generate_skill_md(expert_profile, classification)
        
        # 5. 写入文件
        expert_dir.mkdir(parents=True, exist_ok=True)
        skill_file = expert_dir / "SKILL.md"
        
        if is_update:
            print(f"[专家训练] 更新现有专家：{expert_dir_name}")
        else:
            print(f"[专家训练] 创建新专家：{expert_dir_name}")
        
        skill_file.write_text(skill_content, encoding="utf-8")
        
        # 6. 更新索引文件
        self._update_expert_index(expert_profile, expert_dir_name, classification)
        
        # 7. 通知其他智能体
        notification = self._create_notification(expert_profile, expert_dir_name, is_update)
        self._notify_other_agents(notification)
        
        # 8. 清理缓存
        self._expert_cache = None
        
        return {
            "success": True,
            "expert_name": expert_profile.get("name"),
            "expert_dir": str(expert_dir),
            "skill_file": str(skill_file),
            "is_update": is_update,
            "industry_classification": classification,
            "notification": notification
        }
    
    def _analyze_training_content(self, content: str, suggested_name: Optional[str] = None) -> Optional[Dict]:
        """
        使用LLM分析训练内容，提取专家特征
        
        Returns:
            专家配置文件字典，包含name, domain, description, capabilities, workflows等
        """
        # 如果内容太长，截断
        max_length = 8000
        if len(content) > max_length:
            content = content[:max_length] + "\n...(内容过长，已截断)"
        
        prompt = f"""请分析以下训练内容，提取专家角色的核心特征，并以JSON格式返回。

训练内容：
---
{content}
---

请提取以下信息，返回严格的JSON格式（不要有任何其他输出）：
{{
    "name": "专家名称（中文，格式：领域+专家，如：环评专家、数据分析专家）",
    "english_name": "英文名称（小写，连字符分隔，如：environmental-impact-assessment-expert）",
    "domain": "专业领域（如：环境影响评价、数据分析、法律咨询等）",
    "description": "专家详细描述（200字以内，说明专业知识、擅长解决的问题）",
    "capabilities": ["能力1", "能力2", "能力3"],
    "workflows": ["工作流程1", "工作流程2"],
    "common_problems": ["常见问题1", "常见问题2"],
    "output_template": "输出模板描述",
    "keywords": ["关键词1", "关键词2"]
}}

要求：
1. name要简洁专业，体现核心能力
2. description要说明这个专家能解决什么问题
3. capabilities要具体可执行
4. 如果没有足够信息，某些字段可以为空数组
"""
        
        try:
            # 使用 GlobalModelRouter 调用 LLM（遵守系统架构设定）
            if not self.global_router:
                print("[专家训练] 警告：GlobalModelRouter 不可用，使用规则提取")
                return self._extract_expert_profile_rule_based(content, suggested_name)
            
            # 调用模型（同步方式）
            response = call_model_sync(
                capability=ModelCapability.CONTENT_GENERATION,  # 内容生成
                prompt=prompt,
                system_prompt="你是一个专家特征提取助手。只输出 JSON，不要解释。",
                strategy=RoutingStrategy.QUALITY  # 质量优先
            )
            
            if not response:
                print("[专家训练] LLM调用失败，使用规则提取")
                return self._extract_expert_profile_rule_based(content, suggested_name)
            
            # 解析JSON响应
            content_text = response  # call_model_sync 直接返回文本
            
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', content_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                profile = json.loads(json_str)
                return profile
            else:
                print(f"[专家训练] LLM返回格式异常：{content_text[:200]}")
                return self._extract_expert_profile_rule_based(content, suggested_name)
                
        except json.JSONDecodeError as e:
            print(f"[专家训练] JSON解析失败：{e}")
            return self._extract_expert_profile_rule_based(content, suggested_name)
        except Exception as e:
            print(f"[专家训练] LLM分析失败：{e}")
            return self._extract_expert_profile_rule_based(content, suggested_name)
    
    def _extract_expert_profile_rule_based(self, content: str, suggested_name: Optional[str] = None) -> Dict:
        """
        基于规则提取专家特征（LLM失败时的后备方案）
        """
        # 简单的关键词提取和分类
        content_lower = content.lower()
        
        # 尝试识别领域
        domain_keywords = {
            "环境": ["环保", "环境", "环评", "污染", "监测", "生态"],
            "IT": ["软件", "编程", "开发", "代码", "算法", "数据"],
            "金融": ["金融", "投资", "财务", "会计", "税务"],
            "法律": ["法律", "律师", "合同", "诉讼", "合规"],
            "医疗": ["医疗", "医生", "药品", "临床", "健康"],
            "教育": ["教育", "教学", "培训", "课程"],
            "工程": ["工程", "设计", "施工", "建筑"]
        }
        
        detected_domain = "通用"
        max_matches = 0
        for domain, keywords in domain_keywords.items():
            matches = sum(1 for kw in keywords if kw in content_lower)
            if matches > max_matches:
                max_matches = matches
                detected_domain = domain
        
        # 生成专家名称
        if suggested_name:
            name = suggested_name
        else:
            name = f"{detected_domain}专家"
        
        return {
            "name": name,
            "english_name": name.replace("专家", "-expert").lower(),
            "domain": detected_domain,
            "description": f"专注于{detected_domain}领域的专业顾问，提供专业咨询和问题解决方案。",
            "capabilities": [f"{detected_domain}问题分析", "解决方案设计", "专业建议"],
            "workflows": ["需求理解", "问题分析", "方案设计", "结果输出"],
            "common_problems": [],
            "output_template": "结构化分析报告",
            "keywords": [detected_domain]
        }
    
    def _discover_knowledge(self, training_content: str, expert_profile: Dict) -> List[Dict]:
        """
        使用通用知识发现引擎进行知识发现
        
        Args:
            training_content: 训练内容
            expert_profile: 已提取的专家特征
            
        Returns:
            知识发现列表
        """
        if not AI_SCIENTIST_AVAILABLE:
            return []
        
        try:
            # 获取专家的领域
            domain = expert_profile.get("domain", "general")
            
            # 获取对应的领域引擎（延迟初始化，使用缓存）
            engine = self._get_domain_engine(domain)
            if not engine:
                print(f"[专家训练] 未找到领域 {domain} 的引擎，使用通用引擎")
                engine = self._get_domain_engine("general")
            
            if not engine:
                return []
            
            # 构建项目数据（从训练内容中提取）
            project_data = self._extract_project_data(training_content, expert_profile)
            
            # 调用知识发现功能
            discoveries = engine.discover_knowledge(project_data)
            
            # 转换为可序列化的字典格式
            result = []
            for disc in discoveries:
                result.append({
                    "discovery_id": disc.discovery_id,
                    "discovery_type": disc.discovery_type,
                    "title": disc.title,
                    "description": disc.description,
                    "evidence": disc.evidence,
                    "confidence": disc.confidence,
                    "novelty": disc.novelty,
                    "implications": disc.implications,
                    "domain": disc.domain  # 添加领域信息
                })
            
            return result
            
        except Exception as e:
            print(f"[专家训练] 知识发现失败：{e}")
            import traceback
            traceback.print_exc()  # 打印详细错误信息
            return []
    
    def _get_domain_engine(self, domain: str):
        """获取领域引擎（带缓存）"""
        if domain in self._domain_engine_cache:
            return self._domain_engine_cache[domain]
        
        engine = get_domain_engine(domain)
        if engine:
            self._domain_engine_cache[domain] = engine
            print(f"[专家训练] 已初始化领域引擎：{domain}")
        
        return engine
    
    def _extract_project_data(self, training_content: str, expert_profile: Dict) -> Dict:
        """
        从训练内容中提取项目数据（用于知识发现）
        
        尝试提取工艺流程、排放信息等结构化数据
        """
        project_data = {
            "process_flow": [],
            "emissions": [],
            "domain": expert_profile.get("domain", ""),
            "expert_name": expert_profile.get("name", ""),
            "training_content": training_content[:1000]  # 限制长度
        }
        
        # 尝试提取工艺流程
        content_lower = training_content.lower()
        
        # 常见工艺流程关键词
        process_keywords = ["喷漆", "印刷", "焊接", "电镀", "铸造", "涂装", "清洗", "打磨"]
        for kw in process_keywords:
            if kw in content_lower:
                project_data["process_flow"].append(kw)
        
        # 常见污染物关键词
        pollutant_keywords = ["VOCs", "苯", "甲苯", "二甲苯", "COD", "NH3-N", "重金属", "颗粒物"]
        for kw in pollutant_keywords:
            if kw in content_lower:
                project_data["emissions"].append({"pollutant": kw})
        
        return project_data
    
    def _generate_expert_dir_name(self, expert_profile: Dict) -> str:
        """生成专家目录名称（英文小写，连字符分隔）"""
        english_name = expert_profile.get("english_name", "")
        if not english_name:
            # 从中文名称转换
            name = expert_profile.get("name", "unknown-expert")
            english_name = name.replace("专家", "-expert").lower()
        
        # 确保符合目录命名规范
        english_name = re.sub(r'[^a-z0-9\-]', '-', english_name.lower())
        english_name = re.sub(r'-+', '-', english_name).strip('-')
        
        return english_name
    
    def _generate_skill_md(self, expert_profile: Dict, classification: Dict) -> str:
        """
        生成SKILL.md文件内容
        
        格式规范：
        ---
        name: 专家名称
        description: 触发词描述
        location: 文件位置
        industry: 行业分类
        ---
        
        # 专家名称
        
        ## 核心能力
        ...
        """
        name = expert_profile.get("name", "未知专家")
        domain = expert_profile.get("domain", "")
        description = expert_profile.get("description", "")
        capabilities = expert_profile.get("capabilities", [])
        workflows = expert_profile.get("workflows", [])
        common_problems = expert_profile.get("common_problems", [])
        output_template = expert_profile.get("output_template", "")
        keywords = expert_profile.get("keywords", [])
        
        # 行业信息
        industry_code = classification.get("industry_code", "M")
        industry_name = classification.get("industry_name", "科学研究和技术服务业")
        
        # 构建触发词（从关键词和领域生成）
        trigger_words = list(set([domain] + keywords))
        trigger_description = f"当用户咨询{', '.join(trigger_words[:3])}相关问题时触发"
        
        # 获取知识发现
        knowledge_discoveries = expert_profile.get("knowledge_discoveries", [])
        
        # 生成SKILL.md内容
        content = f"""---
name: {name}
description: {trigger_description}
location: agency-agents-zh/{self._generate_expert_dir_name(expert_profile)}
industry_code: {industry_code}
industry_name: {industry_name}
domain: {domain}
created_at: {datetime.now().isoformat()}
---

# {name}

{description}

## 核心能力

{chr(10).join([f"- **{cap}**" for cap in capabilities]) if capabilities else "- 专业咨询"}

## 工作流程

{chr(10).join([f"{i+1}. {wf}" for i, wf in enumerate(workflows)]) if workflows else "1. 接收问题\n2. 分析需求\n3. 提供专业建议"}

## 常见问题

{chr(10).join([f"**Q: {q}**\nA: [专业解答]" for q in common_problems]) if common_problems else "**Q: 如何获取专业建议？**\nA: 描述您的具体问题，我会提供专业的分析和建议。"}

## 输出模板

{output_template if output_template else "结构化专业分析报告"}

## 知识发现"""
        
        # 添加知识发现部分
        if knowledge_discoveries:
            for disc in knowledge_discoveries:
                content += f"""
### {disc.get('title', '未知发现')}

**发现类型**: {disc.get('discovery_type', '未知')}  
**置信度**: {disc.get('confidence', 0):.2f}  
**创新性**: {disc.get('novelty', 0):.2f}  

{disc.get('description', '')}

**证据**:
{chr(10).join([f"- {ev}" for ev in disc.get('evidence', [])]) if disc.get('evidence') else "- 无"}

**启示**:
{chr(10).join([f"- {im}" for im in disc.get('implications', [])]) if disc.get('implications') else "- 无"}
"""
        else:
            content += "\n*暂无知识发现结果。*\n"
        
        # 继续添加其他部分
        content += f"""
## 行业分类

- **行业代码**: {industry_code}
- **行业名称**: {industry_name}
- **专业领域**: {domain}

## 使用说明

1. 描述您的具体问题或需求
2. 提供相关背景信息
3. 我会根据专业知识和发现的规律提供详细分析和建议

---

*此专家角色由AI训练系统自动生成，基于训练内容提取专业知识。*
*集成了AI科学家的知识发现功能，包含污染物关联、技术路线等深度分析。*
"""
        
        return content
    
    def _update_expert_index(self, expert_profile: Dict, dir_name: str, classification: Dict):
        """更新专家索引文件（按行业分类组织）"""
        index_dir = self.skills_base_dir.parent / "_index"
        index_dir.mkdir(parents=True, exist_ok=True)
        
        # 行业索引
        industry_code = classification.get("industry_code", "M")
        industry_index_file = index_dir / f"industry_{industry_code}.json"
        
        industry_data = {}
        if industry_index_file.exists():
            try:
                industry_data = json.loads(industry_index_file.read_text(encoding="utf-8"))
            except:
                industry_data = {}
        
        industry_data[dir_name] = {
            "name": expert_profile.get("name"),
            "domain": expert_profile.get("domain"),
            "description": expert_profile.get("description"),
            "path": f"agency-agents-zh/{dir_name}"
        }
        
        industry_index_file.write_text(
            json.dumps(industry_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        # 全局索引
        global_index_file = index_dir / "all_experts.json"
        global_data = {}
        if global_index_file.exists():
            try:
                global_data = json.loads(global_index_file.read_text(encoding="utf-8"))
            except:
                global_data = {}
        
        global_data[dir_name] = {
            "name": expert_profile.get("name"),
            "domain": expert_profile.get("domain"),
            "industry_code": industry_code,
            "industry_name": classification.get("industry_name"),
            "path": f"agency-agents-zh/{dir_name}",
            "updated_at": datetime.now().isoformat()
        }
        
        global_index_file.write_text(
            json.dumps(global_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def _create_notification(self, expert_profile: Dict, dir_name: str, is_update: bool) -> Dict:
        """创建通知消息"""
        action = "更新" if is_update else "创建"
        return {
            "type": "expert_created" if not is_update else "expert_updated",
            "timestamp": datetime.now().isoformat(),
            "expert_name": expert_profile.get("name"),
            "expert_dir": dir_name,
            "expert_path": str(self.skills_base_dir / dir_name),
            "domain": expert_profile.get("domain"),
            "industry": expert_profile.get("industry_classification", {}).get("industry_name"),
            "message": f"专家角色「{expert_profile.get('name')}」已{action}"
        }
    
    def _notify_other_agents(self, notification: Dict):
        """
        通知其他智能体
        
        实现方式：
        1. 写入通知文件，由其他智能体轮询
        2. 通过消息队列通知（如果已实现）
        3. 通过API通知（如果已实现）
        """
        notification_dir = Path(__file__).parent.parent.parent / ".livingtree" / "notifications"
        notification_dir.mkdir(parents=True, exist_ok=True)
        
        notification_file = notification_dir / f"expert_{int(time.time())}.json"
        
        try:
            notification_file.write_text(
                json.dumps(notification, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            print(f"[专家训练] 已写入通知文件：{notification_file}")
            
            # TODO: 实现其他通知方式
            # - 通过消息总线通知
            # - 通过WebSocket推送
            # - 通过API调用通知
            
        except Exception as e:
            print(f"[专家训练] 写入通知失败：{e}")
    
    def reorganize_by_industry(self) -> Dict:
        """
        按照行业和职业重新整理专家角色
        
        Returns:
            整理结果统计
        """
        print("[专家训练] 开始按行业重新整理专家角色...")
        
        # 1. 扫描所有现有专家
        experts = self._scan_all_experts()
        
        # 2. 按行业分类
        industry_groups = {}
        for expert in experts:
            classification = self.industry_classifier.classify_expert(
                expert.get("description", ""),
                expert.get("name", "")
            )
            industry_code = classification.get("industry_code", "M")
            
            if industry_code not in industry_groups:
                industry_groups[industry_code] = []
            industry_groups[industry_code].append({
                "expert": expert,
                "classification": classification
            })
        
        # 3. 生成整理报告
        report = {
            "total_experts": len(experts),
            "industry_count": len(industry_groups),
            "industry_distribution": {},
            "reorganization_time": datetime.now().isoformat()
        }
        
        for industry_code, expert_list in industry_groups.items():
            industry_name = INDUSTRY_CATEGORIES.get(industry_code, {}).get("name", "未知行业")
            report["industry_distribution"][industry_code] = {
                "industry_name": industry_name,
                "expert_count": len(expert_list),
                "experts": [e["expert"].get("name") for e in expert_list]
            }
        
        # 4. 保存整理报告
        report_dir = self.skills_base_dir.parent / "_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = report_dir / f"reorganization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        print(f"[专家训练] 整理完成，报告已保存：{report_file}")
        print(f"[专家训练] 共整理 {report['total_experts']} 个专家角色，分布在 {report['industry_count']} 个行业")
        
        return report
    
    def _scan_all_experts(self) -> List[Dict]:
        """扫描所有现有专家角色"""
        experts = []
        
        for expert_dir in self.skills_base_dir.iterdir():
            if not expert_dir.is_dir():
                continue
            
            skill_file = expert_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            
            try:
                content = skill_file.read_text(encoding="utf-8")
                
                # 提取frontmatter
                frontmatter_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
                if frontmatter_match:
                    frontmatter_text = frontmatter_match.group(1)
                    # 简单解析frontmatter
                    metadata = {}
                    for line in frontmatter_text.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            metadata[key.strip()] = value.strip()
                    
                    experts.append({
                        "name": metadata.get("name", expert_dir.name),
                        "dir_name": expert_dir.name,
                        "description": metadata.get("description", ""),
                        "domain": metadata.get("domain", ""),
                        "industry_code": metadata.get("industry_code", ""),
                        "path": str(skill_file)
                    })
            except Exception as e:
                print(f"[专家训练] 扫描专家失败 {expert_dir.name}: {e}")
        
        return experts
    
    def batch_train_from_directory(self, directory: str, progress_callback=None) -> Dict:
        """
        批量从目录中的文件训练专家
        
        Args:
            directory: 包含训练文件的目录
            progress_callback: 进度回调函数
            
        Returns:
            批量训练结果
        """
        directory = Path(directory)
        if not directory.exists():
            return {"success": False, "error": f"目录不存在：{directory}"}
        
        # 支持的文件类型
        supported_extensions = [".txt", ".md", ".pdf", ".docx", ".csv", ".json"]
        
        training_files = []
        for ext in supported_extensions:
            training_files.extend(directory.glob(f"**/*{ext}"))
        
        total_files = len(training_files)
        if total_files == 0:
            return {"success": False, "error": "未找到支持的训练文件"}
        
        print(f"[专家训练] 开始批量训练，共 {total_files} 个文件")
        
        results = {
            "total": total_files,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }
        
        for i, file_path in enumerate(training_files):
            if progress_callback:
                progress = (i / total_files) * 100
                progress_callback(progress, f"处理文件 {i+1}/{total_files}: {file_path.name}")
            
            try:
                # 读取文件内容
                content = self._read_training_file(file_path)
                if not content:
                    results["skipped"] += 1
                    continue
                
                # 训练
                result = self.train_from_content(
                    training_content=content,
                    expert_name=file_path.stem
                )
                
                if result.get("success"):
                    results["success"] += 1
                    results["details"].append({
                        "file": str(file_path),
                        "expert": result.get("expert_name"),
                        "status": "success"
                    })
                else:
                    results["failed"] += 1
                    results["details"].append({
                        "file": str(file_path),
                        "error": result.get("error"),
                        "status": "failed"
                    })
                    
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "file": str(file_path),
                    "error": str(e),
                    "status": "failed"
                })
        
        if progress_callback:
            progress_callback(100, "批量训练完成")
        
        print(f"[专家训练] 批量训练完成：成功 {results['success']}，失败 {results['failed']}，跳过 {results['skipped']}")
        
        return results
    
    def _read_training_file(self, file_path: Path) -> Optional[str]:
        """读取训练文件内容"""
        try:
            if file_path.suffix in [".txt", ".md", ".csv", ".json"]:
                return file_path.read_text(encoding="utf-8", errors="ignore")
            elif file_path.suffix == ".pdf":
                # TODO: 实现PDF读取
                return None
            elif file_path.suffix == ".docx":
                # TODO: 实现DOCX读取
                return None
            else:
                return None
        except Exception as e:
            print(f"[专家训练] 读取文件失败 {file_path}: {e}")
            return None


# 全局训练器实例
_trainer_instance = None

def get_expert_trainer() -> ExpertTrainer:
    """获取专家训练器单例"""
    global _trainer_instance
    if _trainer_instance is None:
        _trainer_instance = ExpertTrainer()
    return _trainer_instance


if __name__ == "__main__":
    # 测试代码
    trainer = get_expert_trainer()
    
    # 测试从内容训练专家
    test_content = """
    我是环境影响评价专家，专注于建设项目环境影响评价报告的编制和审查。
    熟悉《环境影响评价法》、《建设项目环境保护管理条例》等法律法规。
    擅长大气环境影响预测、水环境影响分析、噪声影响评价等技术工作。
    能够使用AERMOD、ADMS等大气扩散模型进行模拟预测。
    """
    
    result = trainer.train_from_content(test_content, "环评专家")
    print("\n训练结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
