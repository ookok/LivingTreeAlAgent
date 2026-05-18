"""ToolExecutor — real backend implementations for shell/git/web/db/data/notify/visual tools.

Each tool registered here has an actual handler function. Tools are invoked
by the LLM generating a tool_call, which then triggers this executor.

18 tools total:
  web: url_fetch, api_call, web_scrape
  database: db_query, db_schema
  git: git_diff, git_log, git_blame
  shell: run_command, run_script
  notify: send_email, send_notification
  multimedia: pdf_parse, ocr_extract
  data: csv_analyze, json_transform, excel_export
  visual: visual_render
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

import jmespath
import pytesseract
from PIL import Image
from pypdf import PdfReader
from ..treellm.unified_exec import run_sync, check_output_sync  # SUBPROCESS MIGRATION


@dataclass
class ToolResult:
    tool: str
    success: bool = True
    output: str = ""
    error: str = ""
    data: Any = None
    elapsed_ms: float = 0.0


class ToolExecutor:
    """Real tool execution engine. Each method returns ToolResult."""

    # ═══ Web tools ═══

    async def url_fetch(self, url: str, format: str = "markdown") -> ToolResult:
        """Fetch a URL. Auto-detects proxy from pool + mirrors."""
        t0 = time.monotonic()
        try:
            import urllib.request
            url = url if url.startswith("http") else "https://" + url

            # ── Auto proxy + mirror ──
            proxied_url = url
            proxy_url = self._get_auto_proxy()
            if proxy_url:
                logger.debug(f"Proxy: {proxy_url[:30]}... for {url[:50]}")

            result_text = ""
            # Try with proxy first, fallback to direct + mirrors
            for attempt_url in self._get_failover_urls(url):
                try:
                    req = urllib.request.Request(attempt_url, headers={"User-Agent": "LivingTree/2.1"})
                    if proxy_url:
                        req.set_proxy(proxy_url, "http")
                        req.set_proxy(proxy_url, "https")
                    with urllib.request.urlopen(req, timeout=12) as resp:
                        raw = resp.read().decode("utf-8", errors="replace")
                        result_text = raw
                        break
                except Exception:
                    continue

            if not result_text:
                return ToolResult("url_fetch", False, error="All failover URLs failed", elapsed_ms=(time.monotonic()-t0)*1000)

            if format in ("text", "html"):
                return ToolResult("url_fetch", True, result_text[:50000], elapsed_ms=(time.monotonic()-t0)*1000)
            # Structured extraction
            parts = []
            for m in re.finditer(r'<table[^>]*>(.*?)</table>', result_text, re.DOTALL|re.IGNORECASE):
                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', m.group(1), re.DOTALL|re.IGNORECASE)
                tbl = []
                for row in rows[:30]:
                    cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL|re.IGNORECASE)
                    tbl.append("| " + " | ".join(re.sub(r'<[^>]+>', '', c).strip()[:80] for c in cells) + " |")
                if tbl:
                    parts.append("[TABLE]\n" + "\n".join(tbl) + "\n[/TABLE]")
            for m in re.finditer(r'<h[1-3][^>]*>(.*?)</h[1-3]>', result_text, re.IGNORECASE):
                parts.append("## " + re.sub(r'<[^>]+>', '', m.group(1)).strip())
            for m in re.finditer(r'<(ul|ol)[^>]*>(.*?)</\1>', result_text, re.DOTALL|re.IGNORECASE):
                items = re.findall(r'<li[^>]*>(.*?)</li>', m.group(2), re.DOTALL|re.IGNORECASE)
                parts.append("\n".join(f"- {re.sub(r'<[^>]+>', '', i).strip()}" for i in items[:20]))
            if not parts:
                clean = re.sub(r'<script[^>]*>.*?</script>', '', result_text, flags=re.DOTALL|re.IGNORECASE)
                clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL|re.IGNORECASE)
                clean = re.sub(r'<[^>]+>', '', clean)
                clean = re.sub(r'\n{3,}', '\n\n', clean)
                parts.append(clean[:10000])
            return ToolResult("url_fetch", True, "\n\n".join(parts)[:30000], elapsed_ms=(time.monotonic()-t0)*1000)
        except Exception as e:
            return ToolResult("url_fetch", False, error=str(e), elapsed_ms=(time.monotonic()-t0)*1000)

    @staticmethod
    def _get_auto_proxy() -> str:
        """Auto-detect proxy from pool or env."""
        try:
            from ..network.proxy_fetcher import get_proxy_pool
            pool = get_proxy_pool()
            p = pool.get_best()
            if p and p.failure_count < 5:
                return p.url
        except Exception:
            pass
        return ""

    @staticmethod
    def _get_failover_urls(url: str) -> list[str]:
        """Generate failover URL chain: original + mirrors."""
        urls = [url]
        if "github.com" in url or "raw.githubusercontent.com" in url:
            urls.append(url.replace("https://github.com", "https://ghproxy.com/https://github.com", 1)
                         .replace("https://raw.githubusercontent.com", "https://ghproxy.com/https://raw.githubusercontent.com", 1))
            urls.append(url.replace("https://github.com", "https://mirror.ghproxy.com/https://github.com", 1))
        return urls

    async def api_call(self, url: str, method: str = "GET", headers: str = "{}", body: str = "") -> ToolResult:
        """Call an external API."""
        t0 = time.monotonic()
        try:
            import urllib.request
            hdrs = json.loads(headers) if headers else {}
            hdrs["User-Agent"] = "LivingTree/2.1"
            data = body.encode() if body else None
            req = urllib.request.Request(url, data=data, headers=hdrs, method=method.upper())
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = resp.read().decode("utf-8", errors="replace")
            return ToolResult("api_call", True, result[:50000], elapsed_ms=(time.monotonic()-t0)*1000)
        except Exception as e:
            return ToolResult("api_call", False, error=str(e), elapsed_ms=(time.monotonic()-t0)*1000)

    # ═══ Database tools ═══

    def db_query(self, sql: str, db_path: str = ":memory:") -> ToolResult:
        """Execute SQL query."""
        t0 = time.monotonic()
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(sql)
            if sql.strip().upper().startswith("SELECT"):
                rows = cursor.fetchall()
                cols = [d[0] for d in cursor.description] if cursor.description else []
                # Format as markdown table
                output = "| " + " | ".join(cols) + " |\n| " + " | ".join("---" for _ in cols) + " |\n"
                for row in rows[:50]:
                    output += "| " + " | ".join(str(v)[:100] for v in row) + " |\n"
                output += f"\n{len(rows)} rows"
            else:
                conn.commit()
                output = f"OK ({cursor.rowcount} rows affected)"
            conn.close()
            return ToolResult("db_query", True, output, elapsed_ms=(time.monotonic()-t0)*1000)
        except Exception as e:
            return ToolResult("db_query", False, error=str(e), elapsed_ms=(time.monotonic()-t0)*1000)

    def db_schema(self, db_path: str, table: str = "") -> ToolResult:
        """Read database schema."""
        t0 = time.monotonic()
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            if table:
                cursor.execute(f"SELECT sql FROM sqlite_master WHERE name=?", (table,))
                result = cursor.fetchall()
                output = "\n".join(str(r[0]) for r in result if r[0])
            else:
                cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','index','view','trigger')")
                rows = cursor.fetchall()
                output = "| Name | Type |\n| --- | --- |\n"
                for name, ttype in rows:
                    output += f"| {name} | {ttype} |\n"
                output += f"\n{len(rows)} objects\n\n"
                # Add CREATE statements
                cursor.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")
                for (sql,) in cursor.fetchall()[:20]:
                    output += f"\n```sql\n{sql}\n```\n"
            conn.close()
            return ToolResult("db_schema", True, output[:30000], elapsed_ms=(time.monotonic()-t0)*1000)
        except Exception as e:
            return ToolResult("db_schema", False, error=str(e), elapsed_ms=(time.monotonic()-t0)*1000)

    # ═══ Git tools ═══

    def _run_git(self, *args: str, cwd: str = ".") -> tuple[str, str, int]:
        try:
            p = subprocess.run(["git"] + list(args), capture_output=True, text=True,
                               cwd=cwd, timeout=15, encoding="utf-8", errors="replace")
            return p.stdout, p.stderr, p.returncode
        except Exception as e:
            return "", str(e), 1

    def git_diff(self, path: str = "", staged: bool = False) -> ToolResult:
        """Show git diff."""
        t0 = time.monotonic()
        args = ["diff"]
        if staged:
            args.append("--staged")
        if path:
            args.append("--")
            args.append(path)
        stdout, stderr, rc = self._run_git(*args)
        output = stdout[:50000] if stdout else stderr[:5000]
        return ToolResult("git_diff", rc == 0, output, error=stderr if rc else "", elapsed_ms=(time.monotonic()-t0)*1000)

    def git_log(self, n: int = 10, path: str = "") -> ToolResult:
        """Show git log."""
        t0 = time.monotonic()
        args = ["log", f"-{n}", "--oneline", "--decorate", "--graph"]
        if path:
            args.extend(["--", path])
        stdout, stderr, rc = self._run_git(*args)
        output = stdout[:30000] if stdout else stderr[:5000]
        return ToolResult("git_log", rc == 0, output, error=stderr if rc else "", elapsed_ms=(time.monotonic()-t0)*1000)

    def git_blame(self, path: str, start_line: int = 0, end_line: int = 0) -> ToolResult:
        """Show git blame for a file."""
        t0 = time.monotonic()
        if not path:
            return ToolResult("git_blame", False, error="path required")
        args = ["blame", "--date=short", path]
        if start_line > 0:
            range_str = f"{start_line}" + (f",{end_line}" if end_line > start_line else "")
            args = ["blame", "--date=short", "-L", range_str, path]
        stdout, stderr, rc = self._run_git(*args)
        output = stdout[:50000] if stdout else stderr[:5000]
        return ToolResult("git_blame", rc == 0, output, error=stderr if rc else "", elapsed_ms=(time.monotonic()-t0)*1000)

    # ═══ Shell tools ═══

    async def run_command(self, command: str, workdir: str = ".", timeout: int = 30) -> ToolResult:
        """Execute a shell command via unified ShellExecutor (safety + cross-platform)."""
        t0 = time.monotonic()
        from ..core.shell_env import get_shell
        shell_exec = get_shell()
        result = await shell_exec.execute(command, timeout=timeout, cwd=workdir)
        return ToolResult("run_command", result.exit_code == 0,
                        result.stdout + ("\n\n[stderr]\n" + result.stderr if result.stderr else ""),
                        error=result.stderr if result.exit_code else "",
                        elapsed_ms=(time.monotonic()-t0)*1000)

    # ═══ Notification tools ═══

    async def send_email(self, to: str, subject: str, body: str, attachments: str = "") -> ToolResult:
        """Send email via SMTP."""
        t0 = time.monotonic()
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            smtp_host = os.environ.get("SMTP_HOST", "smtp.qq.com")
            smtp_port = int(os.environ.get("SMTP_PORT", "587"))
            smtp_user = os.environ.get("SMTP_USER", "")
            smtp_pass = os.environ.get("SMTP_PASS", "")

            if not smtp_user:
                return ToolResult("send_email", False, error="SMTP credentials not configured (set SMTP_USER/PASS env vars)")

            msg = MIMEMultipart()
            msg["From"] = smtp_user
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "html" if body.strip().startswith("<") else "plain", "utf-8"))

            # Run SMTP in thread (blocking)
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._smtp_send(smtp_host, smtp_port, smtp_user, smtp_pass, to, msg.as_string())
            )
            return ToolResult("send_email", True, f"Email sent to {to}", elapsed_ms=(time.monotonic()-t0)*1000)
        except Exception as e:
            return ToolResult("send_email", False, error=str(e), elapsed_ms=(time.monotonic()-t0)*1000)

    def _smtp_send(self, host, port, user, passwd, to, msg_str):
        import smtplib
        s = smtplib.SMTP(host, port, timeout=15)
        s.starttls()
        s.login(user, passwd)
        s.sendmail(user, [to], msg_str)
        s.quit()

    # ═══ Notification tools ═══

    def pdf_parse(self, path: str, pages: str = "") -> ToolResult:
        """Parse PDF content."""
        t0 = time.monotonic()
        try:
            # Try pypdf first
            reader = PdfReader(path)
            page_nums = self._parse_page_range(pages, len(reader.pages))
            texts = []
            for i in page_nums:
                texts.append(reader.pages[i].extract_text() or f"[Page {i+1}: no text]")
            return ToolResult("pdf_parse", True, "\n\n--- Page ---\n\n".join(texts[:10]),
                            elapsed_ms=(time.monotonic()-t0)*1000)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(100000)
            return ToolResult("pdf_parse", True, content, elapsed_ms=(time.monotonic()-t0)*1000)
        except Exception as e:
            return ToolResult("pdf_parse", False, error=str(e), elapsed_ms=(time.monotonic()-t0)*1000)

    def ocr_extract(self, path: str, language: str = "chi_sim") -> ToolResult:
        """OCR image to text."""
        t0 = time.monotonic()
        try:
            img = Image.open(path)
            text = pytesseract.image_to_string(img, lang=language)
            return ToolResult("ocr_extract", True, text[:50000], elapsed_ms=(time.monotonic()-t0)*1000)
        except Exception as e:
            return ToolResult("ocr_extract", False, error=str(e), elapsed_ms=(time.monotonic()-t0)*1000)

    # ═══ Data tools ═══

    def csv_analyze(self, path: str, columns: str = "") -> ToolResult:
        """Analyze CSV file."""
        t0 = time.monotonic()
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            if not rows:
                return ToolResult("csv_analyze", False, error="Empty CSV")

            headers = list(rows[0].keys())
            output = [f"## CSV分析: {path}", f"行数: {len(rows)}", f"列数: {len(headers)}", ""]
            output.append("### 列信息")
            for h in headers:
                values = [r[h] for r in rows if r.get(h)]
                try:
                    nums = [float(v) for v in values if v.strip()]
                    if nums:
                        output.append(f"- **{h}** (数值): min={min(nums):.2f}, max={max(nums):.2f}, avg={sum(nums)/len(nums):.2f}, null={len(rows)-len(values)}")
                    else:
                        uniq = len(set(values[:100]))
                        output.append(f"- **{h}** (文本): 样本={str(values[:3])[:100]}, 唯一值≈{uniq}, null={len(rows)-len(values)}")
                except ValueError:
                    output.append(f"- **{h}** (文本): 样本={str(values[:3])[:100]}")
            return ToolResult("csv_analyze", True, "\n".join(output), data={"headers": headers, "row_count": len(rows)},
                            elapsed_ms=(time.monotonic()-t0)*1000)
        except Exception as e:
            return ToolResult("csv_analyze", False, error=str(e), elapsed_ms=(time.monotonic()-t0)*1000)

    def json_transform(self, input_data: str, expression: str = "") -> ToolResult:
        """Transform JSON data."""
        t0 = time.monotonic()
        try:
            data = json.loads(input_data)
            if not expression:
                return ToolResult("json_transform", True, json.dumps(data, indent=2, ensure_ascii=False)[:50000],
                                elapsed_ms=(time.monotonic()-t0)*1000)
            # Simple transform: dot.separated.path extraction or key filter
            if "." in expression:
                parts = expression.split(".")
                for p in parts:
                    if isinstance(data, dict):
                        data = data.get(p)
                    elif isinstance(data, list) and p.isdigit():
                        data = data[int(p)]
                return ToolResult("json_transform", True, json.dumps(data, indent=2, ensure_ascii=False)[:50000],
                                elapsed_ms=(time.monotonic()-t0)*1000)
            elif expression in data:
                return ToolResult("json_transform", True, json.dumps(data[expression], indent=2, ensure_ascii=False)[:50000],
                                elapsed_ms=(time.monotonic()-t0)*1000)
            else:
                # Try JMESPath
                data = jmespath.search(expression, data)
                return ToolResult("json_transform", True, json.dumps(data, indent=2, ensure_ascii=False)[:50000],
                                elapsed_ms=(time.monotonic()-t0)*1000)
        except json.JSONDecodeError as e:
            return ToolResult("json_transform", False, error=f"Invalid JSON: {e}", elapsed_ms=(time.monotonic()-t0)*1000)

    def excel_export(self, data: str, path: str = "", format: str = "xlsx") -> ToolResult:
        """Export data to Excel/CSV."""
        t0 = time.monotonic()
        out_path = Path(path) if path else Path(f".livingtree/exports/export_{int(time.time())}.{format}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            parsed = json.loads(data)
            if format == "csv":
                if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                    headers = list(parsed[0].keys())
                    with open(out_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=headers)
                        writer.writeheader()
                        writer.writerows(parsed)
            else:
                # Write as JSON (openpyxl fallback)
                import json as _j
                out_path = out_path.with_suffix(".json")
                out_path.write_text(_j.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
            return ToolResult("excel_export", True, str(out_path), elapsed_ms=(time.monotonic()-t0)*1000)
        except Exception as e:
            # Write raw data
            out_path.write_text(data, encoding="utf-8")
            return ToolResult("excel_export", True, str(out_path), elapsed_ms=(time.monotonic()-t0)*1000)

    # ═══ File edit tools ═══

    async def edit_file(self, path: str, old_str: str, new_str: str) -> ToolResult:
        t0 = time.monotonic()
        try:
            p = Path(path)
            if not p.exists():
                return ToolResult("edit_file", False, error=f"File not found: {path}")
            content = p.read_text(encoding="utf-8")
            count = content.count(old_str)
            if count == 0:
                return ToolResult("edit_file", False, error="old_str not found in file")
            if count > 1:
                return ToolResult("edit_file", False, error=f"Found {count} matches — need unique old_str")
            new_content = content.replace(old_str, new_str)
            tmp = p.with_suffix(p.suffix + ".tmp")
            tmp.write_text(new_content, encoding="utf-8")
            os.replace(str(tmp), str(p))
            return ToolResult("edit_file", True,
                            output=f"Replaced in {path} ({len(content)}→{len(new_content)} chars)",
                            elapsed_ms=(time.monotonic()-t0)*1000)
        except Exception as e:
            return ToolResult("edit_file", False, error=str(e), elapsed_ms=(time.monotonic()-t0)*1000)

    async def delete_file(self, path: str) -> ToolResult:
        t0 = time.monotonic()
        try:
            p = Path(path)
            if not p.exists():
                return ToolResult("delete_file", False, error=f"Not found: {path}")
            if p.is_dir():
                import shutil
                shutil.rmtree(p)
                return ToolResult("delete_file", True, output=f"Deleted dir: {path}",
                                elapsed_ms=(time.monotonic()-t0)*1000)
            p.unlink()
            return ToolResult("delete_file", True, output=f"Deleted: {path}",
                            elapsed_ms=(time.monotonic()-t0)*1000)
        except Exception as e:
            return ToolResult("delete_file", False, error=str(e), elapsed_ms=(time.monotonic()-t0)*1000)

    async def create_dir(self, path: str) -> ToolResult:
        t0 = time.monotonic()
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return ToolResult("create_dir", True, output=f"Created: {path}",
                            elapsed_ms=(time.monotonic()-t0)*1000)
        except Exception as e:
            return ToolResult("create_dir", False, error=str(e), elapsed_ms=(time.monotonic()-t0)*1000)

    async def glob_files(self, pattern: str, directory: str = ".") -> ToolResult:
        t0 = time.monotonic()
        try:
            files = sorted(Path(directory).glob(pattern))[:200]
            return ToolResult("glob_files", True,
                            output="\n".join(str(f) for f in files),
                            elapsed_ms=(time.monotonic()-t0)*1000)
        except Exception as e:
            return ToolResult("glob_files", False, error=str(e), elapsed_ms=(time.monotonic()-t0)*1000)

    # ═══ Helpers ═══

    # ── Visual tools ──

    async def visual_render(self, data: Any, type_hint: str = "auto",
                            save_path: str = "") -> ToolResult:
        """Unified visual rendering via UnifiedVisualPort (Vision Banana style).

        Args:
            data: Input data — dict with type info, file path, or raw data
            type_hint: plot | map | document | table | image | diagram | auto
            save_path: Optional save path for generated image
        """
        t0 = time.monotonic()
        try:
            from .unified_visual_port import get_visual_port
            port = get_visual_port()
            output = port.render(data, type_hint)

            response_parts = []
            if output.has_text():
                response_parts.append(output.text)
            if output.has_image():
                response_parts.append(f"\n[图像: {output.width}x{output.height} PNG, "
                                      f"{len(output.image_bytes)} bytes]")
                if save_path:
                    saved = output.save_image(save_path)
                    response_parts.append(f"[已保存: {saved}]")
                else:
                    data_uri = output.image_data_uri()
                    response_parts.append(f"[Data URI: {data_uri[:80]}...]")

            result_text = "\n".join(response_parts)
            return ToolResult(
                "visual_render", success=True, output=result_text,
                data={
                    "text": output.text[:1000],
                    "has_image": output.has_image(),
                    "image_format": output.image_format,
                    "width": output.width,
                    "height": output.height,
                    "source_type": output.source_type,
                    "image_base64": output.image_base64() if output.has_image() else "",
                },
                elapsed_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            logger.warning(f"visual_render: {e}")
            return ToolResult("visual_render", False, error=str(e),
                              elapsed_ms=(time.monotonic() - t0) * 1000)

    # ═══ Helpers ═══

    @staticmethod
    def _quote(cmd: str) -> str:
        if '"' not in cmd:
            return f'"{cmd}"'
        if "'" not in cmd:
            return f"'{cmd}'"
        return cmd

    @staticmethod
    def _kill_on_timeout(command: str) -> None:
        try:
            import subprocess
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/F", "/IM", "cmd.exe"], capture_output=True, timeout=5)
            else:
                subprocess.run(["pkill", "-P", str(os.getpid())], capture_output=True, timeout=5)
        except Exception:
            pass

    def _strip_table(self, html: str) -> str:
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL|re.IGNORECASE)
        output = []
        for row in rows[:30]:
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL|re.IGNORECASE)
            output.append("| " + " | ".join(re.sub(r'<[^>]+>', '', c).strip()[:80] for c in cells) + " |")
        return "\n".join(output[:30])

    def _parse_page_range(self, pages: str, total: int) -> list[int]:
        if not pages:
            return list(range(min(10, total)))
        result = []
        for part in pages.split(","):
            if "-" in part:
                a, b = part.split("-", 1)
                result.extend(range(int(a)-1, min(int(b), total)))
            else:
                result.append(int(part)-1)
        return [i for i in result if 0 <= i < total]


_executor: ToolExecutor | None = None

def get_executor() -> ToolExecutor:
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor
