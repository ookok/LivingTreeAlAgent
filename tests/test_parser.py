"""Test file format detection and parsing."""
import tempfile
from pathlib import Path

import pytest


class TestFormatDetection:
    def test_detect_png(self, temp_dir):
        from livingtree.capability.universal_parser import UniversalFileParser
        f = temp_dir / "test.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        fmt = UniversalFileParser()._detect_format(f)
        assert fmt == ".png"

    def test_detect_jpg(self, temp_dir):
        from livingtree.capability.universal_parser import UniversalFileParser
        f = temp_dir / "test.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF")
        fmt = UniversalFileParser()._detect_format(f)
        assert fmt == ".jpg"

    def test_detect_pdf(self, temp_dir):
        from livingtree.capability.universal_parser import UniversalFileParser
        f = temp_dir / "test.pdf"
        f.write_bytes(b"%PDF-1.4\n%test")
        fmt = UniversalFileParser()._detect_format(f)
        assert fmt == ".pdf"

    def test_detect_json(self, temp_dir):
        from livingtree.capability.universal_parser import UniversalFileParser
        f = temp_dir / "test.json"
        f.write_text('{"key": "value"}', encoding="utf-8")
        fmt = UniversalFileParser()._detect_format(f)
        assert fmt == ".json"

    def test_detect_xml(self, temp_dir):
        from livingtree.capability.universal_parser import UniversalFileParser
        f = temp_dir / "test.xml"
        f.write_text('<?xml version="1.0"?><root></root>', encoding="utf-8")
        fmt = UniversalFileParser()._detect_format(f)
        assert fmt == ".xml"

    def test_detect_zip(self, temp_dir):
        from livingtree.capability.universal_parser import UniversalFileParser
        f = temp_dir / "test.zip"
        f.write_bytes(b"PK\x03\x04\x00\x00\x00\x00")
        fmt = UniversalFileParser()._detect_format(f)
        assert fmt in (".zip", ".docx", ".xlsx")

    def test_detect_sqlite(self, temp_dir):
        import sqlite3
        f = temp_dir / "test.db"
        conn = sqlite3.connect(str(f))
        conn.execute("CREATE TABLE t (c)")
        conn.commit()
        conn.close()
        from livingtree.capability.universal_parser import UniversalFileParser
        fmt = UniversalFileParser()._detect_format(f)
        assert fmt == ".sqlite"

    def test_detect_unknown_extension(self, temp_dir):
        from livingtree.capability.universal_parser import UniversalFileParser
        f = temp_dir / "test.xyz"
        f.write_text("random content", encoding="utf-8")
        fmt = UniversalFileParser()._detect_format(f)
        assert fmt in (".xyz", ".unknown")


class TestParsing:
    def test_parse_csv(self, sample_csv):
        from livingtree.capability.universal_parser import get_universal_parser
        import asyncio
        result = asyncio.run(get_universal_parser().parse(str(sample_csv)))
        assert result.success
        assert len(result.tables) >= 1

    def test_parse_json(self, sample_json):
        from livingtree.capability.universal_parser import get_universal_parser
        import asyncio
        result = asyncio.run(get_universal_parser().parse(str(sample_json)))
        assert result.success
        assert "port" in result.text.lower() or result.success

    def test_parse_xlsx(self, sample_xlsx):
        if sample_xlsx is None:
            pytest.skip("openpyxl not installed")
        from livingtree.capability.universal_parser import get_universal_parser
        import asyncio
        result = asyncio.run(get_universal_parser().parse(str(sample_xlsx)))
        assert result.success
        assert len(result.tables) >= 1

    def test_parse_md(self, sample_md):
        from livingtree.capability.universal_parser import get_universal_parser
        import asyncio
        result = asyncio.run(get_universal_parser().parse(str(sample_md)))
        assert result.success
        assert "第三章" in result.text

    def test_parse_nonexistent(self):
        from livingtree.capability.universal_parser import get_universal_parser
        import asyncio
        result = asyncio.run(get_universal_parser().parse("nonexistent.xyz"))
        assert not result.success

    def test_zip_listing(self, temp_dir):
        import zipfile
        f = temp_dir / "test.zip"
        with zipfile.ZipFile(str(f), "w") as zf:
            zf.writestr("a.txt", "hello")
            zf.writestr("b.txt", "world")
        from livingtree.capability.universal_parser import get_universal_parser
        import asyncio
        result = asyncio.run(get_universal_parser().parse(str(f)))
        assert result.success
        assert "a.txt" in result.text

    def test_parser_registry_coverage(self):
        from livingtree.capability.universal_parser import PARSER_REGISTRY
        exts = set(p.extension for p in PARSER_REGISTRY)
        assert ".pdf" in exts
        assert ".xlsx" in exts
        assert ".dwg" in exts
        assert ".shp" in exts
        assert ".csv" in exts
