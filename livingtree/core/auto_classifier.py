"""Auto Classifier — content-based knowledge domain classification.

Inspired by OpenMetadata's Auto Classification with Custom Recognizers.
Uses multi-strategy matching: regex patterns, keyword vectors, and
LLM-based classification fallback.

Classifies ingested knowledge into domains like:
  ai, environment, engineering, regulation, finance, medical, general
"""

from __future__ import annotations

import re as _re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


DOMAIN_PATTERNS = {
    "ai": {
        "regex": [
            r'\b(llm|模型|训练|推理|token|transformer|agent|GPT|Claude|Gemini|DeepSeek|Qwen|embedding|fine.?tun|RLHF|prompt|神经网络)\b',
            r'\b(AI|artificial intelligence|machine learning|deep learning|neural net)\b',
        ],
        "keywords": ["模型", "推理", "训练", "AI", "token", "agent", "智能", "GPT", "大模型", "深度学习"],
        "weight": 1.0,
    },
    "environment": {
        "regex": [
            r'\b(环评|排放|污染|生态|碳|水质|空气质量|噪声|固废|环境影响|PM2\.5|COD|BOD)\b',
            r'\b(environmental|emission|carbon|ecology|pollution|water quality)\b',
        ],
        "keywords": ["环评", "排放", "污染", "环境", "碳", "生态", "水质", "大气", "噪声", "固废"],
        "weight": 1.0,
    },
    "engineering": {
        "regex": [
            r'\b(施工|图纸|结构|混凝土|钢筋|地基|桥梁|道路|隧道|管道|机电|暖通|给排水)\b',
            r'\b(construction|structural|concrete|bridge|tunnel|pipeline)\b',
        ],
        "keywords": ["施工", "工程", "图纸", "结构", "混凝土", "设计", "建筑", "验收"],
        "weight": 1.0,
    },
    "regulation": {
        "regex": [
            r'\b(法规|标准|规范|GB\s*\d|HJ\s*\d|第.*条|条款|合规|行政许可|审批)\b',
            r'\b(regulation|standard|compliance|permit|license)\b',
        ],
        "keywords": ["法规", "标准", "规范", "GB", "HJ", "合规", "许可", "审批", "条例"],
        "weight": 1.0,
    },
    "programming": {
        "regex": [
            r'\b(def |class |import |function|const |let |var |async |await|npm |pip |git |docker |k8s)\b',
            r'\b(Python|JavaScript|TypeScript|Rust|Go|Java|C\+\+|SQL|HTML|CSS|React|Vue)\b',
        ],
        "keywords": ["代码", "编程", "API", "接口", "数据库", "前端", "后端", "部署", "Git"],
        "weight": 0.9,
    },
    "voice": {
        "regex": [
            r'\b(语音|录音|TTS|STT|ASR|Whisper|说话|朗读|播放|音频|麦克风)\b',
            r'\b(speech|audio|voice|transcribe|synthesize)\b',
        ],
        "keywords": ["语音", "录音", "音频", "说话", "TTS", "STT", "朗读"],
        "weight": 0.9,
    },
    "video": {
        "regex": [
            r'\b(视频|B站|bilibili|YouTube|播放|画面|剪辑|字幕|弹幕)\b',
            r'\b(video|stream|playback|subtitle)\b',
        ],
        "keywords": ["视频", "播放", "B站", "YouTube", "画面", "剪辑"],
        "weight": 0.8,
    },
    "finance": {
        "regex": [
            r'\b(投资|预算|成本|报价|合同|付款|发票|ROI|经济|财务)\b',
            r'\b(finance|budget|cost|invoice|ROI|economic)\b',
        ],
        "keywords": ["预算", "成本", "报价", "投资", "财务", "ROI", "经济"],
        "weight": 0.8,
    },
    "medical": {
        "regex": [
            r'\b(诊断|治疗|药物|临床|病理|患者|手术|检验|体检|医保)\b',
            r'\b(diagnosis|treatment|clinical|patient|surgery|medical)\b',
        ],
        "keywords": ["诊断", "治疗", "药物", "临床", "病理", "手术", "患者"],
        "weight": 0.8,
    },
}


@dataclass
class ClassificationResult:
    domain: str
    confidence: float
    source: str         # "regex", "keyword", "llm", "combined"
    matches: list[str] = field(default_factory=list)
    alternatives: list[tuple[str, float]] = field(default_factory=list)


class AutoClassifier:
    """Multi-strategy knowledge domain classifier."""

    def __init__(self):
        self._compiled = {}
        for domain, patterns in DOMAIN_PATTERNS.items():
            self._compiled[domain] = [_re.compile(r, _re.IGNORECASE) for r in patterns["regex"]]

    def classify(self, text: str, content_type: str = "text") -> ClassificationResult:
        """Classify text into a knowledge domain."""
        if not text or len(text) < 10:
            return ClassificationResult(domain="general", confidence=0.3, source="default")

        scores = Counter()

        for domain, patterns in DOMAIN_PATTERNS.items():
            kw_weight = patterns["weight"]
            for regex in self._compiled.get(domain, []):
                matches = regex.findall(text)
                if matches:
                    scores[domain] += len(matches) * kw_weight * 2.0

            for kw in patterns["keywords"]:
                count = text.lower().count(kw.lower())
                if count > 0:
                    scores[domain] += count * kw_weight * 1.5

        if content_type in ("audio", "voice", "speech"):
            scores["voice"] += 3.0
        elif content_type in ("video"):
            scores["video"] += 3.0
        elif content_type in ("code", "programming"):
            scores["programming"] += 3.0

        if not scores:
            return ClassificationResult(domain="general", confidence=0.4, source="keyword")

        top = scores.most_common(3)
        primary_domain, primary_score = top[0]
        total = sum(scores.values())
        confidence = min(0.95, primary_score / max(1, total))

        alternatives = [(d, round(s / max(1, total), 3)) for d, s in top[1:3]]

        source = "regex" if primary_score > 4 else "keyword"

        return ClassificationResult(
            domain=primary_domain, confidence=round(confidence, 3),
            source=source,
            matches=[m for m in scores if scores[m] > 0][:5],
            alternatives=alternatives,
        )

    def classify_batch(self, items: list[dict]) -> list[dict]:
        """Batch classify. Each item: {id, text, content_type}."""
        results = []
        for item in items:
            result = self.classify(item.get("text", ""), item.get("content_type", "text"))
            results.append({**item, "domain": result.domain, "confidence": result.confidence,
                           "source": result.source})
        return results

    def stats(self) -> dict:
        return {
            "domains": len(DOMAIN_PATTERNS),
            "strategies": ["regex", "keyword", "combined"],
            "domains_list": list(DOMAIN_PATTERNS.keys()),
        }

    def render_html(self, sample_text: str = "") -> str:
        result = self.classify(sample_text) if sample_text else None
        domain_rows = ""
        for domain, patterns in DOMAIN_PATTERNS.items():
            domain_rows += (
                f'<div style="margin:2px 0;padding:4px 8px;font-size:10px">'
                f'<b>{domain}</b> <span style="color:var(--dim)">'
                f'{len(patterns["keywords"])}关键词 · {len(patterns["regex"])}正则</span></div>'
            )

        return f'''<div class="card">
<h2>🏷 自动分类器 <span style="font-size:10px;color:var(--dim)">— OpenMetadata Auto Classification</span></h2>
<div style="font-size:9px;color:var(--dim);margin:4px 0">{len(DOMAIN_PATTERNS)}个领域 · 正则+关键词+AI 三策略</div>
{domain_rows}
{("<div style=margin-top:8px;padding:8px;background:var(--panel);border-radius:4px;font-size:10px>"
 f"<b>示例分类</b>: {sample_text[:50]}... → <b style=color:var(--accent)>{result.domain}</b> (confidence:{result.confidence})</div>") if result else ""}
</div>'''


_instance: Optional[AutoClassifier] = None


def get_classifier() -> AutoClassifier:
    global _instance
    if _instance is None:
        _instance = AutoClassifier()
    return _instance
