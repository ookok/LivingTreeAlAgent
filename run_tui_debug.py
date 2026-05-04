"""Debug launcher — run TUI directly without package imports."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now import using absolute imports
from livingtree.tui.app import LivingTreeTuiApp

if __name__ == "__main__":
    print("Starting TUI in debug mode...")
    app = LivingTreeTuiApp(workspace=str(Path.cwd()))
    app.run()
