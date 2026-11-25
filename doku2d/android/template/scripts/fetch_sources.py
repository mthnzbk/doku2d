"""Download the pinned build inputs and verify their recorded SHA-256 hashes."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.request

project = Path(__file__).resolve().parents[1]
target = Path(sys.argv[1])
target.mkdir(parents=True, exist_ok=True)
sources = json.loads((project / "sources.lock.json").read_text())
for name in sys.argv[2:]:
    entry = sources[name]
    path = target / name
    if not path.exists():
        print("Downloading", name, flush=True)
        temporary = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(entry["url"], timeout=120) as source, temporary.open("wb") as out:
            shutil.copyfileobj(source, out)
        temporary.replace(path)
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != entry["sha256"]:
        raise SystemExit(f"SHA-256 mismatch: {path}")
    print("Verified", name, flush=True)
