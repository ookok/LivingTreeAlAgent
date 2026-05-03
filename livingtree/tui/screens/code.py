"""Code Editor Screen — AI-assisted coding with syntax highlight.

Features:
- Syntax-highlighted code editor (multi-language)
- AI code generation/completion via DeepSeek
- Run/preview output panel
- File save/load
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Input, Label, RichLog, Select, Static, TextArea,
)


LANGUAGES = [
    ("python", "Python"),
    ("javascript", "JavaScript"),
    ("typescript", "TypeScript"),
    ("html", "HTML"),
    ("css", "CSS"),
    ("json", "JSON"),
    ("yaml", "YAML"),
    ("markdown", "Markdown"),
    ("sql", "SQL"),
    ("bash", "Bash"),
    ("rust", "Rust"),
    ("go", "Go"),
    ("java", "Java"),
    ("cpp", "C++"),
]


class CodeScreen(Screen):
    """AI-assisted code editor with syntax highlighting."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None
        self._current_file: Optional[Path] = None
        self._language = "python"

    def set_hub(self, hub) -> None:
        self._hub = hub

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                Select(
                    [(lang, name) for lang, name in LANGUAGES],
                    prompt="Language",
                    value="python",
                    id="lang-select",
                ),
                Input(placeholder="File path...", id="file-path"),
                Button("Open", variant="default", id="open-btn"),
                Button("Save", variant="default", id="save-btn"),
                Button("AI Gen", variant="primary", id="ai-gen-btn"),
                Button("Run", variant="primary", id="run-btn"),
                id="code-toolbar",
            ),
            TextArea.code_editor(
                "",
                language="python",
                id="code-editor",
                show_line_numbers=True,
                tab_behavior="focus",
            ),
            RichLog(id="code-output", highlight=True, markup=True, wrap=True),
        )

    def on_mount(self) -> None:
        output = self.query_one("#code-output", RichLog)
        output.write("[bold]Code Output[/bold]")
        output.write("[dim]Ready — press 'AI Gen' for AI code generation[/dim]")

    @work(exclusive=False)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        editor = self.query_one("#code-editor", TextArea)
        output = self.query_one("#code-output", RichLog)

        if btn_id == "ai-gen-btn":
            await self._ai_generate_code(editor, output)
        elif btn_id == "run-btn":
            await self._run_code(editor, output)
        elif btn_id == "save-btn":
            await self._save_file(editor, output)
        elif btn_id == "open-btn":
            await self._open_file(editor, output)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "lang-select" and event.value:
            lang = str(event.value)
            self._language = lang
            try:
                editor = self.query_one("#code-editor", TextArea)
                editor.language = lang
            except Exception:
                pass

    async def _ai_generate_code(self, editor: TextArea, output: RichLog) -> None:
        """Generate code using DeepSeek API."""
        selection = editor.selected_text or editor.text
        if not selection or selection == editor.text:
            prompt = "Generate a Python utility function that demonstrates best practices"
        else:
            prompt = f"Write code that implements the following: {selection}"

        output.clear()
        output.write("[bold #58a6ff]AI generating code...[/bold #58a6ff]")

        if self._hub and hasattr(self._hub, 'config'):
            api_key = self._hub.config.model.deepseek_api_key
            base_url = self._hub.config.model.deepseek_base_url

            if api_key:
                try:
                    import aiohttp, json
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    }
                    payload = {
                        "model": "deepseek-v4-flash",
                        "messages": [
                            {"role": "system", "content": f"You are a code generation assistant. Generate {self._language} code only. No explanations unless asked."},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.2,
                        "max_tokens": 4096,
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{base_url}/v1/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=60),
                        ) as resp:
                            data = await resp.json()
                            code = data["choices"][0]["message"]["content"]

                    code = code.strip()
                    if code.startswith("```"):
                        lines = code.split("\n")
                        code = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

                    editor.text = code
                    editor.language = self._language
                    output.write("[bold green]Code generated![/bold green]")
                    return
                except Exception as e:
                    output.write(f"[bold red]API Error:[/bold red] {e}")
                    return

        # Fallback template
        template_code = self._get_template_code()
        editor.text = template_code
        editor.language = self._language
        output.write("[bold green]Template code generated (no API key configured)[/bold green]")

    async def _run_code(self, editor: TextArea, output: RichLog) -> None:
        """Run the current code (Python only for safety)."""
        code = editor.text
        if not code.strip():
            output.write("[bold yellow]No code to run[/bold yellow]")
            return

        if self._language != "python":
            output.write("[bold yellow]Running only supported for Python. Switch language.[/bold yellow]")
            return

        output.clear()
        output.write("[bold]Running...[/bold]")

        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            if stdout:
                output.write(f"[green]{stdout.decode('utf-8', errors='replace')}[/green]")
            if stderr:
                output.write(f"[red]{stderr.decode('utf-8', errors='replace')}[/red]")
            output.write(f"[dim]Exit code: {proc.returncode}[/dim]")
        except asyncio.TimeoutError:
            output.write("[bold red]Execution timed out (30s)[/bold red]")
        except Exception as e:
            output.write(f"[bold red]Error:[/bold red] {e}")

    async def _save_file(self, editor: TextArea, output: RichLog) -> None:
        path_input = self.query_one("#file-path", Input)
        path = path_input.value or str(self._current_file or "untitled.py")
        try:
            Path(path).write_text(editor.text, encoding="utf-8")
            self._current_file = Path(path)
            output.write(f"[green]Saved: {path}[/green]")
        except Exception as e:
            output.write(f"[red]Save error: {e}[/red]")

    async def _open_file(self, editor: TextArea, output: RichLog) -> None:
        path_input = self.query_one("#file-path", Input)
        path = path_input.value
        if not path:
            output.write("[yellow]Enter file path[/yellow]")
            return
        try:
            content = Path(path).read_text(encoding="utf-8")
            editor.text = content
            self._current_file = Path(path)
            # Auto-detect language
            ext = Path(path).suffix.lower()
            ext_map = {".py": "python", ".js": "javascript", ".ts": "typescript",
                       ".html": "html", ".css": "css", ".json": "json",
                       ".yaml": "yaml", ".yml": "yaml", ".md": "markdown",
                       ".sql": "sql", ".sh": "bash", ".rs": "rust", ".go": "go", ".java": "java"}
            lang = ext_map.get(ext, "python")
            editor.language = lang
            self._language = lang
            try:
                self.query_one("#lang-select", Select).value = lang
            except Exception:
                pass
            output.write(f"[green]Loaded: {path} ({len(content)} chars)[/green]")
        except Exception as e:
            output.write(f"[red]Open error: {e}[/red]")

    def _get_template_code(self) -> str:
        """Get a template code snippet based on language."""
        templates = {
            "python": '"""LivingTree AI-generated module."""\n\nfrom typing import Any, Optional\nfrom dataclasses import dataclass\n\n\n@dataclass\nclass Config:\n    name: str = "default"\n    version: str = "1.0"\n\n\ndef process(data: Any) -> dict[str, Any]:\n    """Process input data and return results."""\n    result = {"status": "ok", "input": str(data)}\n    return result\n\n\nif __name__ == "__main__":\n    print(process("Hello LivingTree!"))\n',
            "javascript": '// LivingTree AI-generated module\n\n/**\n * Process input data\n */\nfunction process(data) {\n    return { status: "ok", input: String(data) };\n}\n\n// Example\nconsole.log(process("Hello LivingTree!"));\n',
            "rust": '// LivingTree AI-generated module\n\nfn process(data: &str) -> String {\n    format!("Processed: {}", data)\n}\n\nfn main() {\n    println!("{}", process("Hello LivingTree!"));\n}\n',
        }
        return templates.get(self._language, f"# {self._language} code\n# Generated by LivingTree AI\n\nprint('Hello LivingTree!')\n")

    async def refresh(self) -> None:
        pass
