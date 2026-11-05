#!/usr/bin/env python3
"""Remove placeholder classification labels from normalized TAXA-check data.

Usage:
    python build/filter_placeholders.py \
        output/lpsn_normalized.json \
        output/seqcode_normalized.json

Each supplied JSON file is filtered in place. A combined audit is written to:
    output/placeholder_filter_report.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


NOT_ASSIGNED = re.compile(
    r"\bnot\s+assigned\s+to\s+"
    r"(?:domain|kingdom|phylum|class|order|family|genus|species|subspecies)\b",
    re.IGNORECASE,
)

PLACEHOLDER_NAMES = {
    "species",
    "sp",
    "spp",
    "genus",
    "genera",
    "family",
    "families",
    "order",
    "class",
    "phylum",
    "kingdom",
    "domain",
    "strain",
    "isolate",
    "bacterium",
    "bacteria",
    "archaeon",
    "archaea",
    "organism",
    "microorganism",
    "microbe",
    "uncultured",
    "unclassified",
    "unknown",
    "candidate",
}

PLACEHOLDER_PHRASES = (
    "uncultured bacterium",
    "uncultured organism",
    "unclassified bacterium",
    "unclassified organism",
    "unknown bacterium",
    "unknown organism",
    "candidate taxon",
)


def text(value: Any) -> str:
    return str(value or "").strip()


def candidate_values(record: dict[str, Any]) -> list[str]:
    values = [
        record.get("name"),
        record.get("display_name"),
        record.get("full_name"),
        record.get("scientific_name"),
        record.get("taxon_name"),
    ]

    raw = record.get("raw")

    if isinstance(raw, dict):
        values.extend(
            [
                raw.get("name"),
                raw.get("display_name"),
                raw.get("full_name"),
                raw.get("scientific_name"),
                raw.get("taxon_name"),
            ]
        )

    return [
        text(value)
        for value in values
        if text(value)
    ]


def placeholder_reason(record: dict[str, Any]) -> str | None:
    values = candidate_values(record)

    for value in values:
        normalized = re.sub(r"\s+", " ", value).strip().casefold()
        unquoted = normalized.strip('"“”\'‘’')

        if NOT_ASSIGNED.search(value):
            return "not-assigned classification placeholder"

        if unquoted in PLACEHOLDER_NAMES:
            return "generic taxonomic placeholder"

        if any(phrase in normalized for phrase in PLACEHOLDER_PHRASES):
            return "uncultured or unclassified placeholder"

    return None


def process_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Input file does not exist: {path}")

    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise SystemExit(f"Expected a JSON list in {path}")

    retained: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()

    for record in records:
        if not isinstance(record, dict):
            continue

        reason = placeholder_reason(record)

        if reason:
            removed.append(
                {
                    "name": record.get("name"),
                    "display_name": record.get("display_name"),
                    "rank": record.get("rank"),
                    "source": record.get("source"),
                    "record_no": record.get("record_no"),
                    "reason": reason,
                }
            )
            reasons[reason] += 1
        else:
            retained.append(record)

    path.write_text(
        json.dumps(retained, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "file": str(path),
        "records_before": len(records),
        "records_after": len(retained),
        "records_removed": len(removed),
        "reasons": dict(reasons),
        "removed": removed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "files",
        nargs="+",
        help="Normalized JSON files to filter in place",
    )
    parser.add_argument(
        "--report",
        default="output/placeholder_filter_report.json",
    )
    args = parser.parse_args()

    results = [process_file(Path(filename)) for filename in args.files]

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "files_processed": len(results),
                "total_removed": sum(
                    result["records_removed"] for result in results
                ),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    for result in results:
        print(
            f"{result['file']}: "
            f"{result['records_before']:,} -> "
            f"{result['records_after']:,}; "
            f"removed {result['records_removed']:,}"
        )

    print("Audit:", report_path)


if __name__ == "__main__":
    main()
