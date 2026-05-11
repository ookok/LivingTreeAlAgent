"""Standard test fixtures for LivingTree."""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def temp_file(temp_dir):
    def _create(name: str, content: str = "") -> Path:
        fpath = temp_dir / name
        fpath.write_text(content, encoding="utf-8")
        return fpath
    return _create


@pytest.fixture
def sample_csv(temp_dir) -> Path:
    fpath = temp_dir / "test.csv"
    fpath.write_text("name,value,unit\nA,10,kg\nB,20,kg\nC,30,kg\n", encoding="utf-8")
    return fpath


@pytest.fixture
def sample_json(temp_dir) -> Path:
    fpath = temp_dir / "test.json"
    fpath.write_text(json.dumps({"server": {"port": 8100, "host": "localhost"}}), encoding="utf-8")
    return fpath


@pytest.fixture
def sample_config_yml(temp_dir) -> Path:
    fpath = temp_dir / "config.yaml"
    fpath.write_text("port: 8100\nhost: localhost\ndebug: true\n", encoding="utf-8")
    return fpath


@pytest.fixture
def sample_xlsx(temp_dir) -> Path:
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(["名称", "浓度", "单位"])
        ws.append(["A点", 0.023, "mg/m³"])
        ws.append(["B点", 0.045, "mg/m³"])
        fpath = temp_dir / "test.xlsx"
        wb.save(str(fpath))
        return fpath
    except ImportError:
        return None


@pytest.fixture
def sample_md(temp_dir) -> Path:
    fpath = temp_dir / "test.md"
    fpath.write_text(
        "## 第三章 环境质量现状\n\n"
        "### 3.1 大气环境\n\n"
        "本次评价布设3个监测点。\n\n"
        "### 3.2 水环境\n\n"
        "本项目不涉及地表水。\n\n",
        encoding="utf-8",
    )
    return fpath


@pytest.fixture(scope="session")
def hub():
    """Session-scoped IntegrationHub for pipeline tests."""
    import asyncio
    from livingtree.integration.hub import IntegrationHub
    from livingtree.config.settings import get_config

    _hub = IntegrationHub(config=get_config(), lazy=False)
    _hub._init_sync()

    async def _start():
        await _hub._init_async()

    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.run(_start())

    yield _hub

    try:
        asyncio.run(_hub.shutdown())
    except Exception:
        pass
