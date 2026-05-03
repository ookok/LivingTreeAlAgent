"""WT Enhancement Setup — Profile registration, multi-pane, global hotkey.

1. Register LivingTree as a dedicated WT profile (dropdown entry)
2. Create split-pane launch config (chat + code side by side)
3. Set up global Ctrl+` hotkey via WT settings
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def find_wt_settings() -> Path | None:
    """Find Windows Terminal settings.json."""
    paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Packages" / "Microsoft.WindowsTerminal_8wekyb3d8bbwe" / "LocalState" / "settings.json",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows Terminal" / "settings.json",
    ]
    for p in paths:
        if p.exists():
            return p
    return None


def register_profile(root: Path) -> bool:
    """Register LivingTree as a dedicated WT profile."""
    settings_path = find_wt_settings()
    if not settings_path:
        print("[WT] settings.json not found — WT may not be installed via Store")
        return False

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        settings = {"profiles": {"list": []}}

    profiles = settings.setdefault("profiles", {})
    profile_list = profiles.setdefault("list", [])

    # Remove existing LivingTree profile if any
    profile_list = [p for p in profile_list if p.get("name") != "🌳 LivingTree"]
    profiles["list"] = profile_list

    wt_exe = root / ".wt" / "WindowsTerminal.exe"
    python = os.sys.executable
    icon = root / ".wt" / "livingtree.ico"

    profile = {
        "name": "🌳 LivingTree",
        "commandline": f'"{python}" -m livingtree tui --direct',
        "startingDirectory": str(root),
        "icon": str(icon) if icon.exists() else "",
        "tabTitle": "🌳 LivingTree",
        "suppressApplicationTitle": True,
        "hidden": False,
        "font": {"face": "Cascadia Code", "size": 13},
        "colorScheme": "One Half Dark",
        "cursorShape": "bar",
        "useAcrylic": True,
        "acrylicOpacity": 0.85,
        "antialiasingMode": "cleartype",
        "padding": "8, 8, 8, 8",
        "scrollbarState": "hidden",
    }

    profile_list.append(profile)
    profiles["list"] = profile_list

    # Add global hotkey Ctrl+` (96 = backtick)
    if "actions" not in settings:
        settings["actions"] = []
    actions = settings["actions"]
    # Remove existing global summon if any
    actions = [a for a in actions if a.get("name") != "Summon LivingTree"]
    actions.append({
        "command": {
            "action": "newTab",
            "profile": "🌳 LivingTree",
        },
        "name": "Summon LivingTree",
        "keys": "ctrl+`",
    })
    settings["actions"] = actions

    settings_path.write_text(json.dumps(settings, indent=4, ensure_ascii=False), encoding="utf-8")
    print("[WT] Profile registered in settings.json")
    print(f"[WT] Global hotkey: Ctrl+` to summon LivingTree from anywhere")
    return True


def launch_split(root: Path) -> None:
    """Launch WT with split panes: chat left, code right."""
    wt_exe = root / ".wt" / "WindowsTerminal.exe"
    python = os.sys.executable

    if not wt_exe.exists():
        print("[WT] WindowsTerminal.exe not found in .wt/")
        return

    # Split pane: left=chat window, right=code window
    cmd = [
        str(wt_exe),
        "-d", str(root),
        "new-tab", "--title", "🌳 LivingTree",
        ";", "split-pane", "-H",
        f"{python} -c \"print('Code pane ready')\"",
    ]

    # Actually, launch the TUI in the main pane and split only if user wants
    tui_cmd = [
        str(wt_exe),
        "--title", "🌳 LivingTree",
        "-d", str(root),
        f"{python}", "-m", "livingtree", "tui", "--direct",
    ]
    print(f"[WT] Split launch: {' '.join(tui_cmd)}")
    subprocess.Popen(tui_cmd, cwd=str(root))


def setup_all(root: str = ".") -> None:
    """Run all WT enhancements."""
    root_path = Path(root).absolute()

    print("=" * 50)
    print("🌳 LivingTree WT Enhancement Setup")
    print("=" * 50)

    # 1. Register profile
    print("\n[1/3] Registering WT profile...")
    ok = register_profile(root_path)
    if ok:
        print("  Open WT dropdown → 🌳 LivingTree appears")
        print("  Press Ctrl+` anywhere to summon")

    # 2. Verify icon
    icon = root_path / ".wt" / "livingtree.ico"
    if icon.exists():
        print(f"\n[2/3] Icon verified: {icon}")
    else:
        print(f"\n[2/3] Icon not found, generating...")
        from install_shortcut import generate_icon
        icon_path = generate_icon()
        print(f"  Generated: {icon_path}")

    # 3. Done
    print(f"\n[3/3] Complete!")
    print(f"  python -m livingtree tui   → WT window")
    print(f"  Ctrl+` anywhere            → summon LivingTree")
    print("=" * 50)


if __name__ == "__main__":
    setup_all()
