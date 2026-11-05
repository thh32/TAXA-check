#!/usr/bin/env python3
"""Verify representative compiled names and placeholder exclusions."""

import json
from pathlib import Path


NAMES_PATH = Path(
    "extension/generated/names.json"
)

EPITHETS_PATH = Path(
    "extension/generated/epithets.json"
)

SUPPORTED_MONOMIAL_RANKS = {
    "domain",
    "realm",
    "kingdom",
    "subkingdom",
    "infrakingdom",
    "phylum",
    "subphylum",
    "superphylum",
    "class",
    "subclass",
    "superclass",
    "order",
    "suborder",
    "family",
    "subfamily",
    "tribe",
    "subtribe",
    "genus",
    "subgenus",
}


if not NAMES_PATH.is_file():
    raise SystemExit(
        f"Missing {NAMES_PATH}"
    )

if not EPITHETS_PATH.is_file():
    raise SystemExit(
        f"Missing {EPITHETS_PATH}"
    )


names = json.loads(
    NAMES_PATH.read_text(
        encoding="utf-8"
    )
)

epithets = json.loads(
    EPITHETS_PATH.read_text(
        encoding="utf-8"
    )
)


if not isinstance(names, dict):
    raise SystemExit(
        "FAILED: names.json must "
        "contain a JSON object"
    )

if not isinstance(epithets, dict):
    raise SystemExit(
        "FAILED: epithets.json must "
        "contain a JSON object"
    )


for name in (
    "Firmicutes",
    "Protisticellales",
):
    record = names.get(
        name.casefold()
    )

    print(f"\n{name}:")
    print(
        json.dumps(
            record,
            ensure_ascii=False,
            indent=2,
        )
    )

    if not record:
        raise SystemExit(
            "FAILED: representative name "
            f"{name!r} is absent"
        )

    ranks = record.get(
        "rank",
        [],
    )

    if not isinstance(ranks, list):
        ranks = [ranks]

    if not any(
        str(rank).casefold()
        in SUPPORTED_MONOMIAL_RANKS
        for rank in ranks
    ):
        raise SystemExit(
            f"FAILED: {name!r} has no "
            "supported monomial rank: "
            f"{ranks!r}"
        )


for blocked_epithet in (
    "not",
    "assigned",
):
    candidates = epithets.get(
        blocked_epithet,
        [],
    )

    if candidates:
        raise SystemExit(
            "FAILED: pseudo-epithet "
            f"{blocked_epithet!r} contains "
            f"{len(candidates)} candidates; "
            f"examples: {candidates[:10]!r}"
        )


placeholder_names = [
    key
    for key in names
    if "not assigned to"
    in key.casefold()
]


if placeholder_names:
    raise SystemExit(
        "FAILED: classification "
        "placeholders remain in "
        "names.json: "
        + ", ".join(
            placeholder_names[:10]
        )
    )


print(
    "\nPASS: representative names are "
    "present and placeholder labels "
    "are absent"
)
