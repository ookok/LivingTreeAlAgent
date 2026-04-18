# =================================================================
# 溯源报告生成器 - Provenance Report Generator
# =================================================================
# 功能：
# 1. 生成可视化溯源报告
# 2. 支持多种格式（HTML/Markdown/PDF）
# 3. 可信交付包生成
# =================================================================

import json
import time
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime


class ReportFormat(Enum):
    """报告格式"""
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"


class ReportTemplate(Enum):
    """报告模板"""
    BASIC = "basic"               # 基础溯源
    KNOWLEDGE = "knowledge"       # 知识溯源
    PRODUCT = "product"           # 商品溯源
    SERVICE = "service"           # 服务溯源
    DELIVERY = "delivery"        # 可信交付包


@dataclass
class ProvenanceReport:
    """
    溯源报告

    包含完整的溯源信息和元数据
    """
    report_id: str
    report_type: str
    title: str

    # 目标实体
    target_node_id: str
    target_name: str
    target_type: str

    # 溯源链
    provenance_chain: List[Dict[str, Any]] = field(default_factory=list)
    derivation_paths: List[List[Dict[str, Any]]] = field(default_factory=list)

    # 版本历史
    version_history: List[Dict[str, Any]] = field(default_factory=list)

    # 事件日志摘要
    event_summary: Dict[str, Any] = field(default_factory=dict)

    # 图谱关系
    relationships: List[Dict[str, Any]] = field(default_factory=list)

    # 元数据
    generated_at: float = field(default_factory=time.time)
    generated_by: str = "system"
    template: str = "basic"

    # 签名
    content_hash: str = ""        # 报告内容哈希
    signature: str = ""           # 数字签名（可选）

    @property
    def generated_at_str(self) -> str:
        return datetime.fromtimestamp(self.generated_at).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "report_id": self.report_id,
            "report_type": self.report_type,
            "title": self.title,
            "target_node_id": self.target_node_id,
            "target_name": self.target_name,
            "target_type": self.target_type,
            "provenance_chain": self.provenance_chain,
            "derivation_paths": self.derivation_paths,
            "version_history": self.version_history,
            "event_summary": self.event_summary,
            "relationships": self.relationships,
            "generated_at": self.generated_at_str,
            "generated_by": self.generated_by,
            "template": self.template,
            "content_hash": self.content_hash,
            "signature": self.signature
        }


class ProvenanceReportGenerator:
    """
    溯源报告生成器

    功能：
    1. 从图谱和事件日志生成完整溯源报告
    2. 支持多种格式导出
    3. 生成可信交付包
    """

    def __init__(
        self,
        graph: Any = None,        # ProvenanceGraph
        event_logger: Any = None  # EventLogger
    ):
        self.graph = graph
        self.event_logger = event_logger

    def generate_report(
        self,
        node_id: str,
        template: ReportTemplate = ReportTemplate.BASIC,
        include_events: bool = True,
        include_graph: bool = True
    ) -> ProvenanceReport:
        """
        生成溯源报告

        Args:
            node_id: 目标节点ID
            template: 报告模板
            include_events: 是否包含事件日志
            include_graph: 是否包含图谱关系

        Returns:
            溯源报告
        """
        # 获取节点信息
        node_data = self.graph.get_node(node_id) if self.graph else None
        if not node_data:
            node_data = {"node_id": node_id, "name": "Unknown", "node_type": "unknown"}

        # 构建报告
        report = ProvenanceReport(
            report_id=f"rpt_{int(time.time())}_{node_id[:8]}",
            report_type=template.value,
            title=f"溯源报告: {node_data.get('name', node_id)}",
            target_node_id=node_id,
            target_name=node_data.get("name", ""),
            target_type=node_data.get("node_type", ""),
            template=template.value
        )

        # 获取溯源链
        if self.graph:
            report.provenance_chain = self.graph.trace_provenance(node_id)
            report.derivation_paths = self.graph.trace_derivation(node_id)

            # 获取关系
            neighbors = self.graph.query_neighbors(node_id)
            report.relationships = [
                {
                    "node_id": n.get("node_id"),
                    "node_name": n.get("name"),
                    "relation": n.get("relation"),
                    "relation_display": n.get("relation_display")
                }
                for n in neighbors[:20]  # 限制数量
            ]

        # 获取事件日志
        if include_events and self.event_logger:
            events = self.event_logger.get_entity_events(node_id)
            report.event_summary = {
                "total_events": len(events),
                "events_by_type": self._count_events_by_type(events),
                "first_event": events[0].timestamp_str if events else None,
                "last_event": events[-1].timestamp_str if events else None,
                "recent_events": [
                    {
                        "event_id": e.event_id,
                        "event_type": e.event_type.value,
                        "operator": e.operator,
                        "timestamp": e.timestamp_str
                    }
                    for e in events[-10:]  # 最近10条
                ]
            }

        # 版本历史
        if node_data.get("versions"):
            report.version_history = node_data.get("versions", [])

        # 计算报告哈希
        report.content_hash = self._compute_report_hash(report)

        return report

    def _count_events_by_type(self, events: List) -> Dict[str, int]:
        """统计事件类型"""
        counts: Dict[str, int] = {}
        for event in events:
            event_type = event.event_type.value if hasattr(event, 'event_type') else str(event)
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts

    def _compute_report_hash(self, report: ProvenanceReport) -> str:
        """计算报告哈希"""
        import hashlib
        content = json.dumps(report.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    # ========== 格式导出 ==========

    def export_report(
        self,
        report: ProvenanceReport,
        format: ReportFormat,
        output_path: str = None
    ) -> str:
        """
        导出报告

        Args:
            report: 报告
            format: 格式
            output_path: 输出路径

        Returns:
            输出文件路径
        """
        if output_path is None:
            output_path = str(Path.home() / ".hermes-desktop" / "provenance" / "reports")
            Path(output_path).mkdir(parents=True, exist_ok=True)

        if format == ReportFormat.HTML:
            filepath = f"{output_path}/{report.report_id}.html"
            content = self._generate_html(report)
        elif format == ReportFormat.MARKDOWN:
            filepath = f"{output_path}/{report.report_id}.md"
            content = self._generate_markdown(report)
        elif format == ReportFormat.JSON:
            filepath = f"{output_path}/{report.report_id}.json"
            content = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath

    def _generate_html(self, report: ProvenanceReport) -> str:
        """生成 HTML 格式报告"""
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.title}</title>
    <style>
        :root {{
            --primary: #1a5f2a;
            --accent: #2e8b3d;
            --bg: #f8faf9;
            --card: #ffffff;
            --text: #1a1a1a;
            --text-secondary: #666;
            --border: #e0e0e0;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}

        .header {{
            background: linear-gradient(135deg, var(--primary), var(--accent));
            color: white;
            padding: 30px;
            text-align: center;
        }}

        .header h1 {{ font-size: 1.5rem; margin-bottom: 10px; }}
        .header .meta {{ opacity: 0.9; font-size: 0.85rem; }}

        .container {{ max-width: 900px; margin: 0 auto; padding: 24px; }}

        .card {{
            background: var(--card);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}

        .card h2 {{
            font-size: 1.1rem;
            color: var(--primary);
            margin-bottom: 16px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--accent);
        }}

        .timeline {{
            border-left: 3px solid var(--accent);
            padding-left: 20px;
            margin-left: 10px;
        }}

        .timeline-item {{
            position: relative;
            padding-bottom: 20px;
        }}

        .timeline-item::before {{
            content: '';
            position: absolute;
            left: -26px;
            top: 0;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--accent);
        }}

        .timeline-item .time {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-bottom: 4px;
        }}

        .timeline-item .content {{
            background: #f8f9f8;
            padding: 12px;
            border-radius: 8px;
        }}

        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            background: #e8f5e9;
            color: var(--primary);
        }}

        .relation-list {{
            list-style: none;
        }}

        .relation-list li {{
            padding: 10px;
            border-bottom: 1px solid var(--border);
        }}

        .relation-list li:last-child {{ border-bottom: none; }}

        .hash {{
            font-family: monospace;
            font-size: 0.85rem;
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 4px;
            word-break: break-all;
        }}

        .footer {{
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 0.8rem;
        }}
    </style>
</head>
<body>
    <header class="header">
        <h1>🌿 {report.title}</h1>
        <div class="meta">
            <div>报告ID: {report.report_id}</div>
            <div>生成时间: {report.generated_at_str}</div>
            <div>生成者: {report.generated_by}</div>
        </div>
    </header>

    <div class="container">
        <!-- 基本信息 -->
        <div class="card">
            <h2>📋 基本信息</h2>
            <table style="width:100%;">
                <tr><td style="width:120px;color:var(--text-secondary)">节点ID</td><td><code>{report.target_node_id}</code></td></tr>
                <tr><td style="color:var(--text-secondary)">名称</td><td>{report.target_name}</td></tr>
                <tr><td style="color:var(--text-secondary)">类型</td><td><span class="badge">{report.target_type}</span></td></tr>
            </table>
        </div>

        <!-- 溯源链 -->
        <div class="card">
            <h2>🔗 溯源链</h2>
            <div class="timeline">
"""

        # 添加溯源链节点
        for i, path in enumerate(report.provenance_chain[:5]):  # 最多5条路径
            for j, node in enumerate(path):
                depth = node.get("depth", 0)
                indent = "　" * depth
                relation = node.get("relation", "")
                relation_text = f"({relation})" if relation else ""

                html += f"""
                <div class="timeline-item">
                    <div class="time">{indent}{node.get('node_name', node.get('node_id', ''))} {relation_text}</div>
                    <div class="content">
                        <div>类型: {node.get('node_type', '')}</div>
                        <div>ID: <code>{node.get('node_id', '')}</code></div>
                    </div>
                </div>
"""

        html += """
            </div>
        </div>
"""

        # 添加关系
        if report.relationships:
            html += """
        <!-- 关联关系 -->
        <div class="card">
            <h2>🕸️ 关联关系</h2>
            <ul class="relation-list">
"""
            for rel in report.relationships[:10]:
                html += f"""
                <li>
                    <strong>{rel.get('node_name', rel.get('node_id', ''))}</strong>
                    <span class="badge">{rel.get('relation_display', rel.get('relation', ''))}</span>
                    <br>
                    <small style="color:var(--text-secondary)">ID: {rel.get('node_id', '')}</small>
                </li>
"""
            html += """
            </ul>
        </div>
"""

        # 添加事件摘要
        if report.event_summary:
            html += f"""
        <!-- 事件日志 -->
        <div class="card">
            <h2>📜 事件日志</h2>
            <p>共 {report.event_summary.get('total_events', 0)} 个事件</p>
            <p>首次: {report.event_summary.get('first_event', '-')}</p>
            <p>最近: {report.event_summary.get('last_event', '-')}</p>
        </div>
"""

        html += f"""
        <!-- 报告签名 -->
        <div class="card">
            <h2>🔐 报告签名</h2>
            <p>内容哈希 (SHA-256):</p>
            <div class="hash">{report.content_hash or 'N/A'}</div>
        </div>
    </div>

    <footer class="footer">
        <p>此报告由 Hermes Desktop 溯源系统生成</p>
        <p>报告ID: {report.report_id} · 生成时间: {report.generated_at_str}</p>
    </footer>
</body>
</html>"""

        return html

    def _generate_markdown(self, report: ProvenanceReport) -> str:
        """生成 Markdown 格式报告"""

        md = f"""# {report.title}

## 基本信息

| 属性 | 值 |
|------|-----|
| 报告ID | `{report.report_id}` |
| 目标节点ID | `{report.target_node_id}` |
| 名称 | {report.target_name} |
| 类型 | {report.target_type} |
| 生成时间 | {report.generated_at_str} |
| 生成者 | {report.generated_by} |

## 溯源链

"""

        for i, path in enumerate(report.provenance_chain[:5]):
            md += f"\n### 路径 {i+1}\n\n"
            for node in path:
                md += f"- **{node.get('node_name', node.get('node_id', ''))}**\n"
                md += f"  - ID: `{node.get('node_id', '')}`\n"
                md += f"  - 类型: {node.get('node_type', '')}\n"
                if node.get('relation'):
                    md += f"  - 关系: {node.get('relation')}\n"
                md += "\n"

        if report.relationships:
            md += "## 关联关系\n\n"
            for rel in report.relationships[:10]:
                md += f"- **{rel.get('node_name', rel.get('node_id', ''))}** ({rel.get('relation_display', rel.get('relation', ''))})\n"

        if report.event_summary:
            md += f"""
## 事件日志

- 总事件数: {report.event_summary.get('total_events', 0)}
- 首次事件: {report.event_summary.get('first_event', '-')}
- 最近事件: {report.event_summary.get('last_event', '-')}
"""

        md += f"""
## 报告签名

**内容哈希 (SHA-256):**
```
{report.content_hash or 'N/A'}
```

---

*此报告由 Hermes Desktop 溯源系统生成*
*报告ID: {report.report_id}*
*生成时间: {report.generated_at_str}*
"""

        return md

    # ========== 可信交付包 ==========

    def generate_delivery_package(
        self,
        node_id: str,
        output_dir: str = None
    ) -> Dict[str, str]:
        """
        生成可信交付包

        包含：
        1. 溯源报告 (HTML)
        2. 溯源报告 (Markdown)
        3. 原始数据 (JSON)
        4. 清单文件 (manifest.json)

        Args:
            node_id: 目标节点ID
            output_dir: 输出目录

        Returns:
            交付包文件路径映射
        """
        if output_dir is None:
            output_dir = str(Path.home() / ".hermes-desktop" / "provenance" / "delivery")
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 创建以节点ID命名的子目录
        package_dir = output_path / f"{node_id}_{int(time.time())}"
        package_dir.mkdir(exist_ok=True)

        # 生成报告
        report = self.generate_report(node_id, ReportTemplate.DELIVERY)

        # 导出各种格式
        files = {}

        html_path = self.export_report(report, ReportFormat.HTML, str(package_dir))
        files["html_report"] = html_path

        md_path = self.export_report(report, ReportFormat.MARKDOWN, str(package_dir))
        files["markdown_report"] = md_path

        json_path = self.export_report(report, ReportFormat.JSON, str(package_dir))
        files["json_data"] = json_path

        # 生成 manifest
        manifest = {
            "package_id": f"pkg_{int(time.time())}_{node_id[:8]}",
            "node_id": node_id,
            "generated_at": report.generated_at_str,
            "files": {
                "html_report": str(package_dir / f"{report.report_id}.html"),
                "markdown_report": str(package_dir / f"{report.report_id}.md"),
                "json_data": str(package_dir / f"{report.report_id}.json")
            },
            "content_hash": report.content_hash,
            "signature": report.signature
        }

        manifest_path = package_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        files["manifest"] = str(manifest_path)

        return files

    # ========== 批量报告 ==========

    def generate_batch_reports(
        self,
        node_ids: List[str],
        template: ReportTemplate = ReportTemplate.BASIC
    ) -> List[ProvenanceReport]:
        """
        批量生成报告

        Args:
            node_ids: 节点ID列表
            template: 报告模板

        Returns:
            报告列表
        """
        reports = []
        for node_id in node_ids:
            try:
                report = self.generate_report(node_id, template)
                reports.append(report)
            except Exception as e:
                print(f"[ReportGenerator] Failed to generate report for {node_id}: {e}")

        return reports
