"""Integration layer — Central hub that wires all layers together.

The IntegrationHub is the entry point that:
1. Loads configuration
2. Creates all components with DI
3. Wires LifeEngine with all layers
4. Manages lifecycle (start/stop)
5. Provides the unified API surface
"""

from .hub import IntegrationHub
from .launcher import launch, LaunchMode
from .sse_server import SSEAgentServer, create_sse_server
from .self_updater import check_update, download_update, install_update, run_update

__all__ = [
    "IntegrationHub", "launch", "LaunchMode",
    "SSEAgentServer", "create_sse_server",
    "check_update", "download_update", "install_update", "run_update",
]
