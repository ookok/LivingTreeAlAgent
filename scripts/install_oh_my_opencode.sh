#!/usr/bin/env bash
set -euo pipefail

# Install oh-my-opencode using bunx if available, otherwise fall back to npx
echo "Installing oh-my-opencode..."

if command -v bunx >/dev/null 2>&1; then
  echo "Using bunx to install oh-my-opencode..."
  bunx oh-my-opencode install
elif command -v npx >/dev/null 2>&1; then
  echo "Using npx to install oh-my-opencode..."
  npx oh-my-opencode install
else
  echo "Error: bunx (Bun) or npm/npx not found. Install Bun or Node to proceed." >&2
  exit 1
fi

# Post-install: create a default config if not present
CONFIG_DIR="${HOME}/.config/opencode"
CONFIG_FILE="${CONFIG_DIR}/oh-my-openagent.json"
mkdir -p "${CONFIG_DIR}"
if [ ! -f "${CONFIG_FILE}" ]; then
  cat > "${CONFIG_FILE}" <<'JSON'
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
JSON
  echo "Created default config at ${CONFIG_FILE}"
else
  echo "Config already exists at ${CONFIG_FILE}, skipping creation."
fi

echo "oh-my-opencode installation finished."
