"""Standalone TUI debug — no package imports, all absolute."""
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import time
from loguru import logger

# Setup logging to file
logger.add("debug_boot.log", level="INFO", rotation="1 MB")

logger.info("=== TUI Debug Start ===")

async def test_import():
    """Test each import step."""
    steps = [
        ("加载模块: config", lambda: __import__("livingtree.config", fromlist=["get_config"])),
        ("加载模块: observability", lambda: __import__("livingtree.observability", fromlist=["setup_observability"])),
        ("加载模块: integration.hub", lambda: __import__("livingtree.integration.hub", fromlist=["IntegrationHub"])),
    ]
    
    for name, func in steps:
        try:
            logger.info(f"Testing: {name}")
            t0 = time.time()
            func()
            logger.info(f"  OK ({time.time()-t0:.2f}s)")
        except Exception as e:
            logger.error(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    return True

if __name__ == "__main__":
    print("Testing imports... see debug_boot.log")
    ok = asyncio.run(test_import())
    print("All imports OK!" if ok else "Import FAILED! Check debug_boot.log")
