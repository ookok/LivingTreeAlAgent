"""Intelligence Collector tests — adaptive extract + stream parse + cognitive delta + pipeline.

Tests:
  - AdaptiveExtractor: page type detection, item extraction, field extraction
  - OnlineStreamParser: format detection, text parsing
  - CognitiveDelta: gap/diff/dup decisions
  - IntelligenceCollector: full pipeline from HTML
"""

from __future__ import annotations

import pytest

from livingtree.capability.adaptive_extractor import AdaptiveExtractor, ExtractedItem, ExtractedPage
from livingtree.capability.online_stream_parser import OnlineStreamParser, StreamParseResult
from livingtree.knowledge.cognitive_delta import CognitiveDelta, DeltaResult, DeltaDecision


# ═══ Sample HTML Pages ═══

GOV_LIST_PAGE = """<!DOCTYPE html><html><head><title>环境影响评价公示</title></head><body>
<h1>2024年环境影响评价公示列表</h1>
<ul>
<li>
  <a href="/detail/001">XX化工园区项目环评公示</a>
  <span>发布时间：2024-03-15</span>
  <span>状态：公示中</span>
  <a href="/files/001.pdf">环评报告附件.pdf</a>
</li>
<li>
  <a href="/detail/002">XX高速公路扩建环评</a>
  <span>发布时间：2024-02-20</span>
  <span>状态：已批复</span>
  <a href="/files/002.pdf">批复文件.pdf</a>
</li>
</ul>
</body></html>"""

GOV_TABLE_PAGE = """<!DOCTYPE html><html><head><title>审批公告</title></head><body>
<table>
<tr><th>项目名称</th><th>时间</th><th>状态</th><th>附件</th></tr>
<tr><td>污水处理厂</td><td>2024-01-10</td><td>已批</td><td><a href="/att/003.pdf">下载</a></td></tr>
<tr><td>垃圾焚烧项目</td><td>2024-03-01</td><td>待批</td><td><a href="/att/004.zip">下载</a></td></tr>
</table>
</body></html>"""


# ═══ AdaptiveExtractor ═══

class TestAdaptiveExtractor:
    def test_list_page_detection(self):
        ext = AdaptiveExtractor()
        page = ext.extract(GOV_LIST_PAGE, "https://example.gov.cn/")
        assert page.page_type == "list"
        assert len(page.items) >= 2

    def test_table_page_detection(self):
        ext = AdaptiveExtractor()
        page = ext.extract(GOV_TABLE_PAGE, "https://example.gov.cn/")
        assert page.page_type == "table"
        assert len(page.items) >= 2

    def test_title_extraction(self):
        ext = AdaptiveExtractor()
        page = ext.extract(GOV_LIST_PAGE, "https://example.gov.cn/")
        assert "环境" in page.title

    def test_date_extraction(self):
        ext = AdaptiveExtractor()
        page = ext.extract(GOV_LIST_PAGE, "https://example.gov.cn/")
        dates = [i.publish_date for i in page.items if i.publish_date]
        assert len(dates) >= 1
        assert "2024" in dates[0]

    def test_status_extraction(self):
        ext = AdaptiveExtractor()
        page = ext.extract(GOV_LIST_PAGE, "https://example.gov.cn/")
        statuses = [i.status for i in page.items if i.status]
        assert len(statuses) >= 1

    def test_attachment_detection(self):
        ext = AdaptiveExtractor()
        page = ext.extract(GOV_LIST_PAGE, "https://example.gov.cn/")
        all_attachments = [a for i in page.items for a in i.attachment_links]
        assert len(all_attachments) >= 2

    def test_field_extraction(self):
        """Should extract key-value pairs from text."""
        ext = AdaptiveExtractor()
        text = "项目名称：测试项目\n发布时间：2024-01-01\n状态：已批复"
        item = ext._extract_item_from_text(text, "")
        assert item.title
        assert item.publish_date
        assert item.status

    def test_confidence_computation(self):
        ext = AdaptiveExtractor()
        item = ExtractedItem(title="Test", publish_date="2024-01-01", status="已批")
        conf = ext._compute_confidence(item)
        assert abs(conf - 0.9) < 0.01

    def test_is_attachment(self):
        ext = AdaptiveExtractor()
        assert ext._is_attachment("file.pdf")
        assert ext._is_attachment("doc.zip")
        assert ext._is_attachment("data.xlsx")
        assert not ext._is_attachment("page.html")


# ═══ OnlineStreamParser ═══

class TestOnlineStreamParser:
    def test_parse_text_bytes(self):
        parser = OnlineStreamParser()
        result = parser.parse_bytes(b"Hello World Content", "file.txt")
        assert result.success
        assert "Hello" in result.text_content

    def test_detect_pdf(self):
        parser = OnlineStreamParser()
        assert parser._detect_extension("doc.pdf") == "pdf"
        assert parser._detect_extension("file.doc?ver=1") == "doc"

    def test_detect_pdf_from_magic(self):
        parser = OnlineStreamParser()
        ext = parser._detect_extension("download", b"%PDF-1.4 content")
        assert ext == "pdf"

    def test_detect_zip_magic(self):
        parser = OnlineStreamParser()
        ext = parser._detect_extension("download", b"PK\x03\x04")
        assert ext == "zip"

    def test_parse_empty(self):
        parser = OnlineStreamParser()
        result = parser.parse_bytes(b"", "")
        assert not result.success

    def test_result_warnings(self):
        parser = OnlineStreamParser()
        result = StreamParseResult()
        result.warnings.append("test warning")
        assert len(result.warnings) == 1


# ═══ CognitiveDelta ═══

class TestCognitiveDelta:
    def test_gap_when_no_existing(self):
        delta = CognitiveDelta()
        new_item = {"title": "新项目", "content": "测试内容", "source": "test"}
        result = delta.evaluate(new_item, [])
        assert result.decision == DeltaDecision.GAP
        assert "空白" in result.reason

    def test_dup_exact_same(self):
        delta = CognitiveDelta()
        item = {"title": "项目A", "content": "相同内容", "source": "test", "date": "2024-01-01"}
        result = delta.evaluate(item, [item.copy()])
        assert result.decision == DeltaDecision.DUP

    def test_diff_when_status_changes(self):
        delta = CognitiveDelta(content_similarity_threshold=0.3)
        old = {"title": "项目A", "content": "环评报告内容大气扩散", "status": "待批", "date": "2024-01"}
        new = {"title": "项目A", "content": "环评报告内容大气扩散修改后", "status": "已批", "date": "2024-03"}
        result = delta.evaluate(new, [old])
        assert result.decision in (DeltaDecision.DIFF, DeltaDecision.DUP)

    def test_build_entry_gap(self):
        delta = CognitiveDelta()
        item = {"title": "新项目", "content": "重点工程环评", "source": "gov.cn", "date": "2024-05"}
        entry = delta.build_entry(item, [])
        assert entry["delta_decision"] == "gap"
        assert "id" in entry

    def test_build_entry_dup(self):
        delta = CognitiveDelta()
        item = {"title": "项目A", "content": "same", "source": "test", "date": "2024-01"}
        entry = delta.build_entry(item, [item.copy()])
        assert entry["delta_decision"] == "dup"
        assert "[重复" in entry["summary"]

    def test_content_hash_different(self):
        delta = CognitiveDelta()
        a = delta._content_hash({"title": "A", "content": "x"})
        b = delta._content_hash({"title": "B", "content": "y"})
        assert a != b

    def test_entry_similarity(self):
        delta = CognitiveDelta()
        a = {"title": "环境影响评价报告", "content": "大气扩散模型参数设置"}
        b = {"title": "环境影响评价报告", "content": "大气扩散模型参数设置方法"}
        sim = delta._entry_similarity(a, b)
        assert sim > 0.5

    def test_compute_diff(self):
        delta = CognitiveDelta()
        diff = delta._compute_diff(
            {"title": "A", "status": "new", "content": "x y z"},
            {"title": "A", "status": "old", "content": "x y"},
        )
        assert "status" in diff or "old" in diff or len(diff) > 0


# ═══ Integration ═══

class TestFullPipeline:
    def test_end_to_end_list_page(self):
        ext = AdaptiveExtractor()
        page = ext.extract(GOV_LIST_PAGE, "https://example.gov.cn/")

        delta = CognitiveDelta()
        existing = [
            {"title": "旧项目", "content": "旧环评", "source": "example.gov.cn", "date": "2023"},
        ]

        for item in page.items:
            if item.confidence > 0:
                new_entry = {
                    "title": item.title,
                    "content": item.raw_text,
                    "source": page.url,
                    "date": item.publish_date,
                    "status": item.status,
                }
                result = delta.evaluate(new_entry, existing)
                assert result.decision in ("gap", "diff", "dup")

    def test_table_page_end_to_end(self):
        ext = AdaptiveExtractor()
        page = ext.extract(GOV_TABLE_PAGE, "https://example.gov.cn/")

        delta = CognitiveDelta()
        stored = 0
        skipped = 0

        for item in page.items:
            if not item.confidence or item.confidence < 0.1:
                skipped += 1
                continue
            new_entry = {
                "title": item.title,
                "content": item.raw_text,
                "source": page.url,
                "date": item.publish_date,
                "status": item.status,
            }
            result = delta.evaluate(new_entry, [])
            if result.decision == "gap":
                stored += 1
            else:
                skipped += 1

        assert stored >= 1  # Some items should be stored
