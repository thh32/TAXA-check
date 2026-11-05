#!/usr/bin/env python3
"""Sanitize compiled TAXA-check names and rebuild the epithet index."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


NAMES_PATH = Path("extension/generated/names.json")
EPITHETS_PATH = Path("extension/generated/epithets.json")
AUDIT_PATH = Path("output/compiled_database_sanitization.json")

NOT_ASSIGNED = re.compile(
    r"\bnot\s+assigned\s+to\s+"
    r"(?:domain|kingdom|phylum|class|order|family|genus|species|subspecies)\b",
    re.IGNORECASE,
)

BLOCKED_EPITHETS = {
    "not",
    "assigned",
    "species",
    "sp",
    "spp",
    "genus",
    "family",
    "order",
    "class",
    "phylum",
    "kingdom",
    "domain",
    "strain",
    "isolate",
    "bacterium",
    "bacteria",
    "organism",
    "microorganism",
    "uncultured",
    "unclassified",
    "unknown",
    "candidate",
}


def text(value: Any) -> str:
    return str(value or "").strip()


def is_placeholder(name: str) -> bool:
    return bool(NOT_ASSIGNED.search(name))


def is_species_level(record: dict[str, Any]) -> bool:
    ranks = record.get("rank", [])

    if not isinstance(ranks, list):
        ranks = [ranks]

    return any(
        text(rank).casefold()
        in {"species", "subspecies", "variety", "form"}
        for rank in ranks
    )


def main() -> None:
    if not NAMES_PATH.exists():
        raise SystemExit(
            f"Missing {NAMES_PATH}; run merge_compile.py first"
        )

    names = json.loads(NAMES_PATH.read_text(encoding="utf-8"))
    if not isinstance(names, dict):
        raise SystemExit("names.json must contain a JSON object")

    cleaned_names: dict[str, dict[str, Any]] = {}
    removed: list[str] = []

    for key, record in names.items():
        displayed = text(
            record.get("name") if isinstance(record, dict) else key
        )

        if is_placeholder(key) or is_placeholder(displayed):
            removed.append(key)
            continue

        cleaned_names[key] = record

    epithets: dict[str, list[str]] = defaultdict(list)

    for key, record in cleaned_names.items():
        if not isinstance(record, dict):
            continue

        if not is_species_level(record):
            continue

        parts = key.split()

        if len(parts) < 2:
            continue

        epithet = re.sub(
            r"[^a-z-]",
            "",
            parts[1].casefold(),
        )

        if (
            not epithet
            or epithet in BLOCKED_EPITHETS
        ):
            continue

        if key not in epithets[epithet]:
            epithets[epithet].append(key)


    cleaned_epithets = {
        epithet: sorted(values)
        for epithet, values in sorted(epithets.items())
    }

    NAMES_PATH.write_text(
        json.dumps(
            cleaned_names,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    EPITHETS_PATH.write_text(
        json.dumps(
            cleaned_epithets,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(
        json.dumps(
            {
                "compiled_names_before": len(names),
                "compiled_names_after": len(cleaned_names),
                "placeholder_names_removed": len(removed),
                "removed_names": removed,
                "epithet_entries_after": len(cleaned_epithets),
                "blocked_epithets_present": [
                    word
                    for word in sorted(BLOCKED_EPITHETS)
                    if word in cleaned_epithets
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if "not" in cleaned_epithets:
        raise SystemExit(
            "FAILED: pseudo-epithet 'not' remains in epithets.json"
        )

    if "assigned" in cleaned_epithets:
        raise SystemExit(
            "FAILED: pseudo-epithet 'assigned' remains in epithets.json"
        )

    print("Compiled placeholder names removed:", len(removed))
    print("Compiled names retained:", len(cleaned_names))
    print("Epithet entries rebuilt:", len(cleaned_epithets))
    print("Audit:", AUDIT_PATH)


if __name__ == "__main__":
    main()