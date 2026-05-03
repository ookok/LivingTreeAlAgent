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

    # 32x32 RGBA pixels: green tree icon
    # Simple bitmap: green "L" shape on dark background
    width, height = 32, 32
    pixels = bytearray()

    for y in range(height):
        for x in range(width):
            # Tree shape: centered trunk + canopy
            cx, cy = 16, 20  # center
            dx, dy = abs(x - cx), abs(y - cy)
            in_trunk = dx <= 2 and y >= 12 and y <= 30
            in_canopy = (y < 18 and dx <= 10 and dy <= 10 and not (dx <= 2 and y < 12))
            if in_canopy:
                pixels.extend([0, 180, 60, 255])  # green
            elif in_trunk:
                pixels.extend([80, 50, 20, 255])   # brown
            else:
                pixels.extend([13, 17, 23, 0])     # transparent

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


def create_shortcut():
    root = Path(__file__).parent.parent
    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    shortcut_path = desktop / "LivingTree AI Agent.lnk"
    python = sys.executable
    bootstrapper = root / "livingtree" / "tui" / "wt_bootstrap.py"
    icon_path = generate_icon()

    ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{python}"
$Shortcut.Arguments = '"{bootstrapper}"'
$Shortcut.WorkingDirectory = "{root}"
$Shortcut.IconLocation = "{icon_path}"
$Shortcut.Description = "LivingTree AI Agent — Digital Lifeform Platform"
$Shortcut.Save()
"""

    try:
        subprocess.run(["powershell", "-Command", ps_script],
                       capture_output=True, timeout=10)
        print(f"[LivingTree] Desktop shortcut created: {shortcut_path}")
        print(f"[LivingTree] Icon: {icon_path}")
    except Exception as e:
        print(f"[LivingTree] Shortcut failed: {e}")
        print(f"  python {python} {bootstrapper}")


if __name__ == "__main__":
    create_shortcut()
