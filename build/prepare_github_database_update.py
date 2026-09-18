#!/usr/bin/env python3
"""Create the database files consumed by TAXA-check's GitHub updater.

This script is normally called automatically by build/build_all.py.
It can also be run directly from the repository root:
    python build/prepare_github_database_update.py --version 2026.09.18
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "extension" / "generated"
DATABASE = ROOT / "database"
RAW_BASE = "https://raw.githubusercontent.com/thh32/TAXA-check/main/database/"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"Required generated database is missing or empty: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {path}: {error}") from error


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        required=True,
        help="Database version, preferably YYYY.MM.DD",
    )
    args = parser.parse_args()

    DATABASE.mkdir(parents=True, exist_ok=True)

    source_paths = {
        "names": GENERATED / "names.json",
        "epithets": GENERATED / "epithets.json",
        "metadata": GENERATED / "metadata.json",
    }

    names = read_json(source_paths["names"])
    epithets = read_json(source_paths["epithets"])
    metadata = read_json(source_paths["metadata"])

    if not isinstance(names, dict) or not names:
        raise SystemExit("names.json must contain a non-empty JSON object.")
    if not isinstance(epithets, dict) or not epithets:
        raise SystemExit("epithets.json must contain a non-empty JSON object.")
    if not isinstance(metadata, dict):
        raise SystemExit("metadata.json must contain a JSON object.")

    for required in ("escherichia coli", "firmicutes", "proteobacteria"):
        if required not in names:
            raise SystemExit(f"Required validation name is absent: {required}")

    created_at = datetime.now(timezone.utc).isoformat()
    published_metadata = dict(metadata)
    published_metadata["database_version"] = args.version
    published_metadata["database_published_at"] = created_at

    shutil.copyfile(source_paths["names"], DATABASE / "names.json")
    shutil.copyfile(source_paths["epithets"], DATABASE / "epithets.json")
    write_json(DATABASE / "metadata.json", published_metadata)

    manifest = {
        "schema_version": 1,
        "database_version": args.version,
        "created_at": created_at,
        "names_url": RAW_BASE + "names.json",
        "epithets_url": RAW_BASE + "epithets.json",
        "metadata_url": RAW_BASE + "metadata.json",
        "names_sha256": sha256(DATABASE / "names.json"),
        "epithets_sha256": sha256(DATABASE / "epithets.json"),
        "metadata_sha256": sha256(DATABASE / "metadata.json"),
        "written_names": len(names),
        "epithet_entries": len(epithets),
    }
    write_json(DATABASE / "latest.json", manifest)

    # Verify the completed manifest and copied files before reporting success.
    read_json(DATABASE / "latest.json")
    read_json(DATABASE / "names.json")
    read_json(DATABASE / "epithets.json")
    read_json(DATABASE / "metadata.json")

    print("Prepared GitHub update database:", DATABASE)
    print("Database version:", args.version)
    print("Unique written names:", f"{len(names):,}")
    print("Created:")
    for filename in ("latest.json", "names.json", "epithets.json", "metadata.json"):
        path = DATABASE / filename
        print(f"  {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
