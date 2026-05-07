"""Force reset admin password in the relay server's account store."""
import hashlib
import json
from pathlib import Path

ACCOUNT_FILE = Path(".livingtree/relay_accounts.json")
NEW_PASSWORD = "admin123"

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
