"""
智能创作与专业审核增强系统 - 统一调度器

整合：专业审核引擎 + 智能创作助手 + 知识图谱 + 协同创作 + 质量认证
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

# 导入各子系统
from business.professional_review import (
    ProfessionalReviewSystem, ReviewDomain, ReviewLevel, ReviewStatus,
    Document as ReviewDocument, ReviewResult, ReviewOpinion
)
from business.creative_assistant import (
    CreativeAssistantSystem, ContentType, WritingStyle,
    WritingContext, ContentAnalysis
)
from business.knowledge_graph import KnowledgeGraphSystem
from business.collaboration import CollaborationSystem
from business.quality_certification import (
    QualitySystem, QualityReport, CertLevel
)


class CreativeReviewIntegratedSystem:
    """
    智能创作与专业审核增强系统 - 集成系统
    
    工作流程:
    创作 -> 智能辅助 -> 专业审核 -> 质量认证 -> 协同优化 -> 分享传播
    """
    
    def __init__(self):
        # 初始化各子系统
        self.review_system = ProfessionalReviewSystem()
        self.creative_system = CreativeAssistantSystem()
        self.knowledge_system = KnowledgeGraphSystem()
        self.collaboration_system = CollaborationSystem()
        self.quality_system = QualitySystem()
        
        # 工作流记录
        self.workflows: Dict[str, Dict] = {}
        
        # 统计
        self.stats = {
            "total_documents": 0,
            "total_reviews": 0,
            "total_certs": 0,
            "avg_quality_score": 0.0
        }
    
    # ========== 创作流程 ==========
    
    def create_with_assistance(self, title: str, content: str, domain: str = "general",
                               author: str = "") -> Dict:
        """
        智能创作：创建文档并获取创作辅助
        """
        doc_id = str(uuid.uuid4())
        
        # 1. 分析内容
        analysis = self.creative_system.analyze(content, domain)
        
        # 2. 获取建议
        suggestions = self.creative_system.suggest(content, domain)
        
        # 3. 改进内容
        improved_content = self.creative_system.improve(content, domain)
        
        # 4. 创建审核文档
        review_domain = ReviewDomain(domain) if domain in [d.value for d in ReviewDomain] else ReviewDomain.GENERAL
        review_doc = self.review_system.create_document(title, improved_content, review_domain, author)
        
        # 5. 更新工作流
        self.workflows[doc_id] = {
            "doc_id": doc_id,
            "review_doc_id": review_doc.doc_id,
            "title": title,
            "author": author,
            "domain": domain,
            "created_at": datetime.now().isoformat(),
            "stage": "created",
            "quality_score": 0.0
        }
        
        self.stats["total_documents"] += 1
        
        return {
            "doc_id": doc_id,
            "review_doc_id": review_doc.doc_id,
            "original_content": content,
            "improved_content": improved_content,
            "analysis": self._format_analysis(analysis),
            "suggestions": [self._format_suggestion(s) for s in suggestions]
        }
    
    # ========== 审核流程 ==========
    
    def review_document(self, doc_id: str, level: ReviewLevel = ReviewLevel.AUTO_PREVIEW) -> Dict:
        """
        专业审核：多阶段审核流程
        """
        workflow = self.workflows.get(doc_id)
        if not workflow:
            raise ValueError(f"Workflow {doc_id} not found")
        
        # 执行审核
        result = self.review_system.review(workflow["review_doc_id"], level)
        
        # 生成审核意见
        opinion = self.review_system.generate_opinion(result)
        
        # 更新工作流
        workflow["review_result_id"] = result.result_id
        workflow["review_score"] = result.overall_score
        workflow["review_level"] = level.value
        workflow["stage"] = "reviewed"
        
        self.stats["total_reviews"] += 1
        
        return {
            "doc_id": doc_id,
            "review_result": self._format_review_result(result),
            "opinion": self._format_opinion(opinion),
            "issues": [self._format_issue(i) for i in result.issues],
            "processing_time_ms": result.processing_time_ms
        }
    
    def multi_domain_review(self, doc_id: str, domains: List[str]) -> List[Dict]:
        """
        多领域审核
        """
        workflow = self.workflows.get(doc_id)
        if not workflow:
            raise ValueError(f"Workflow {doc_id} not found")
        
        review_domains = []
        for d in domains:
            if d in [rd.value for rd in ReviewDomain]:
                review_domains.append(ReviewDomain(d))
        
        results = self.review_system.multi_review(workflow["review_doc_id"], review_domains)
        
        return [{
            "domain": r.domain.value,
            "score": r.overall_score,
            "issues_count": len(r.issues),
            "status": r.status.value
        } for r in results]
    
    # ========== 质量认证 ==========
    
    def certify_quality(self, doc_id: str) -> Dict:
        """
        质量认证：评估并颁发认证
        """
        workflow = self.workflows.get(doc_id)
        if not workflow:
            raise ValueError(f"Workflow {doc_id} not found")
        
        # 获取审核结果
        review_result = None
        review_doc = self.review_system.documents.get(workflow["review_doc_id"])
        if review_doc:
            review_result = review_doc.review_result
        
        # 执行认证
        document = {
            "id": doc_id,
            "title": workflow["title"],
            "content": review_doc.content if review_doc else "",
            "author": workflow["author"]
        }
        
        cert_report = self.quality_system.certify_document(
            document,
            workflow["author"],
            review_result
        )
        
        # 更新工作流
        workflow["cert_id"] = cert_report.report_id
        workflow["quality_score"] = cert_report.overall_score
        workflow["cert_level"] = cert_report.cert_level.value
        workflow["stage"] = "certified"
        
        self.stats["total_certs"] += 1
        
        return self._format_cert_report(cert_report)
    
    # ========== 协同创作 ==========
    
    def create_workspace(self, name: str, owner_id: str) -> Dict:
        """创建协作工作空间"""
        workspace = self.collaboration_system.create_workspace(name, owner_id)
        return {
            "workspace_id": workspace.workspace_id,
            "name": workspace.name,
            "created_at": workspace.created_at.isoformat()
        }
    
    def collaborate_on_document(self, workspace_id: str, title: str, owner_id: str) -> Dict:
        """创建协作文档"""
        doc = self.collaboration_system.create_document(workspace_id, title, owner_id)
        
        # 关联到工作流
        doc_id = str(uuid.uuid4())
        self.workflows[doc_id] = {
            "doc_id": doc_id,
            "collab_doc_id": doc.doc_id,
            "workspace_id": workspace_id,
            "title": title,
            "author": owner_id,
            "created_at": datetime.now().isoformat(),
            "stage": "collaborating"
        }
        
        return {
            "doc_id": doc_id,
            "collab_doc_id": doc.doc_id,
            "workspace_id": workspace_id
        }
    
    def add_collaboration_comment(self, doc_id: str, user_id: str, content: str) -> Dict:
        """添加协作评论"""
        workflow = self.workflows.get(doc_id)
        if not workflow or "collab_doc_id" not in workflow:
            raise ValueError(f"Collaborative document {doc_id} not found")
        
        comment = self.collaboration_system.add_comment(
            workflow["collab_doc_id"],
            user_id,
            content
        )
        
        return {
            "comment_id": comment.comment_id,
            "content": comment.content,
            "created_at": comment.created_at.isoformat()
        }
    
    # ========== 知识管理 ==========
    
    def add_to_knowledge_base(self, doc_id: str) -> Dict:
        """添加到知识库"""
        workflow = self.workflows.get(doc_id)
        if not workflow:
            raise ValueError(f"Workflow {doc_id} not found")
        
        review_doc = self.review_system.documents.get(workflow.get("review_doc_id", ""))
        
        entry = {
            "title": workflow["title"],
            "content": review_doc.content if review_doc else "",
            "domain": workflow["domain"],
            "author": workflow["author"],
            "quality_score": workflow.get("quality_score", 0),
            "tags": [workflow["domain"]] if workflow["domain"] else []
        }
        
        entry_id = self.knowledge_system.add_entry(entry)
        
        # 关联知识库条目
        workflow["knowledge_entry_id"] = entry_id
        workflow["stage"] = "knowledge_added"
        
        return {
            "entry_id": entry_id,
            "title": entry["title"]
        }
    
    def search_knowledge(self, query: str, domain: str = None) -> List[Dict]:
        """搜索知识库"""
        return self.knowledge_system.query(query, category=domain)
    
    # ========== 分享传播 ==========
    
    def prepare_for_share(self, doc_id: str) -> Dict:
        """准备分享：生成分享数据包"""
        workflow = self.workflows.get(doc_id)
        if not workflow:
            raise ValueError(f"Workflow {doc_id} not found")
        
        # 获取认证信息
        cert = self.quality_system.get_certification(workflow.get("cert_id", ""))
        
        # 获取审核结果
        review_doc = self.review_system.documents.get(workflow.get("review_doc_id", ""))
        
        share_package = {
            "title": workflow["title"],
            "author": workflow["author"],
            "domain": workflow["domain"],
            "quality_score": workflow.get("quality_score", 0),
            "cert_level": workflow.get("cert_level", "none"),
            "review_score": workflow.get("review_score", 0),
            "content": review_doc.content if review_doc else "",
            "created_at": workflow["created_at"],
            "share_code": self._generate_share_code(doc_id)
        }
        
        workflow["stage"] = "ready_to_share"
        
        return share_package
    
    def _generate_share_code(self, doc_id: str) -> str:
        """生成分享码"""
        import hashlib
        return hashlib.md5(f"{doc_id}{datetime.now().isoformat()}".encode()).hexdigest()[:8]
    
    # ========== 格式化输出 ==========
    
    def _format_analysis(self, analysis: ContentAnalysis) -> Dict:
        return {
            "word_count": analysis.word_count,
            "char_count": analysis.char_count,
            "sentence_count": analysis.sentence_count,
            "paragraph_count": analysis.paragraph_count,
            "readability_score": analysis.readability_score,
            "quality_score": analysis.quality_score,
            "complexity": analysis.complexity,
            "structure_tags": analysis.structure_tags,
            "keywords": analysis.keywords,
            "issues": analysis.issues
        }
    
    def _format_suggestion(self, suggestion) -> Dict:
        return {
            "type": suggestion.type,
            "text": suggestion.text,
            "confidence": suggestion.confidence,
            "reason": suggestion.reason
        }
    
    def _format_review_result(self, result: ReviewResult) -> Dict:
        return {
            "result_id": result.result_id,
            "overall_score": result.overall_score,
            "quality_level": result.quality_level.value,
            "status": result.status.value,
            "issue_counts": {
                "critical": result.critical_count,
                "major": result.major_count,
                "minor": result.minor_count,
                "suggestion": result.suggestion_count
            }
        }
    
    def _format_issue(self, issue) -> Dict:
        return {
            "title": issue.title,
            "description": issue.description,
            "severity": issue.severity.value,
            "category": issue.category.value,
            "suggestion": issue.suggestion
        }
    
    def _format_opinion(self, opinion: ReviewOpinion) -> Dict:
        return {
            "summary": opinion.summary,
            "verdict": opinion.verdict,
            "key_findings": opinion.key_findings,
            "strengths": opinion.strengths,
            "improvements": opinion.improvements
        }
    
    def _format_cert_report(self, report: QualityReport) -> Dict:
        return {
            "cert_id": report.report_id,
            "overall_score": report.overall_score,
            "cert_level": report.cert_level.value,
            "certified": report.certified,
            "metrics": {
                "accuracy": report.metrics.accuracy,
                "completeness": report.metrics.completeness,
                "consistency": report.metrics.consistency,
                "clarity": report.metrics.clarity,
                "professionalism": report.metrics.professionalism,
                "innovation": report.metrics.innovation
            },
            "strengths": report.strengths,
            "weaknesses": report.weaknesses,
            "recommendations": report.recommendations
        }
    
    # ========== 统计 ==========
    
    def get_system_stats(self) -> Dict:
        """获取系统统计"""
        review_stats = self.review_system.get_statistics()
        quality_stats = self.quality_system.get_stats()
        collab_stats = self.collaboration_system.get_activities(limit=1)
        knowledge_stats = self.knowledge_system.get_stats()
        
        return {
            "total_documents": self.stats["total_documents"],
            "total_reviews": self.stats["total_reviews"],
            "total_certs": self.stats["total_certs"],
            "review_stats": review_stats,
            "quality_stats": quality_stats,
            "knowledge_stats": knowledge_stats,
            "collaboration_stats": {
                "active_workspaces": len(self.collaboration_system.workspaces),
                "total_documents": len(self.collaboration_system.documents)
            }
        }
    
    def get_workflow_status(self, doc_id: str) -> Dict:
        """获取工作流状态"""
        workflow = self.workflows.get(doc_id, {})
        return {
            "doc_id": doc_id,
            "stage": workflow.get("stage", "unknown"),
            "quality_score": workflow.get("quality_score", 0),
            "cert_level": workflow.get("cert_level", "none")
        }


def create_integrated_system() -> CreativeReviewIntegratedSystem:
    """创建集成系统"""
    return CreativeReviewIntegratedSystem()


# ========== 便捷函数 ==========

def quick_create_and_review(title: str, content: str, domain: str = "general") -> Dict:
    """快捷创建并审核"""
    system = create_integrated_system()
    
    # 创建
    create_result = system.create_with_assistance(title, content, domain)
    
    # 审核
    review_result = system.review_document(create_result["doc_id"])
    
    # 认证
    cert_result = system.certify_quality(create_result["doc_id"])
    
    return {
        "doc_id": create_result["doc_id"],
        "review": review_result,
        "certification": cert_result
    }
