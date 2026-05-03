"""Download Windows Terminal for offline pre-bundling."""
import urllib.request, zipfile, shutil, os, json, ssl
from pathlib import Path

ssl._create_default_https_context = ssl._create_unverified_context

VERSION = "v1.25.1171.0"
NAME = f"Microsoft.WindowsTerminal_{VERSION.lstrip('v')}_x64"

# Try API first
zip_url = f"https://github.com/microsoft/terminal/releases/download/{VERSION}/{NAME}.zip"
try:
    api = f"https://api.github.com/repos/microsoft/terminal/releases/tags/{VERSION}"
    req = urllib.request.Request(api, headers={"User-Agent": "LivingTree/2.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        release = json.loads(r.read())
    for a in release.get("assets", []):
        if a["name"].endswith("_x64.zip") and "PreinstallKit" not in a["name"]:
            zip_url = a["browser_download_url"]
            print(f"Asset: {a['name']} ({a['size']//1024//1024}MB)")
            break
except Exception as e:
    print(f"API: {e}, using direct URL")

dest = Path(".wt")
dest.mkdir(exist_ok=True)
zp = dest / "wt.zip"

print(f"Downloading {zip_url}...")
req2 = urllib.request.Request(zip_url, headers={"User-Agent": "LivingTree/2.0"})
with urllib.request.urlopen(req2, timeout=600) as r:
    with open(zp, "wb") as f:
        total = 0
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
        print(f"Downloaded: {total//1024//1024}MB")

print("Extracting...")
ext = dest / "_ext"
ext.mkdir(exist_ok=True)
with zipfile.ZipFile(zp, "r") as zf:
    zf.extractall(ext)
for root, dirs, files in os.walk(ext):
    if "WindowsTerminal.exe" in files:
        src = Path(root) / "WindowsTerminal.exe"
        shutil.move(str(src), str(dest / "WindowsTerminal.exe"))
        print(f"Installed: {dest / 'WindowsTerminal.exe'}")
        break
zp.unlink()
shutil.rmtree(ext, ignore_errors=True)
print("Done")
