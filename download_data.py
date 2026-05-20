#!/usr/bin/env python3
"""Download RareArena benchmark data files from GitHub."""

import os
import sys
import urllib.request
from pathlib import Path

# GitHub CDN requires a non-default User-Agent
opener = urllib.request.build_opener()
opener.addheaders = [("User-Agent", "Mozilla/5.0 (rare-disease-benchmark/1.0)")]
urllib.request.install_opener(opener)

# Add repo root to sys.path
from config import DATA_DIR, DATA_FILES


def download_file(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"  [skip] {dest.name} already exists")
        return
    print(f"  Downloading {dest.name} from GitHub...")
    urllib.request.urlretrieve(url, dest)
    size_mb = dest.stat().st_size / 1024 / 1024
    print(f"  Done: {dest.name} ({size_mb:.1f} MB)")


def main():
    data_dir = Path(DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading RareArena benchmark data...")
    for name, url in DATA_FILES.items():
        ext = "json" if name == "orphanet_hypernym" else "jsonl"
        dest = data_dir / f"{name}.{ext}"
        download_file(url, dest)

    print("\nAll files ready:")
    for f in sorted(data_dir.iterdir()):
        print(f"  {f.name}  ({f.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
