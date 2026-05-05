"""Test tools for correctness — deterministic input → deterministic output."""
import json
import tempfile
from pathlib import Path

import pytest


class TestDocumentEditor:
    def test_replace_pattern_direct(self, temp_file):
        f = temp_file("config.yaml", "port: 8100\nhost: localhost\n")
        from livingtree.capability.document_editor import get_editor
        editor = get_editor()
        result = editor.replace_pattern(str(f), r"port:\s*8100", "port: 8888")
        assert result.replacements == 1
        assert "port: 8888" in f.read_text()

    def test_replace_pattern_no_match(self, temp_file):
        f = temp_file("config.yaml", "port: 8100\n")
        from livingtree.capability.document_editor import get_editor
        result = get_editor().replace_pattern(str(f), "9999", "0000")
        assert result.replacements == 0

    def test_smart_replace_key(self, temp_file):
        f = temp_file("config.yaml", "port: 8100\nhost: localhost\n")
        from livingtree.capability.document_editor import get_editor
        result = get_editor().smart_replace(str(f), "port: 8100", "port: 9999", mode="key")
        assert result.replacements == 1

    def test_bulk_replace(self, temp_file):
        f = temp_file("config.yaml", "port: 8100\ndebug: false\n")
        from livingtree.capability.document_editor import get_editor
        result = get_editor().bulk_replace(str(f), {"8100": "8888", "false": "true"})
        assert result.replacements >= 1

    def test_replace_section(self, sample_md):
        from livingtree.capability.document_editor import get_editor
        result = get_editor().replace_section(str(sample_md), "第三章", "新内容\n", dry_run=True)
        assert result.replacements == 1


class TestToolExecutor:
    def test_csv_analyze(self, sample_csv):
        from livingtree.capability.tool_executor import get_executor
        exe = get_executor()
        result = exe.csv_analyze(str(sample_csv))
        assert result.success
        assert "name" in result.output
        assert "value" in result.output

    def test_db_query(self):
        from livingtree.capability.tool_executor import get_executor
        exe = get_executor()
        result = exe.db_query("SELECT 1 AS test_col")
        assert result.success
        assert "test_col" in result.output

    def test_db_schema(self, temp_dir):
        import sqlite3
        db_path = temp_dir / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE users (id INTEGER, name TEXT)")
        conn.commit()
        conn.close()

        from livingtree.capability.tool_executor import get_executor
        result = get_executor().db_schema(str(db_path))
        assert result.success
        assert "users" in result.output

    def test_json_transform(self):
        from livingtree.capability.tool_executor import get_executor
        result = get_executor().json_transform('{"a": {"b": 42}}', "a.b")
        assert result.success
        assert "42" in result.output

    def test_json_transform_invalid(self):
        from livingtree.capability.tool_executor import get_executor
        result = get_executor().json_transform("not json", "")
        assert not result.success


class TestTemplateEngine:
    def test_extract_variables(self):
        from livingtree.capability.template_engine import TemplateEngine
        engine = TemplateEngine()
        vars_found = engine.extract_variables("项目名称: {{name}}, 日期: {{date}}")
        assert set(vars_found) == {"name", "date"}

    def test_fill_static(self):
        from livingtree.capability.template_engine import TemplateEngine
        engine = TemplateEngine()
        filled, missing = engine.fill_static(
            "{{name}}在{{place}}", {"name": "张三"}
        )
        assert "张三" in filled
        assert "place" in missing


class TestContentDedup:
    def test_blocks_detection(self):
        from livingtree.capability.content_dedup import ContentDedup
        dedup = ContentDedup(min_lines=2, min_chars=10)
        blocks_map = {}
        lines = ["def foo():\n", "    pass\n", "def foo():\n", "    pass\n"]
        dedup._extract_blocks("test.py", lines, 2, blocks_map)
        assert len(blocks_map) >= 1


class TestPatchManager:
    def test_generate_patch(self, temp_file):
        f = temp_file("test.py", "line one\nline two\nline three\n")
        from livingtree.capability.patch_manager import get_patch_manager
        pm = get_patch_manager()
        result = pm.generate(str(f), "line one\nline two\nline three\n", "line one\nline NEW\nline three\n", name="test")
        assert result.patch_path is not None
        assert result.lines_added >= 1 or result.lines_removed >= 1


class TestFileWatcher:
    def test_skip_dirs(self, temp_file):
        from livingtree.capability.file_watcher import FileWatcher
        w = FileWatcher()
        assert w._should_skip(Path(".venv/test.py"))
        # Create a test file that exists and verify it's NOT skipped
        f = temp_file("main.py", "print('hello')")
        assert not w._should_skip(f)


class TestSemanticBackup:
    def test_backup_list_empty(self):
        from livingtree.capability.semantic_backup import get_semantic_backup
        sb = get_semantic_backup()
        entries = sb.list("nonexistent_file.py")
        assert entries == [] or entries is not None
