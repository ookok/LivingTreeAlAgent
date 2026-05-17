"""Office API connectors — Google Docs, MS365 Graph, WPS, LaTeX, PPT generation.

Tools exposed to LLM:
  gdocs_create(title, content) → Google Docs document
  ms365_send_email(to, subject, body) → Outlook email
  wps_create(title, content) → WPS document
  export_latex(content) → LaTeX compile to PDF
  export_pptx(title, slides_data) → PowerPoint file
"""

from __future__ import annotations

import os
from pathlib import Path

from loguru import logger


# ═══ P1: Google Docs API ═══

def gdocs_create(title: str, content: str) -> str:
    """Create Google Docs document. Requires GOOGLE_SERVICE_ACCOUNT_JSON env var."""
    creds_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not creds_file or not Path(creds_file).exists():
        return (
            "Google Docs not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON to "
            "the path of your service account key file.\n"
            "Get one at: https://console.cloud.google.com/apis/credentials"
        )
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_file(
            creds_file, scopes=["https://www.googleapis.com/auth/documents"],
        )
        service = build("docs", "v1", credentials=creds)
        doc = service.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]

        # Insert content
        requests = [{"insertText": {"location": {"index": 1}, "text": content}}]
        service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

        return f"Google Docs created: https://docs.google.com/document/d/{doc_id}/edit"
    except ImportError:
        return "pip install google-auth google-api-python-client google-auth-httplib2"
    except Exception as e:
        return f"Google Docs error: {e}"


# ═══ P1: MS365 Graph API ═══

def ms365_send_email(to: str, subject: str, body: str) -> str:
    """Send email via MS365 Graph. Requires MS365_CLIENT_ID/TENANT_ID/SECRET env vars."""
    client_id = os.environ.get("MS365_CLIENT_ID", "")
    if not client_id:
        return (
            "MS365 not configured. Set MS365_CLIENT_ID, MS365_TENANT_ID, MS365_CLIENT_SECRET.\n"
            "Register app at: https://portal.azure.com → App registrations"
        )
    try:
        import requests
        tenant = os.environ["MS365_TENANT_ID"]
        secret = os.environ["MS365_CLIENT_SECRET"]
        sender = os.environ.get("MS365_SENDER_EMAIL", "")

        # Get token
        token_resp = requests.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "client_id": client_id, "client_secret": secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=15,
        )
        token = token_resp.json()["access_token"]

        # Send email
        requests.post(
            "https://graph.microsoft.com/v1.0/me/sendMail",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "message": {
                    "subject": subject,
                    "body": {"contentType": "Text", "content": body},
                    "toRecipients": [{"emailAddress": {"address": addr.strip()}} for addr in to.split(",")],
                },
            },
            timeout=15,
        )
        return f"Email sent to {to} via MS365"
    except ImportError:
        return "pip install requests"
    except Exception as e:
        return f"MS365 error: {e}"


def ms365_create_doc(title: str, content: str) -> str:
    """Create Word doc in OneDrive via MS365 Graph."""
    client_id = os.environ.get("MS365_CLIENT_ID", "")
    if not client_id:
        return "MS365 not configured."
    try:
        import requests
        tenant = os.environ["MS365_TENANT_ID"]
        secret = os.environ["MS365_CLIENT_SECRET"]
        token_resp = requests.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={"client_id": client_id, "client_secret": secret,
                  "scope": "https://graph.microsoft.com/.default",
                  "grant_type": "client_credentials"}, timeout=15,
        )
        token = token_resp.json()["access_token"]
        resp = requests.put(
            f"https://graph.microsoft.com/v1.0/me/drive/root:/{title}.docx:/content",
            headers={"Authorization": f"Bearer {token}"},
            data=content.encode("utf-8"),
            timeout=15,
        )
        return f"MS365 doc created: {title}.docx" if resp.ok else f"MS365 error: {resp.status_code}"
    except Exception as e:
        return f"MS365 error: {e}"


# ═══ P1: WPS API ═══

def wps_create(title: str, content: str) -> str:
    """Create WPS document. Requires WPS_API_KEY env var."""
    api_key = os.environ.get("WPS_API_KEY", "")
    if not api_key:
        return (
            "WPS not configured. Set WPS_API_KEY.\n"
            "Get key at: https://open.wps.cn"
        )
    try:
        import requests
        resp = requests.post(
            "https://openapi.wps.cn/v1/documents",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"title": title, "content": content, "format": "docx"},
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            return f"WPS doc created: {data.get('url', '')}"
        return f"WPS error: {resp.status_code} {resp.text[:200]}"
    except Exception as e:
        return f"WPS error: {e}"


# ═══ P1: LaTeX Export ═══

def export_latex(content: str, output: str = "output.pdf") -> str:
    """Compile LaTeX to PDF. Requires pdflatex on PATH."""
    import tempfile
    import subprocess as _sp

    # Check pdflatex
    try:
        _sp.run(["pdflatex", "--version"], capture_output=True, timeout=5)
    except FileNotFoundError:
        return "LaTeX not available. Install: sudo apt install texlive-latex-base"

    # Write .tex file
    tex_path = Path(tempfile.mktemp(suffix=".tex"))
    tex_path.write_text(content, encoding="utf-8")

    try:
        result = _sp.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory",
             str(tex_path.parent), str(tex_path.name)],
            capture_output=True, text=True, timeout=30, cwd=str(tex_path.parent),
        )
        pdf = tex_path.with_suffix(".pdf")
        if pdf.exists():
            # Move to working dir
            dest = Path(output)
            pdf.rename(dest)
            return f"LaTeX compiled: {dest} ({dest.stat().st_size} bytes)"
        return f"LaTeX compilation failed:\n{result.stdout[-1000:]}"
    except _sp.TimeoutExpired:
        return "LaTeX compilation timed out"
    except Exception as e:
        return f"LaTeX error: {e}"
    finally:
        tex_path.unlink(missing_ok=True)


# ═══ P2: PPT Generation ═══

def export_pptx(title: str, slides_json: str) -> str:
    """Generate PowerPoint from JSON slide data.

    slides_json format: [{"title":"Slide 1","content":["bullet1","bullet2"]}, ...]
    """
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        import json

        slides = json.loads(slides_json)
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        # Title slide
        title_slide = prs.slides.add_slide(prs.slide_layouts[0])
        title_slide.shapes.title.text = title
        if slides:
            title_slide.placeholders[1].text = slides[0].get("subtitle", "")

        # Content slides
        for i, slide_data in enumerate(slides[:20]):
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = slide_data.get("title", f"Slide {i+1}")

            body = slide.placeholders[1].text_frame
            body.clear()
            for bullet in slide_data.get("content", [])[:10]:
                p = body.add_paragraph()
                p.text = str(bullet)
                p.level = 0

        out = Path(title.replace(" ", "_") + ".pptx")
        prs.save(str(out))
        return f"PPT created: {out} ({len(slides)} slides, {out.stat().st_size} bytes)"
    except ImportError:
        return "pip install python-pptx"
    except Exception as e:
        return f"PPT error: {e}"


# ── Tool registration ──

TOOLS = {
    "gdocs_create": {"desc": "Create Google Docs document.", "params": "title, content"},
    "ms365_send_email": {"desc": "Send email via MS365 Outlook.", "params": "to, subject, body"},
    "ms365_create_doc": {"desc": "Create Word doc in OneDrive via MS365.", "params": "title, content"},
    "wps_create": {"desc": "Create WPS document.", "params": "title, content"},
    "export_latex": {"desc": "Compile LaTeX to PDF.", "params": "latex_content [output_path]"},
    "export_pptx": {"desc": "Generate PowerPoint from JSON slides.", "params": "title, slides_json"},
}
