"""
Generate data/test_manifest.json — records each locked test file's name,
row count, and SHA-256 hash, so anyone can verify they have identical
test data without the files themselves being committed.

Usage:
    uv run python scripts/make_manifest.py
"""
import hashlib
import json
from pathlib import Path

LOCKED_DIR = Path("data/test_locked")
MANIFEST_PATH = Path("data/test_manifest.json")


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def count_rows(path: Path) -> int:
    """Line count minus header (works for .csv and .tsv)."""
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


def main() -> None:
    manifest = {}
    for file_path in sorted(LOCKED_DIR.iterdir()):
        if file_path.is_file():
            manifest[file_path.name] = {
                "rows": count_rows(file_path),
                "sha256": sha256_of_file(file_path),
            }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Wrote manifest for {len(manifest)} files to {MANIFEST_PATH}")
    for name, info in manifest.items():
        print(f"  {name}: {info['rows']} rows, sha256={info['sha256'][:12]}...")


if __name__ == "__main__":
    main()