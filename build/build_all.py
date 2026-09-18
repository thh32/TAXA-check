#!/usr/bin/env python3
"""Canonical TAXA-check database build, verification, and GitHub update pipeline.

Run from the repository root:
    python build/build_all.py

Recommended release build:
    python build/build_all.py --restart

Reuse existing raw downloads:
    python build/build_all.py --skip-downloads

By default, the GitHub database version is the current UTC date in YYYY.MM.DD
format. Override it when necessary:
    python build/build_all.py --database-version 2026.09.18

The pipeline creates:
    extension/generated/names.json
    extension/generated/epithets.json
    extension/generated/metadata.json
    database/names.json
    database/epithets.json
    database/metadata.json
    database/latest.json
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
OUTPUT = ROOT / "output"
GENERATED = ROOT / "extension" / "generated"
DATABASE = ROOT / "database"

LPSN_RAW = "output/lpsn_raw.jsonl"
LPSN_NORMALIZED = "output/lpsn_normalized.json"
SEQCODE_NORMALIZED = "output/seqcode_normalized.json"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build, verify, and package the TAXA-check database"
    )
    parser.add_argument("--email", help="LPSN account email")
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Restart the primary LPSN download",
    )
    parser.add_argument(
        "--skip-downloads",
        action="store_true",
        help="Reuse existing raw LPSN and SeqCode downloads",
    )
    parser.add_argument(
        "--skip-higher-rank-completion",
        action="store_true",
        help="Skip supplemental LPSN higher-rank queries",
    )
    parser.add_argument(
        "--include-general-supplements",
        action="store_true",
        help=(
            "Run add_lpsn_supplements.py; disabled by default because its "
            "legacy additions may overlap newer curated stages"
        ),
    )
    parser.add_argument(
        "--database-version",
        default=datetime.now(timezone.utc).strftime("%Y.%m.%d"),
        help="Published database version; default is the current UTC date",
    )
    parser.add_argument(
        "--skip-github-package",
        action="store_true",
        help="Do not create the database/ files used by the GitHub updater",
    )
    return parser.parse_args()


def require_script(filename: str) -> Path:
    path = BUILD / filename
    if not path.is_file():
        raise SystemExit(f"Required build script is missing: {path}")
    return path


def run(label: str, filename: str, *extra: str) -> None:
    script = require_script(filename)
    command = [sys.executable, str(script), *extra]
    print(
        f"\n{'=' * 72}\n{label}\n$ {' '.join(command)}\n{'=' * 72}",
        flush=True,
    )
    started = time.monotonic()
    subprocess.run(command, cwd=ROOT, env=os.environ.copy(), check=True)
    print(f"Completed in {time.monotonic() - started:.1f} seconds", flush=True)


def require_output(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"Expected output is missing or empty: {path}")
    return path


def main() -> None:
    args = arguments()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    GENERATED.mkdir(parents=True, exist_ok=True)
    auth = ["--email", args.email] if args.email else []

    if not args.skip_downloads:
        primary_args = list(auth)
        if args.restart:
            primary_args.append("--restart")
        run("1. Download LPSN records", "download_lpsn.py", *primary_args)

        if not args.skip_higher_rank_completion:
            run(
                "2. Complete higher-rank LPSN coverage",
                "download_lpsn_higher_ranks.py",
                *auth,
            )

        run(
            "3. Fetch missing linked LPSN records",
            "fetch_missing_lpsn_links.py",
            *auth,
        )
        run("4. Download SeqCode Registry records", "download_seqcode.py")
    else:
        print("Reusing existing raw downloads (--skip-downloads).", flush=True)

    require_output(LPSN_RAW)

    run("5. Normalize LPSN records", "normalize_lpsn.py")
    require_output(LPSN_NORMALIZED)

    if args.include_general_supplements:
        run("6a. Apply reviewed general LPSN supplements", "add_lpsn_supplements.py")
        require_output(LPSN_NORMALIZED)

    run("6. Apply historical phylum supplement", "add_phylum_synonym_supplement.py")
    require_output(LPSN_NORMALIZED)

    run("7. Normalize SeqCode Registry records", "normalize_seqcode.py")
    require_output(SEQCODE_NORMALIZED)

    run(
        "8. Remove placeholder pseudo-taxa",
        "filter_placeholders.py",
        LPSN_NORMALIZED,
        SEQCODE_NORMALIZED,
    )
    require_output(LPSN_NORMALIZED)
    require_output(SEQCODE_NORMALIZED)

    run("9. Merge sources and compile extension indexes", "merge_compile.py")
    require_output("extension/generated/names.json")
    require_output("extension/generated/epithets.json")
    require_output("extension/generated/metadata.json")

    run(
        "10. Remove redundant same-spelling redirects",
        "deduplicate_identical_name_redirects.py",
    )
    run("11. Propagate LoRN relevance to genera", "propagate_lorn_to_genera.py")

    run("12a. Verify normalized records contain no self-links", "verify_self_links.py")
    run("12b. Verify higher-rank coverage", "verify_all_higher_ranks.py")
    run("12c. Verify historical phylum supplement", "verify_phylum_supplement.py")
    run("13a. Verify representative compiled names", "verify_names.py")
    run("13b. Verify correct-name resolution", "verify_resolution.py")

    if not args.skip_github_package:
        run(
            "14. Prepare GitHub database update files",
            "prepare_github_database_update.py",
            "--version",
            args.database_version,
        )
        require_output("database/latest.json")
        require_output("database/names.json")
        require_output("database/epithets.json")
        require_output("database/metadata.json")

    print("\nTAXA-check database build and verification completed successfully.")
    print("Extension database:", GENERATED)
    if not args.skip_github_package:
        print("GitHub update database:", DATABASE)
        print("Published database version:", args.database_version)
        print("Commit the database/ directory together with the updated source files.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(
            f"Build stopped because a stage failed with exit code {error.returncode}."
        )
