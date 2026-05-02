"""
报告生成器
DocLifecycle 报告生成器 - 多格式报告生成
"""

import json
import logging
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import ReportInfo, ReviewResult, ReviewTask

logger = logging.getLogger(__name__)


class ReportGenerator:
    """报告生成器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._reports_dir = Path.home() / ".hermes-desktop" / "reports"
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        
        self._initialized = True
        logger.info(f"ReportGenerator initialized, reports dir: {self._reports_dir}")
    
    def set_reports_dir(self, directory: str):
        """设置报告目录"""
        self._reports_dir = Path(directory)
        self._reports_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_html_report(self, result: ReviewResult, task: ReviewTask, 
                            template: str = "default") -> ReportInfo:
        """生成HTML报告"""
        report_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{result.task_id[:8]}"
        
        # 创建日期目录
        date_dir = self._reports_dir / datetime.now().strftime('%Y-%m-%d') / 'html'
        date_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = date_dir / f"{report_id}.html"
        
        # 生成HTML内容
        html_content = self._render_html_template(result, task, template)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # 创建报告信息
        report_info = ReportInfo(
            report_id=report_id,
            task_id=result.task_id,
            doc_id=result.doc_id,
            report_type="single",
            report_format="html",
            file_path=str(file_path),
            file_size=len(html_content),
            title=f"审核报告 - {task.doc_info.file_name if task.doc_info else result.doc_id}",
            created_at=datetime.now()
        )
        
        logger.info(f"Generated HTML report: {report_id}")
        return report_info
    
    def _render_html_template(self, result: ReviewResult, task: ReviewTask,
                              template: str) -> str:
        """渲染HTML模板"""
        doc_name = task.doc_info.file_name if task.doc_info else "Unknown"
        quality_level = self._get_quality_level(result.quality_score)
        
        risk_colors = {
            "low": "#22c55e",
            "medium": "#f59e0b", 
            "high": "#ef4444",
            "critical": "#dc2626"
        }
        risk_color = risk_colors.get(result.risk_level, "#22c55e")
        
        issues_html = ""
        for issue in result.issues:
            severity_color = {
                "critical": "#dc2626",
                "high": "#ef4444",
                "medium": "#f59e0b",
                "low": "#22c55e"
            }.get(issue.get("severity", "low"), "#22c55e")
            
            issues_html += f"""
            <div class="issue-item">
                <div class="issue-header">
                    <span class="severity-badge" style="background:{severity_color}">
                        {issue.get("severity", "info").upper()}
                    </span>
                    <span class="issue-type">{issue.get("type", "问题")}</span>
                </div>
                <div class="issue-content">{issue.get("description", "")}</div>
                {f'<div class="issue-location">位置: {issue.get("location", "")}</div>' if issue.get("location") else ""}
            </div>
            """
        
        suggestions_html = ""
        for i, suggestion in enumerate(result.suggestions, 1):
            suggestions_html += f"""
            <div class="suggestion-item">
                <div class="suggestion-header">
                    <span class="suggestion-number">{i}</span>
                    <span class="suggestion-type">{suggestion.get("type", "建议")}</span>
                </div>
                <div class="suggestion-content">{suggestion.get("description", "")}</div>
            </div>
            """
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>审核报告 - {doc_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        .header .doc-name {{ font-size: 18px; opacity: 0.9; }}
        .header .meta {{ font-size: 14px; opacity: 0.8; margin-top: 10px; }}
        .score-card {{ background: white; border-radius: 12px; padding: 25px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .score-overview {{ display: flex; align-items: center; gap: 40px; }}
        .score-circle {{ width: 150px; height: 150px; border-radius: 50%; background: conic-gradient({quality_level['color']} {result.quality_score * 3.6}deg, #e5e7eb {result.quality_score * 3.6}deg); display: flex; align-items: center; justify-content: center; position: relative; }}
        .score-circle::before {{ content: ''; width: 120px; height: 120px; background: white; border-radius: 50%; position: absolute; }}
        .score-value {{ position: relative; text-align: center; }}
        .score-value .number {{ font-size: 42px; font-weight: bold; color: {quality_level['color']}; }}
        .score-value .label {{ font-size: 14px; color: #666; }}
        .score-dimensions {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 20px; }}
        .dimension {{ background: #f9fafb; padding: 12px 15px; border-radius: 8px; }}
        .dimension-label {{ font-size: 12px; color: #666; margin-bottom: 5px; }}
        .dimension-bar {{ height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden; }}
        .dimension-fill {{ height: 100%; background: {quality_level['color']}; border-radius: 4px; }}
        .dimension-value {{ font-size: 14px; font-weight: 600; color: #333; margin-top: 5px; }}
        .section {{ background: white; border-radius: 12px; padding: 25px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .section h2 {{ font-size: 20px; color: #333; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #e5e7eb; }}
        .issue-item {{ border-left: 4px solid #ef4444; background: #fef2f2; padding: 15px; margin-bottom: 15px; border-radius: 8px; }}
        .issue-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
        .severity-badge {{ padding: 3px 10px; border-radius: 12px; font-size: 11px; color: white; font-weight: 600; }}
        .issue-type {{ font-weight: 600; color: #333; }}
        .issue-content {{ color: #555; margin-left: 5px; }}
        .suggestion-item {{ border-left: 4px solid #22c55e; background: #f0fdf4; padding: 15px; margin-bottom: 15px; border-radius: 8px; }}
        .suggestion-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
        .suggestion-number {{ width: 24px; height: 24px; background: #22c55e; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; }}
        .suggestion-type {{ font-weight: 600; color: #333; }}
        .suggestion-content {{ color: #555; margin-left: 5px; }}
        .summary {{ background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); padding: 20px; border-radius: 12px; line-height: 1.8; }}
        .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
        .tag {{ display: inline-block; padding: 4px 12px; background: #e0e7ff; color: #3730a3; border-radius: 20px; font-size: 12px; margin: 3px; }}
        .risk-tag {{ background: {risk_color}; color: white; }}
        .tags-section {{ margin-top: 20px; padding: 15px; background: #f9fafb; border-radius: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📋 文档审核报告</h1>
            <div class="doc-name">{doc_name}</div>
            <div class="meta">
                报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 
                处理时间: {result.processing_time:.2f}秒 | 
                风险等级: <span class="tag risk-tag">{result.risk_level.upper()}</span>
            </div>
        </div>
        
        <div class="score-card">
            <div class="score-overview">
                <div class="score-circle">
                    <div class="score-value">
                        <div class="number">{result.quality_score:.1f}</div>
                        <div class="label">{quality_level['label']}</div>
                    </div>
                </div>
                <div class="score-dimensions">
                    <div class="dimension">
                        <div class="dimension-label">准确性</div>
                        <div class="dimension-bar"><div class="dimension-fill" style="width: {result.accuracy_score}%"></div></div>
                        <div class="dimension-value">{result.accuracy_score:.1f}</div>
                    </div>
                    <div class="dimension">
                        <div class="dimension-label">完整性</div>
                        <div class="dimension-bar"><div class="dimension-fill" style="width: {result.completeness_score}%"></div></div>
                        <div class="dimension-value">{result.completeness_score:.1f}</div>
                    </div>
                    <div class="dimension">
                        <div class="dimension-label">一致性</div>
                        <div class="dimension-bar"><div class="dimension-fill" style="width: {result.consistency_score}%"></div></div>
                        <div class="dimension-value">{result.consistency_score:.1f}</div>
                    </div>
                    <div class="dimension">
                        <div class="dimension-label">清晰度</div>
                        <div class="dimension-bar"><div class="dimension-fill" style="width: {result.clarity_score}%"></div></div>
                        <div class="dimension-value">{result.clarity_score:.1f}</div>
                    </div>
                    <div class="dimension">
                        <div class="dimension-label">专业性</div>
                        <div class="dimension-bar"><div class="dimension-fill" style="width: {result.professionalism_score}%"></div></div>
                        <div class="dimension-value">{result.professionalism_score:.1f}</div>
                    </div>
                    <div class="dimension">
                        <div class="dimension-label">创新性</div>
                        <div class="dimension-bar"><div class="dimension-fill" style="width: {result.innovation_score}%"></div></div>
                        <div class="dimension-value">{result.innovation_score:.1f}</div>
                    </div>
                </div>
            </div>
            <div class="tags-section">
                <div style="margin-bottom: 10px; color: #666; font-size: 14px;">文档分类</div>
                <span class="tag">{result.category or '未分类'}</span>
                {''.join(f'<span class="tag">{tag}</span>' for tag in result.tags)}
            </div>
        </div>
        
        <div class="section">
            <h2>📝 审核摘要</h2>
            <div class="summary">{result.summary or '暂无摘要信息'}</div>
        </div>
        
        <div class="section">
            <h2>⚠️ 发现的问题 ({len(result.issues)})</h2>
            {issues_html or '<p>未发现问题</p>'}
        </div>
        
        <div class="section">
            <h2>💡 改进建议 ({len(result.suggestions)})</h2>
            {suggestions_html or '<p>暂无建议</p>'}
        </div>
        
        {f'''
        <div class="section">
            <h2>🔒 敏感词检测</h2>
            <div style="background: #fef2f2; padding: 15px; border-radius: 8px;">
                <div style="margin-bottom: 10px;">发现 <strong>{len(result.sensitive_words_found)}</strong> 个敏感词</div>
                {', '.join(f"<code>{w}</code>" for w in result.sensitive_words_found[:20])}
            </div>
        </div>
        ''' if result.sensitive_words_found else ''}
        
        <div class="footer">
            由 Hermes Desktop 文档审核系统生成 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>"""
        return html
    
    def _get_quality_level(self, score: float) -> Dict[str, Any]:
        """获取质量等级"""
        if score >= 90:
            return {"label": "优秀", "color": "#22c55e"}
        elif score >= 80:
            return {"label": "良好", "color": "#84cc16"}
        elif score >= 70:
            return {"label": "中等", "color": "#f59e0b"}
        elif score >= 60:
            return {"label": "及格", "color": "#ef4444"}
        else:
            return {"label": "较差", "color": "#dc2626"}
    
    def generate_json_report(self, result: ReviewResult, task: ReviewTask) -> ReportInfo:
        """生成JSON报告"""
        report_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{result.task_id[:8]}"
        date_dir = self._reports_dir / datetime.now().strftime('%Y-%m-%d') / 'json'
        date_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = date_dir / f"{report_id}.json"
        
        report_data = {
            "report_id": report_id,
            "task_id": result.task_id,
            "doc_id": result.doc_id,
            "doc_name": task.doc_info.file_name if task.doc_info else "Unknown",
            "generated_at": datetime.now().isoformat(),
            "processing_time": result.processing_time,
            "quality_score": result.quality_score,
            "dimensions": {
                "accuracy": result.accuracy_score,
                "completeness": result.completeness_score,
                "consistency": result.consistency_score,
                "clarity": result.clarity_score,
                "professionalism": result.professionalism_score,
                "innovation": result.innovation_score
            },
            "risk_level": result.risk_level,
            "category": result.category,
            "tags": result.tags,
            "summary": result.summary,
            "issues": result.issues,
            "suggestions": result.suggestions,
            "sensitive_words_found": result.sensitive_words_found
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        report_info = ReportInfo(
            report_id=report_id,
            task_id=result.task_id,
            doc_id=result.doc_id,
            report_type="single",
            report_format="json",
            file_path=str(file_path),
            file_size=len(json.dumps(report_data)),
            title=f"审核报告 - {task.doc_info.file_name if task.doc_info else result.doc_id}",
            created_at=datetime.now()
        )
        
        logger.info(f"Generated JSON report: {report_id}")
        return report_info
    
    def generate_batch_summary(self, results: List[ReviewResult], 
                               title: str = "批量审核汇总报告") -> ReportInfo:
        """生成批量汇总报告"""
        report_id = f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        date_dir = self._reports_dir / datetime.now().strftime('%Y-%m-%d') / 'summary'
        date_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = date_dir / f"{report_id}.html"
        
        total_docs = len(results)
        avg_score = sum(r.quality_score for r in results) / total_docs if total_docs else 0
        total_issues = sum(len(r.issues) for r in results)
        total_suggestions = sum(len(r.suggestions) for r in results)
        
        docs_html = ""
        for r in sorted(results, key=lambda x: x.quality_score):
            level = self._get_quality_level(r.quality_score)
            docs_html += f"""
            <tr>
                <td>{r.doc_id[:16]}</td>
                <td><span style="color: {level['color']}; font-weight: 600;">{r.quality_score:.1f}</span></td>
                <td>{r.category or '-'}</td>
                <td>{len(r.issues)}</td>
                <td>{len(r.suggestions)}</td>
                <td>{r.risk_level}</td>
            </tr>
            """
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
        .header h1 {{ margin-bottom: 10px; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .stat-value {{ font-size: 36px; font-weight: bold; color: #667eea; }}
        .stat-label {{ color: #666; font-size: 14px; margin-top: 5px; }}
        .section {{ background: white; padding: 25px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .section h2 {{ margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #e5e7eb; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
        th {{ background: #f9fafb; font-weight: 600; }}
        .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 {title}</h1>
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="stats">
            <div class="stat-card"><div class="stat-value">{total_docs}</div><div class="stat-label">审核文档数</div></div>
            <div class="stat-card"><div class="stat-value">{avg_score:.1f}</div><div class="stat-label">平均质量分</div></div>
            <div class="stat-card"><div class="stat-value">{total_issues}</div><div class="stat-label">发现问题数</div></div>
            <div class="stat-card"><div class="stat-value">{total_suggestions}</div><div class="stat-label">改进建议数</div></div>
        </div>
        
        <div class="section">
            <h2>📄 文档详情</h2>
            <table>
                <thead>
                    <tr><th>文档ID</th><th>质量分</th><th>分类</th><th>问题数</th><th>建议数</th><th>风险等级</th></tr>
                </thead>
                <tbody>{docs_html}</tbody>
            </table>
        </div>
        
        <div class="footer">由 Hermes Desktop 文档审核系统生成</div>
    </div>
</body>
</html>"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        report_info = ReportInfo(
            report_id=report_id,
            report_type="batch",
            report_format="html",
            file_path=str(file_path),
            file_size=len(html),
            title=title,
            created_at=datetime.now()
        )
        
        logger.info(f"Generated batch summary report: {report_id}")
        return report_info
    
    def export_reports(self, report_ids: List[str]) -> str:
        """导出多个报告"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_path = self._reports_dir / f"export_{timestamp}.zip"
        
        with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for report_id in report_ids:
                for ext in ['.html', '.json']:
                    pattern = f"**/*{report_id}*{ext}"
                    for file in self._reports_dir.glob(pattern):
                        zf.write(file, file.relative_to(self._reports_dir))
        
        logger.info(f"Exported {len(report_ids)} reports to {export_path}")
        return str(export_path)


# 全局实例
_report_generator: Optional[ReportGenerator] = None


def get_report_generator() -> ReportGenerator:
    """获取报告生成器实例"""
    global _report_generator
    if _report_generator is None:
        _report_generator = ReportGenerator()
    return _report_generator
