"""Direct TUI launcher — no package import needed for debugging."""
import sys
from pathlib import Path

# Add project root and make relative imports work
project = Path(__file__).parent
sys.path.insert(0, str(project))

# Mock the package structure so relative imports work
import types
livingtree = types.ModuleType("livingtree")
livingtree.tui = types.ModuleType("livingtree.tui")
sys.modules["livingtree"] = livingtree
sys.modules["livingtree.tui"] = livingtree.tui

# Now import
from livingtree.tui.app import LivingTreeTuiApp

if __name__ == "__main__":
    print("TUI debug mode — check data/logs/livingtree.log for boot progress")
    app = LivingTreeTuiApp(workspace=str(Path.cwd()))
    app.run()
