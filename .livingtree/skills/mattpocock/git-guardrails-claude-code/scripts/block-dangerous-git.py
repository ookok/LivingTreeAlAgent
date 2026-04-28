#!/usr/bin/env python3
"""
block-dangerous-git.py
Windows-compatible version of block-dangerous-git.sh
Reads JSON from stdin, checks if the command matches dangerous git patterns.

Exit codes:
  0  - safe, allow command
  2  - blocked, deny command (matches Claude Code hook convention)
"""

import json
import re
import sys

DANGEROUS_PATTERNS = [
    r"git\s+push",
    r"git\s+reset\s+--hard",
    r"git\s+clean\s+-fd",
    r"git\s+clean\s+-f\b",
    r"git\s+branch\s+-D",
    r"git\s+checkout\s+\.",
    r"git\s+restore\s+\.",
    r"push\s+--force",
    r"reset\s+--hard",
]


def main():
    # Read JSON from stdin
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        # Not valid JSON, just exit 0 (allow)
        sys.exit(0)

    # Extract command from tool_input.command
    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not command and isinstance(data, dict):
        # Try nested access
        command = data.get("tool_input", {}).get("command", "")

    # Check against dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            print(
                f"BLOCKED: '{command}' matches dangerous pattern '{pattern}'. "
                "The user has prevented you from doing this.",
                file=sys.stderr,
            )
            sys.exit(2)

    # Safe
    sys.exit(0)


if __name__ == "__main__":
    main()
