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

__all__ = ["IntegrationHub", "launch", "LaunchMode"]
