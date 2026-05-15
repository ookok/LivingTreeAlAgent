"""Force reset admin password in the relay server's account store."""
import hashlib
import json
import os
from pathlib import Path

ACCOUNT_FILE = Path(".livingtree/relay_accounts.json")
NEW_PASSWORD = os.environ.get("LT_RELAY_ADMIN_PWD", "")
if not NEW_PASSWORD:
    try:
        from livingtree.config.secrets import get_secret_vault
        NEW_PASSWORD = get_secret_vault().get("relay_admin_pwd", "")
    except Exception:
        pass
if not NEW_PASSWORD:
    print("ERROR: No admin password set. Set env LT_RELAY_ADMIN_PWD or add relay_admin_pwd to vault.")
    exit(1)

if not ACCOUNT_FILE.exists():
    print(f"ERROR: {ACCOUNT_FILE} not found")
    exit(1)

data = json.loads(ACCOUNT_FILE.read_text())

if "admin" not in data:
    print("ERROR: admin account not found")
    exit(1)

data["admin"]["password_hash"] = hashlib.sha256(NEW_PASSWORD.encode()).hexdigest()
data["admin"]["is_admin"] = True

ACCOUNT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
print(f"✓ Admin password reset to: {NEW_PASSWORD}")
print(f"  File: {ACCOUNT_FILE}")
