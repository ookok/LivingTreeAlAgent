"""
LivingTree Desktop Shortcut Installer with icon.

Creates a Windows shortcut (.lnk) on the desktop with the LivingTree icon.
Generates a simple .ico from embedded pixels if not found.
"""

import os
import sys
import subprocess
import struct
from pathlib import Path


def generate_icon() -> Path:
    """Generate a minimal .ico file in the program directory."""
    icon_path = Path(__file__).parent.parent / ".wt" / "livingtree.ico"
    if icon_path.exists():
        return icon_path

    icon_path.parent.mkdir(parents=True, exist_ok=True)

    # 32x32 RGBA: 🌳 tree icon — rounded canopy + trunk on green
    width, height = 32, 32
    pixels = bytearray()
    # Draw a proper tree with rounded canopy on grass
    for y in range(height):
        for x in range(width):
            cx = 16
            dx = abs(x - cx)
            dy_up = max(0, 16 - y)  # distance from canopy top

            # Gradient sky background
            if y < 5 and dx > 10:
                r, g, b, a = 135, 206, 235, 255  # sky blue top
            elif y < 15 and dx > 10:
                r, g, b, a = 176, 224, 230, 255  # lighter sky
            else:
                r, g, b, a = 240, 255, 255, 255   # white bg

            # Trunk: 4px wide, bottom portion
            trunk = y >= 16 and y <= 27 and dx <= 3 and dx >= 0
            # Canopy: 3 layered ellipses
            top_canopy = y >= 3 and y <= 9 and dx <= 7 - (y - 3) * 0.3
            mid_canopy = y >= 6 and y <= 13 and dx <= 10 - (y - 6) * 0.4
            bot_canopy = y >= 9 and y <= 17 and dx <= 13 - (y - 9) * 0.5

            canopy = top_canopy or mid_canopy or bot_canopy

            # Draw canopy — gradient green
            if canopy:
                shade = 100 + (y - 3) * 8  # darker at bottom
                r, g, b, a = 34, min(200, shade), 34, 255
            # Draw trunk — brown
            elif trunk:
                r, g, b, a = 101, 67, 33, 255
            # Ground line
            elif y >= 28 and dx <= 14:
                r, g, b, a = 34, 139, 34, 255
            elif y >= 29 and dx <= 16:
                r, g, b, a = 50, 180, 50, 255

            pixels.extend([r, g, b, a])

    # BMP data
    bmp_size = 40 + len(pixels)
    bmp = b''
    bmp += struct.pack('<I', 40)      # header size
    bmp += struct.pack('<i', width)
    bmp += struct.pack('<i', height * 2)  # double height for ICO
    bmp += struct.pack('<H', 1)       # planes
    bmp += struct.pack('<H', 32)      # bpp
    bmp += struct.pack('<I', 0)       # compression
    bmp += struct.pack('<I', len(pixels))
    bmp += struct.pack('<i', 0) * 4   # unused
    bmp += bytes(pixels)

    # ICO header
    ico = b''
    ico += struct.pack('<HHH', 0, 1, 1)  # reserved, type, count
    ico += struct.pack('<BBBBHHII', width, height, 0, 0, 1, 32, len(bmp), 22)
    ico += bmp

    icon_path.write_bytes(ico)
    return icon_path


def install():
    """Full install: icon + shortcut + pre-download WT."""
    root = Path(__file__).parent.parent

    # 1. Generate icon
    icon_path = generate_icon()
    print(f"[LivingTree] Icon: {icon_path}")

    # 2. Pre-download WT (so first launch is instant)
    wt_path = root / ".wt" / "WindowsTerminal.exe"
    if not wt_path.exists():
        print("[LivingTree] Pre-downloading Windows Terminal...")
        # Import our bootstrapper's download
        bootstrapper = root / "livingtree" / "tui" / "wt_bootstrap.py"
        result = subprocess.run(
            [sys.executable, str(bootstrapper), "--download"],
            capture_output=True, text=True, timeout=300, cwd=str(root),
        )
        print(result.stdout.strip())
    else:
        print(f"[LivingTree] WT already installed: {wt_path}")

    # 3. Create desktop shortcut
    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    shortcut_path = desktop / "LivingTree AI Agent.lnk"
    python = sys.executable
    bs = root / "livingtree" / "tui" / "wt_bootstrap.py"

    ps = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{python}"
$Shortcut.Arguments = '"{bs}"'
$Shortcut.WorkingDirectory = "{root}"
$Shortcut.IconLocation = "{icon_path}"
$Shortcut.Description = "LivingTree AI Agent — Digital Lifeform Platform"
$Shortcut.Save()
"""
    try:
        subprocess.run(["powershell", "-Command", ps], capture_output=True, timeout=10)
        print(f"[LivingTree] Desktop shortcut created: {shortcut_path}")
    except Exception as e:
        print(f"[LivingTree] Shortcut failed: {e}")

    # 4. Register WT profile + global hotkey
    try:
        from .wt_setup import register_profile
        register_profile(root)
    except ImportError:
        sys.path.insert(0, str(root / "scripts"))
        from wt_setup import register_profile
        register_profile(root)


if __name__ == "__main__":
    install()
