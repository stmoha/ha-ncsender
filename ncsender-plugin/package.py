"""Package the HA Switches plugin the way ncSender installs it: one top-level
folder named after the plugin id. Usage: python ncsender-plugin/package.py [label]
-> ncsender-plugin/dist/com.cncdocs.ha-switches_<label>.zip (default label v<version>)."""
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
FILES = ["manifest.json", "index.js", "config.html", "README.md", "icon.png"]

manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
label = sys.argv[1] if len(sys.argv) > 1 else f"v{manifest['version']}"
out = HERE / "dist" / f"{manifest['id']}_{label}.zip"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for name in FILES:
        zf.write(HERE / name, f"{manifest['id']}/{name}")
print(f"Created {out}")
