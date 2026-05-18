"""Format Observer — LLM observes and reproduces formatting by pattern matching.

Core insight: LLM doesn't need to understand CSS/docx XML. It observes raw
formatted content, describes patterns in natural language, stores them in the
knowledge base, and reproduces them when generating similar content.

Universal: works for .docx, HTML, Markdown, PDF, .pptx — any formatted document.

Architecture:
  1. observe_format(filepath) → dump raw content as text
  2. LLM analyzes the text, describes style patterns in its own words
  3. LLM calls save_pattern(description) → stores in knowledge base
  4. LLM calls find_pattern(domain) → retrieves pattern for reproduction
  5. LLM applies the pattern when generating new content

This is not XML parsing. This is LLM observing and imitating — exactly how
humans learn design by looking at examples.
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

PATTERN_DB = Path(".livingtree/format_patterns.json")


# ═══ Core: observe raw content ═══

def observe_format(filepath: str) -> str:
    """Dump a formatted document as raw text for LLM observation.

    The LLM sees the structure and describes patterns in its own words.
    No hardcoded parsing — pure observation.
    """
    p = Path(filepath)
    if not p.exists():
        return f"File not found: {filepath}"

    suffix = p.suffix.lower()

    if suffix == ".docx":
        return _dump_docx(p)
    elif suffix == ".html" or suffix == ".htm":
        return _dump_html(p)
    elif suffix == ".md":
        return _dump_markdown(p)
    elif suffix == ".pptx":
        return _dump_pptx(p)
    elif suffix == ".pdf":
        return _dump_pdf(p)
    else:
        # Generic: just show raw content
        try:
            return p.read_text(encoding="utf-8", errors="replace")[:8000]
        except Exception:
            return f"Cannot read: {filepath}"


def _dump_docx(p: Path) -> str:
    """Dump docx as structured text with formatting markers."""
    import zipfile, xml.etree.ElementTree as ET
    NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    try:
        with zipfile.ZipFile(p) as z:
            doc_xml = z.read("word/document.xml") if "word/document.xml" in z.namelist() else b""
            styles_xml = z.read("word/styles.xml") if "word/styles.xml" in z.namelist() else b""

        lines = [f"=== Document: {p.name} ===", f"Raw size: {p.stat().st_size} bytes", ""]

        if doc_xml:
            root = ET.fromstring(doc_xml)
            lines.append("--- BODY ---")
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "p":
                    # Paragraph
                    ppr = elem.find(f"{NS}pPr")
                    style_info = ""
                    if ppr is not None:
                        pstyle = ppr.find(f"{NS}pStyle")
                        if pstyle is not None:
                            style_info = f' [style={pstyle.get(f"{NS}val","")}]'
                        jc = ppr.find(f"{NS}jc")
                        if jc is not None:
                            style_info += f' [align={jc.get(f"{NS}val","")}]'

                    texts = []
                    for t in elem.iter(f"{NS}t"):
                        if t.text:
                            texts.append(t.text)
                        # Bold/italic markers
                        rpr = None
                        for parent in elem.iter():
                            if parent.tag.endswith("}rPr"):
                                rpr = parent
                                break
                        if rpr is not None:
                            for b in rpr.iter(f"{NS}b"):
                                if texts:
                                    texts[-1] = f"**{texts[-1]}**"
                            for i in rpr.iter(f"{NS}i"):
                                if texts:
                                    texts[-1] = f"*{texts[-1]}*"

                    text = "".join(texts)
                    if text.strip():
                        lines.append(f"{style_info} {text.strip()[:200]}")

                elif tag == "tbl":
                    lines.append("[TABLE]")

        if styles_xml:
            root = ET.fromstring(styles_xml)
            lines.append("\n--- STYLES ---")
            for style in root.iter(f"{NS}style"):
                sid = style.get(f"{NS}styleId", "")
                sname = style.find(f"{NS}name")
                name = sname.get(f"{NS}val", "") if sname is not None else ""
                if sid or name:
                    # Font info
                    font_info = ""
                    for rpr in style.iter(f"{NS}rPr"):
                        for rf in rpr.iter(f"{NS}rFonts"):
                            f = rf.get(f"{NS}ascii", "") or rf.get(f"{NS}eastAsia", "")
                            if f:
                                font_info += f" font={f}"
                        for sz in rpr.iter(f"{NS}sz"):
                            val = sz.get(f"{NS}val", "")
                            if val:
                                font_info += f" size={int(val)//2}pt"
                    if font_info:
                        lines.append(f"  [{sid}] {name}:{font_info}")

        return "\n".join(lines[:200])
    except Exception as e:
        return f"docx dump error: {e}"


def _dump_html(p: Path) -> str:
    """Dump HTML showing tag structure and inline styles."""
    import re
    content = p.read_text(encoding="utf-8", errors="replace")[:15000]

    # Extract CSS
    styles = re.findall(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
    body = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
    body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL)

    # Show structure with class/id
    tags = re.findall(r'<(/?\w+)[^>]*class="([^"]*)"[^>]*>', body)
    ids = re.findall(r'<(/?\w+)[^>]*id="([^"]*)"[^>]*>', body)

    lines = [f"=== HTML: {p.name} ===", ""]
    if styles:
        lines.append(f"--- CSS ({len(styles)} blocks) ---")
        for s in styles[:5]:
            lines.append(s.strip()[:500])

    lines.append(f"\n--- Structure ({len(tags)} class tags, {len(ids)} id tags) ---")
    for tag, cls in tags[:30]:
        lines.append(f"  <{tag} class=\"{cls}\">")
    for tag, iid in ids[:10]:
        lines.append(f"  <{tag} id=\"{iid}\">")

    return "\n".join(lines[:150])


def _dump_markdown(p: Path) -> str:
    """Dump Markdown showing heading hierarchy and formatting."""
    import re
    content = p.read_text(encoding="utf-8", errors="replace")[:10000]

    lines = [f"=== Markdown: {p.name} ===", ""]
    headings = re.findall(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)
    if headings:
        lines.append("--- Heading Hierarchy ---")
        for level, title in headings[:20]:
            depth = len(level)
            indent = "  " * (depth - 1)
            lines.append(f"{indent}{'#'*depth} {title.strip()}")

    # Tables
    tables = re.findall(r'^\|.+\|$', content, re.MULTILINE)
    if tables:
        lines.append(f"\n--- Tables ({len(tables)} rows) ---")
        for t in tables[:10]:
            lines.append(t.strip()[:150])

    # Code blocks
    code_blocks = re.findall(r'```(\w*)\n(.*?)```', content, re.DOTALL)
    if code_blocks:
        lines.append(f"\n--- Code Blocks ({len(code_blocks)}) ---")
        for lang, _ in code_blocks[:5]:
            lines.append(f"  lang={lang or 'plain'}")

    return "\n".join(lines[:100])


def _dump_pptx(p: Path) -> str:
    """Dump PowerPoint showing slide structure."""
    import zipfile, xml.etree.ElementTree as ET
    try:
        with zipfile.ZipFile(p) as z:
            slides = [n for n in z.namelist() if n.startswith("ppt/slides/slide")]
            lines = [f"=== PPT: {p.name} === {len(slides)} slides", ""]
            for sn in slides[:15]:
                xml = z.read(sn)
                root = ET.fromstring(xml)
                texts = [t.text for t in root.iter() if t.tag.endswith("}t") and t.text]
                lines.append(f"\n--- {sn.split('/')[-1]} ---")
                for t in texts[:8]:
                    lines.append(f"  {t[:150]}")
            return "\n".join(lines[:150])
    except Exception as e:
        return f"pptx dump error: {e}"


def _dump_pdf(p: Path) -> str:
    """Dump PDF text content."""
    import fitz
    try:
        doc = fitz.open(p)
        lines = [f"=== PDF: {p.name} === {len(doc)} pages", ""]
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                lines.append(f"\n--- Page {i+1} ---")
                lines.append(text[:1000])
            if len(lines) > 100:
                break
        doc.close()
        return "\n".join(lines[:150])
    except Exception as e:
        return f"PDF dump error: {e}"


# ═══ Pattern storage (LLM-described) ═══

def save_pattern(json_spec: str) -> str:
    """Save an LLM-described formatting pattern to the knowledge base.

    The LLM describes what it observed in its own words and structured format.
    This is stored for future retrieval when generating similar documents.

    Expected JSON:
    {
      "domain": "环评报告",
      "source": "template.docx",
      "description": "正式公文风格，SimSun正文12pt，标题黑体加粗，1.5倍行距，A4页面...",
      "structure": {"headings": [...], "paragraph_style": {...}, "page": {...}},
      "tags": ["formal", "environment", "government"],
      "applies_to": ["docx", "pdf"],
      "prompt_hint": "使用正式的环评报告格式，SimSun字体..."
    }
    """
    try:
        data = json.loads(json_spec)
        patterns = _load_patterns()
        # Deduplicate by source
        patterns = [p for p in patterns if p.get("source") != data.get("source")]
        patterns.append(data)
        _save_patterns(patterns)
        domain = data.get("domain", "unknown")
        return f"Pattern saved: domain={domain} ({len(patterns)} total)"
    except Exception as e:
        return f"Save error: {e}"


def find_pattern(query: str) -> str:
    """Find matching patterns by domain or tags.

    Args: "eia" or "eia,formal" (domain + comma-separated tags)
    """
    parts = query.split(",")
    domain = parts[0].strip().lower()
    need_tags = [t.strip().lower() for t in parts[1:]] if len(parts) > 1 else []

    patterns = _load_patterns()
    if not patterns:
        return "No patterns stored. Use observe_format to look at examples, then save_pattern."

    # Match by domain
    candidates = [
        p for p in patterns
        if domain in p.get("domain", "").lower()
    ]
    if not candidates:
        # Fuzzy match on any field
        candidates = [
            p for p in patterns
            if domain in json.dumps(p).lower()
        ]

    # Filter by tags
    if need_tags and candidates:
        tagged = [
            p for p in candidates
            if all(
                any(t in tag.lower() for tag in p.get("tags", []))
                for t in need_tags
            )
        ]
        if tagged:
            candidates = tagged

    if not candidates:
        return f"No pattern found for '{query}'. Available domains: " + \
               ", ".join(set(p.get("domain","?") for p in patterns))

    return json.dumps(candidates[0], ensure_ascii=False, indent=2)


def list_patterns() -> str:
    """List all stored patterns."""
    patterns = _load_patterns()
    if not patterns:
        return "No patterns stored."
    items = [
        {"domain": p.get("domain", "?"), "source": p.get("source", "?"),
         "tags": p.get("tags", []), "applies_to": p.get("applies_to", [])}
        for p in patterns
    ]
    return json.dumps(items, ensure_ascii=False, indent=2)


def _load_patterns() -> list[dict]:
    if not PATTERN_DB.exists():
        return []
    try:
        return json.loads(PATTERN_DB.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_patterns(patterns: list[dict]):
    PATTERN_DB.parent.mkdir(parents=True, exist_ok=True)
    PATTERN_DB.write_text(json.dumps(patterns, ensure_ascii=False, indent=2), encoding="utf-8")


# ═══ Innovation 1: Style Diff — compare two templates ═══

def style_diff(file1: str, file2: str) -> str:
    """Dump both files and prompt LLM to describe formatting differences.

    Returns a prompt-ready diff description. LLM should call this,
    then describe what changed between the two templates.
    """
    dump1 = observe_format(file1)
    dump2 = observe_format(file2)
    return (
        f"=== Template A: {file1} ===\n{dump1[:4000]}\n\n"
        f"=== Template B: {file2} ===\n{dump2[:4000]}\n\n"
        f"[INSTRUCTION for LLM] Describe the formatting differences between these two templates. "
        f"Focus on: fonts, margins, colors, heading styles, spacing, alignment. "
        f"Output JSON: "
        '{"differences": [{"element":"...", "A":"...", "B":"..."}], '
        '"verdict": "A is better for X, B is better for Y"}'
    )


# ═══ Innovation 2: Style Merge — combine from multiple sources ═══

def style_merge(query: str) -> str:
    """Merge styles from multiple stored patterns.

    Args: comma-separated domains to merge, e.g. "eia,contract,letter"
    """
    domains = [d.strip() for d in query.split(",")]
    patterns = _load_patterns()
    merged = []

    for d in domains:
        for p in patterns:
            if d.lower() in p.get("domain", "").lower():
                merged.append(p)
                break

    if not merged:
        return f"No patterns found for: {domains}"

    result = {
        "sources": [p.get("source", "") for p in merged],
        "merged_hints": [p.get("prompt_hint", "") for p in merged],
        "merged_structure": {},
    }

    # Merge structures
    for p in merged:
        for key, val in p.get("structure", {}).items():
            if key not in result["merged_structure"]:
                result["merged_structure"][key] = val

    return json.dumps(result, ensure_ascii=False, indent=2)


# ═══ Innovation 3: Cross-format translation ═══

def style_translate(source: str) -> str:
    """Translate between formats. LLM provides the source format description.

    Args: JSON with {from_format, to_format, style_description}
    Example: {"from":"docx","to":"css","style":"SimSun 12pt, A4 margins 2.8cm"}
    """
    try:
        spec = json.loads(source)
        from_fmt = spec.get("from", "docx")
        to_fmt = spec.get("to", "css")
        description = spec.get("style", "")

        # Provide format-specific hints
        hints = {
            ("docx", "css"): (
                "Convert docx style to CSS. Font-size in pt → px (1pt≈1.33px). "
                "Margins in cm → CSS margin. Alignment: both→justify, center→center. "
                f"Style: {description}\n"
                "Output as CSS rules."
            ),
            ("docx", "md"): (
                "Convert docx style to Markdown theme hints. "
                f"Style: {description}\n"
                "Describe what the Markdown output should look like."
            ),
            ("docx", "latex"): (
                "Convert docx style to LaTeX preamble. "
                "SimSun → \\setCJKmainfont{SimSun}. A4 → a4paper. "
                f"Style: {description}\n"
                "Output LaTeX preamble code."
            ),
            ("html", "docx"): (
                "Convert CSS to docx style description. "
                f"CSS: {description}\n"
                "Describe equivalent docx formatting."
            ),
            ("css", "latex"): (
                "Convert CSS to LaTeX preamble. "
                f"CSS: {description}\n"
                "Output LaTeX preamble."
            ),
        }

        hint = hints.get((from_fmt, to_fmt), (
            f"Convert from {from_fmt} to {to_fmt} format. "
            "Style: {description}"
        ))

        return hint
    except Exception as e:
        return f"Translate error: {e}"


# ═══ Innovation 4: Style verification loop ═══

def style_verify(original: str, generated: str) -> str:
    """Compare original template with generated output. Prompt LLM to score and fix.

    Args: original file path, generated file path
    """
    orig_dump = observe_format(original)
    gen_dump = observe_format(generated)

    return (
        f"=== Original Template: {original} ===\n{orig_dump[:3000]}\n\n"
        f"=== Generated Output: {generated} ===\n{gen_dump[:3000]}\n\n"
        f"[INSTRUCTION for LLM] Compare the formatting of these two documents. "
        f"Score similarity 0-100. If below 80, list specific fixes needed. "
        f"Output JSON: "
        '{"score": 85, "issues": ["font size differs", "margin too small"], '
        '"fixes": ["change font to SimSun 12pt", "set margin to 2.8cm"]}'
    )


# ═══ Innovation 5: Few-shot style learning ═══

def style_learn_examples(good_files: str, bad_files: str) -> str:
    """Show LLM good and bad examples to learn what good formatting looks like.

    Args: "good1.docx,good2.docx" and "bad1.docx,bad2.docx" (comma-separated paths)
    """
    good_list = [f.strip() for f in good_files.split(",")]
    bad_list = [f.strip() for f in bad_files.split(",")]

    parts = ["=== Good Examples ==="]
    for f in good_list[:3]:
        parts.append(observe_format(f)[:2000])
    parts.append("\n=== Bad Examples ===")
    for f in bad_list[:3]:
        parts.append(observe_format(f)[:2000])

    parts.append(
        "\n[INSTRUCTION for LLM] These are GOOD and BAD document formatting examples. "
        "Learn what makes a document well-formatted. Summarize the principles. "
        "Output JSON: "
        '{"principles": ["use consistent fonts", "adequate margins", ...], '
        f'"anti_patterns": ["cramped margins", "inconsistent headings", ...], '
        '"scoring_rubric": {"font_consistency": 20, "margin_adequacy": 20, ...}}'
    )
    return "\n".join(parts)


# ═══ Innovation 6: Hierarchical style inheritance ═══

def style_inherit_chain(base_pattern: str, overrides_json: str) -> str:
    """Create a hierarchical style chain. Child inherits from parent, with overrides.

    Args:
      base_pattern: domain name of the parent style
      overrides_json: JSON with fields to override
    """
    patterns = _load_patterns()
    base = None
    for p in patterns:
        if base_pattern.lower() in p.get("domain", "").lower():
            base = p
            break

    if not base:
        return f"Base pattern '{base_pattern}' not found. Available: " + \
               ", ".join(p.get("domain","?") for p in patterns)

    try:
        overrides = json.loads(overrides_json)
    except Exception:
        overrides = {}

    inherited = dict(base)  # Shallow copy
    inherited["inherits_from"] = base.get("domain", "")
    inherited["domain"] = overrides.get("domain", base.get("domain", "") + "_child")

    # Apply overrides
    if "structure" in overrides and "structure" in inherited:
        inherited["structure"] = {**inherited["structure"], **overrides["structure"]}
    for key in ("tags", "description", "prompt_hint", "applies_to"):
        if key in overrides:
            inherited[key] = overrides[key]

    return json.dumps(inherited, ensure_ascii=False, indent=2)


# ═══ Innovation 7: Vector storage for semantic style search ═══

def style_index_all() -> str:
    """Index all stored patterns into vector DB for semantic search."""
    patterns = _load_patterns()
    if not patterns:
        return "No patterns to index."

    try:
        from ..knowledge.vector_store import VectorStore
        store = VectorStore()
        for i, p in enumerate(patterns):
            text = json.dumps(p, ensure_ascii=False)
            embedding = store.embed(text[:2000])
            store.add_vectors([(f"style:{i}", embedding)])
        return f"Indexed {len(patterns)} patterns into vector store"
    except Exception as e:
        # Fallback: just save as JSON
        return f"Vector store unavailable, patterns in JSON: {PATTERN_DB}"


def style_search_semantic(query: str, top_k: int = 5) -> str:
    """Semantic search for styles matching a natural language description.

    Args: "正式学术论文格式" or "corporate report with blue headings"
    """
    patterns = _load_patterns()
    if not patterns:
        return "No patterns stored."

    try:
        from ..knowledge.vector_store import VectorStore
        store = VectorStore()
        q_vec = store.embed(query)
        results = store.search_similar(q_vec, top_k=min(top_k, len(patterns)))
        if results:
            items = []
            for doc_id in results:
                idx = int(doc_id.split(":")[-1]) if ":" in doc_id else 0
                if idx < len(patterns):
                    p = patterns[idx]
                    items.append({
                        "domain": p.get("domain", "?"),
                        "description": p.get("description", "")[:100],
                        "tags": p.get("tags", []),
                    })
            return json.dumps(items, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # Fallback: keyword search on descriptions
    results = []
    for p in patterns:
        desc = p.get("description", "") + " " + " ".join(p.get("tags", []))
        if any(kw in desc.lower() for kw in query.lower().split()):
            results.append(p)
    items = [
        {"domain": p.get("domain", "?"), "description": p.get("description", "")[:100],
         "tags": p.get("tags", [])}
        for p in results[:top_k]
    ]
    return json.dumps(items, ensure_ascii=False, indent=2) if items else "No matching styles found."


# ═══ Batch observation: learn common style from multiple examples ═══

def observe_batch(files_json: str) -> str:
    """Observe multiple documents and extract COMMON patterns.

    Token strategy:
      - First pass: 2000 chars each (for ~6000 tokens, $0.012)
      - If LLM signals "not enough", second pass: 4000 chars each
      - Styles section only (not full body content) for large docs

    Performance:
      12 docs × 2000 chars ≈ 6000 input tokens + 1000 output ≈ $0.014
      One-time cost. Subsequent generations use saved pattern — zero token cost.
    """
    try:
        files = json.loads(files_json)
    except Exception:
        return f"Invalid JSON: {files_json}"

    if not files or len(files) < 2:
        return "Need at least 2 files for batch observation."

    parts = [f"=== Batch Observation: {len(files)} documents ===", ""]
    total_chars = 0

    for i, f in enumerate(files):
        dump = observe_format(f.strip())
        # Styles-only mode: take first 1500 chars + styles section, skip body content
        if len(dump) > 3000:
            # Keep header + styles, truncate body
            body_start = dump.find("--- BODY ---")
            styles_start = dump.find("--- STYLES ---")
            if styles_start > 0:
                dump = dump[:min(body_start + 500, 1500)] + "\n...\n" + dump[styles_start:styles_start + 2000]
            else:
                dump = dump[:2000]
        dump = dump[:2000]  # Hard cap per doc
        total_chars += len(dump)
        parts.append(f"--- Document {i+1}: {f} ---")
        parts.append(dump)
        parts.append("")

    est_tokens = total_chars // 4
    est_cost = f"${est_tokens * 0.002 / 1000:.4f} (DeepSeek)" if est_tokens < 100000 else "⚠️ Consider using fewer documents"

    parts.append(
        f"\n[Token estimate: ~{est_tokens} input tokens, est cost: {est_cost}]"
    )

    parts.append(
        f"\n[INSTRUCTION for LLM] You have observed {len(files)} documents "
        f"that should share a common formatting style.\n\n"
        f"1. Identify what is CONSISTENT across ALL documents (fonts, margins, "
        f"heading styles, spacing, alignment, colors, page setup, headers/footers). "
        f"These are the STYLE DNA — they should be reproduced exactly.\n\n"
        f"2. Identify what VARIES across documents (content, data, specific numbers, "
        f"names, dates, chapter titles). These are CONTENT — they should NOT be copied.\n\n"
        f"3. For each style property, note how many documents use it "
        f"(e.g. 'SimSun 12pt in 12/12 docs' vs 'SimSun 14pt in 1/12 docs'). "
        f"The majority pattern IS the style.\n\n"
        f"4. If there are minor inconsistencies (e.g. 11 docs use 2.8cm left margin, "
        f"1 doc uses 3.0cm), the majority wins. Flag the outlier.\n\n"
        f"Output JSON:\n"
        '{\n'
        '  "style_dna": {\n'
        '    "fonts": {"body": {"name":"SimSun","size":12,"confidence":"12/12"}},\n'
        '    "margins": {"top":3.7,"bottom":3.5,"left":2.8,"right":2.6,"confidence":"12/12"},\n'
        '    "headings": {"h1":{"font":"SimHei","size":16,"bold":true,"confidence":"12/12"}},\n'
        '    "spacing": {"line":1.5,"confidence":"11/12"},\n'
        '    "page": {"size":"A4","confidence":"12/12"}\n'
        '  },\n'
        '  "outliers": [{"doc":3,"property":"left_margin","value":3.0,"expected":2.8}],\n'
        '  "description": "正式环评报告格式，SimSun正文12pt，SimHei标题16pt...",\n'
        '  "template_prompt": "使用环评报告格式生成。正文SimSun 12pt，1.5倍行距..."\n'
        '}'
    )

    return "\n".join(parts)


def diff_to_baseline(files_json: str, baseline_file: str) -> str:
    """Compare each document to a baseline reference.

    Given 12 reports and 1 "golden" template, show what deviates.
    Useful when you have one perfect template and 11 variants.
    """
    try:
        files = json.loads(files_json)
    except Exception:
        return f"Invalid JSON: {files_json}"

    if not files:
        return "No files provided."

    baseline_dump = observe_format(baseline_file.strip())
    parts = [f"=== Baseline: {baseline_file} ===", baseline_dump[:3000], ""]

    parts.append(f"=== Variants: {len(files)} documents ===")
    for i, f in enumerate(files):
        dump = observe_format(f.strip())
        parts.append(f"\n--- Variant {i+1}: {f} ---")
        parts.append(dump[:1000])

    parts.append(
        "\n[INSTRUCTION for LLM] The baseline is the correct/desired format. "
        "For each variant, identify where it DEVIATES from the baseline. "
        "Output JSON: "
        '[{"file":"variant1.docx","deviations":["font size 14pt vs baseline 12pt", '
        '"left margin 3.0cm vs baseline 2.8cm"]}]'
    )

    return "\n".join(parts)


def normalize_to_style(files_json: str) -> str:
    """Extract common style and output a normalization spec.

    Same as observe_batch but optimized: only dumps styles section, not body.
    Target: <3000 tokens for 12 docs.
    """
    try:
        files = json.loads(files_json)
    except Exception:
        return f"Invalid JSON: {files_json}"

    parts = [f"=== Normalize from {len(files)} documents (styles only) ===", ""]
    total_chars = 0
    for i, f in enumerate(files):
        dump = observe_format(f.strip())
        # Styles-only: skip body text, keep only formatting info
        styles_start = dump.find("--- STYLES ---")
        body_start = dump.find("--- BODY ---")
        if styles_start > 0:
            dump = dump[:min(body_start + 300, 800)] + "\n" + dump[styles_start:styles_start + 1500]
        dump = dump[:1200]
        total_chars += len(dump)
        parts.append(f"--- Doc {i+1}: {f} ---")
        parts.append(dump)
        parts.append("")

    est_tokens = total_chars // 4

    parts.append(
        "\n[INSTRUCTION for LLM] Extract the common formatting style from these "
        "documents and output a format_docx JSON spec. This spec will be used to "
        "generate new documents with the SAME style but NEW content.\n\n"
        "Output a complete JSON object compatible with format_docx tool. "
        "Include: page, margins, header, footer, default_paragraph style, heading styles. "
        "Omit: sections/content — those will be filled with new content.\n"
        "Output ONLY the JSON — no commentary."
    )

    return "\n".join(parts)


# ═══ Update TOOLS ═══

TOOLS = {
    "observe_format": {"func": observe_format, "desc": "Dump formatted doc as raw text for LLM observation.", "params": "filepath"},
    "observe_batch": {"func": observe_batch, "desc": "Observe multiple docs, extract COMMON style patterns (what's consistent vs varies).", "params": "json_array_of_paths"},
    "diff_to_baseline": {"func": diff_to_baseline, "desc": "Compare documents to a golden baseline, find deviations.", "params": "json_array, baseline_file"},
    "normalize_to_style": {"func": normalize_to_style, "desc": "From multiple docs, produce a format_docx spec for new docs with same style.", "params": "json_array_of_paths"},
    "save_pattern": {"func": save_pattern, "desc": "Save LLM-described formatting pattern to KB.", "params": "json_spec"},
    "find_pattern": {"func": find_pattern, "desc": "Find formatting pattern by domain.", "params": "domain[,tags]"},
    "list_patterns": {"func": list_patterns, "desc": "List all stored formatting patterns.", "params": ""},
    "style_diff": {"func": style_diff, "desc": "Compare two templates, prompt LLM to describe differences.", "params": "file1, file2"},
    "style_merge": {"func": style_merge, "desc": "Merge styles from multiple domains.", "params": "domain1,domain2,..."},
    "style_translate": {"func": style_translate, "desc": "Translate between formats (docx↔css↔md↔latex).", "params": "json_spec"},
    "style_verify": {"func": style_verify, "desc": "Compare original vs generated, score similarity.", "params": "original, generated"},
    "style_learn": {"func": style_learn_examples, "desc": "Learn formatting from good vs bad examples.", "params": "good_files, bad_files"},
    "style_inherit": {"func": style_inherit_chain, "desc": "Create hierarchical style chain.", "params": "base_pattern, overrides_json"},
    "style_index": {"func": style_index_all, "desc": "Index all patterns into vector DB.", "params": ""},
    "style_search": {"func": style_search_semantic, "desc": "Semantic search for styles by description.", "params": "query"},
}
