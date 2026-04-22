# Installation Guide: oh-my-opencode

This guide mirrors the official installation instructions for oh-my-opencode. Follow the steps below to install and configure the harness locally.

Official instructions (reference):
- Install and configure oh-my-opencode by following the instructions here: https://raw.githubusercontent.com/code-yeongyu/oh-my-openagent/refs/heads/dev/docs/guide/installation.md

Recommended one-liner installers
- Bun-based installer (recommended):
  bunx oh-my-opencode install
- Node-based installer (alternative):
  npx oh-my-opencode install

Prerequisites
- Ensure you have a runtime available for Bun or Node (npm/npx) installed on your system.
- Bun is preferred for the bunx workflow, but npm/npx will work as an alternative.

Step-by-step installation
- Step 1: Install oh-my-opencode
  - If bunx is available:
    bunx oh-my-opencode install
  - Else if npm/npx is available:
    npx oh-my-opencode install
  - If neither is available, install Bun or Node first.
- Step 2: Post-install configuration
  - A default configuration file will be created at:
    ~/.config/opencode/oh-my-openagent.json
  - You can customize provider keys (Claude, ChatGPT, Gemini) in that JSON file.
- Step 3: Validation
  - Verify binary/command availability, e.g. run:
    oh-my-opencode --version  # or the equivalent CLI entry point if provided

Config file (example)
```json
{
  "providers": {
    "claude": { "enabled": false, "apiKey": "" },
    "chatgpt": { "enabled": true, "apiKey": "" },
    "gemini": { "enabled": false, "apiKey": "" }
  },
  "agents": {
    "default": "LivingTreeAgent"
  }
}
```

Notes
- The official installation guide may reference additional configuration options. Adjust the config file to fit your environment and provider subscriptions.
- This repo includes a local installer script for convenience: `scripts/install_oh_my_opencode.sh`.

If you want to start from this local guide, you can run:
- bash scripts/install_oh_my_opencode.sh
