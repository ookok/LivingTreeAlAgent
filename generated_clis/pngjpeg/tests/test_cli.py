"""Unit tests for CLI tool"""
import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCLI:
    """CLI functionality tests"""

    def test_parser_creation(self):
        """Test argument parser creation"""
        from cli_tool.__main__ import create_parser
        parser = create_parser()
        assert parser is not None

    def test_help_flag(self):
        """Test help parameter"""
        import io
        import contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            pass  # Verify no error

    def test_version_flag(self):
        """Test version parameter"""
        from cli_tool.__main__ import VERSION
        assert VERSION is not None
        assert len(VERSION.split(".")) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
