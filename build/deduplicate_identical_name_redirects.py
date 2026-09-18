#!/usr/bin/env python3
"""Remove redundant same-spelling redirects from compiled TAXA-check data.

Place in the existing project's build/ directory and run after merge_compile.py.

Example corrected:
  Enterobacteriaceae [correct name]
  Enterobacteriaceae [synonym -> Enterobacteriaceae]
becomes one displayed LPSN history, classified as a current LPSN name.

Genuine changes such as Firmicutes -> Bacillota are retained unchanged.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def normalize_name(value: Any) -> str:
    """Normalize harmless display differences for name comparison."""
    text = str(value or "")
    text = text.strip().strip('"“”\'‘’')
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\s,;:.]+$", "", text)
    return text.casefold()


def is_lpsn(history: dict[str, Any]) -> bool:
    return history.get("source") == "LPSN"


def is_explicitly_current(history: dict[str, Any]) -> bool:
    status = str(history.get("status") or "").casefold()
    return (
        "correct name" in status
        or "accepted name" in status
        or "current name" in status
    ) and not any(
        marker in status
        for marker in (
            "not correct name",
            "synonym",
            "superseded",
            "rejected",
            "taxonomically suspended",
            "taxonomic suspension",
        )
    )


def is_same_spelling_redirect(
    history: dict[str, Any],
    displayed_name: str,
) -> bool:
    if not is_lpsn(history):
        return False

    status = str(history.get("status") or "").casefold()
    redirected = history.get("superseded") or any(
        marker in status
        for marker in (
            "synonym",
            "superseded",
            "redirected",
            "not correct name",
        )
    )

    if not redirected:
        return False

    correct_name = history.get("correct_name") or history.get("current_name")
    return bool(
        correct_name
        and normalize_name(correct_name) == normalize_name(displayed_name)
    )


def recalculate_state(record: dict[str, Any]) -> str:
    histories = record.get("history", [])

    lpsn = [history for history in histories if is_lpsn(history)]
    seqcode = [
        history
        for history in histories
        if history.get("source") == "SeqCode Registry"
    ]

    # Preserve explicit unresolved/conflicting states when genuine differing
    # treatments remain.
    genuine_superseded = [
        history
        for history in histories
        if history.get("superseded")
        and normalize_name(
            history.get("correct_name") or history.get("current_name")
        )
        not in {"", normalize_name(record.get("name"))}
    ]

    correct_targets = {
        normalize_name(
            history.get("correct_name") or history.get("current_name")
        )
        for history in genuine_superseded
        if history.get("correct_name") or history.get("current_name")
    }

    ranks = {
        str(history.get("rank") or "").casefold()
        for history in histories
        if history.get("rank")
    }

    if len(correct_targets) > 1 or len(ranks) > 1:
        return "conflict"

    if genuine_superseded:
        return "superseded"

    if lpsn and seqcode:
        return "both"

    if seqcode:
        valid_seqcode = any(
            "valid (seqcode)" in str(history.get("status") or "").casefold()
            or str(history.get("validly_published") or "").casefold()
            in {"true", "yes", "seqcode"}
            for history in seqcode
        )
        return "seqcode" if valid_seqcode else "seqcode-unverified"

    return "lpsn"


def process_record(record: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    displayed_name = str(record.get("name") or "")
    histories = record.get("history")

    if not isinstance(histories, list):
        return record, []

    has_current_lpsn = any(
        is_lpsn(history) and is_explicitly_current(history)
        for history in histories
    )

    # Only suppress a same-spelling synonym if an explicit current LPSN record
    # for the same written name is also present. This avoids hiding unresolved
    # historical information when no current record exists.
    if not has_current_lpsn:
        return record, []

    kept = []
    removed = []

    for history in histories:
        if is_same_spelling_redirect(history, displayed_name):
            removed.append(history)
        else:
            kept.append(history)

    if not removed:
        return record, []

    record["history"] = kept
    record["state"] = recalculate_state(record)
    return record, removed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database",
        default="extension/generated/names.json",
        help="Compiled TAXA-check names database",
    )
    parser.add_argument(
        "--audit",
        default="output/identical_name_redirects_removed.json",
        help="Audit report path",
    )
    args = parser.parse_args()

    database_path = Path(args.database)
    audit_path = Path(args.audit)

    if not database_path.exists():
        raise SystemExit(
            f"Missing {database_path}. Run python build/merge_compile.py first."
        )

    database = json.loads(database_path.read_text(encoding="utf-8"))

    audit_records = []

    for key, original_record in database.items():
        record, removed = process_record(original_record)
        database[key] = record

        if removed:
            audit_records.append(
                {
                    "name": record.get("name"),
                    "final_state": record.get("state"),
                    "removed_count": len(removed),
                    "removed_histories": removed,
                }
            )

    database_path.write_text(
        json.dumps(database, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(
            {
                "records_changed": len(audit_records),
                "records": audit_records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("Names with redundant same-spelling redirects removed:", len(audit_records))
    print("Audit:", audit_path)

    enterobacteriaceae = database.get("enterobacteriaceae")
    if enterobacteriaceae:
        print(
            "Enterobacteriaceae final state:",
            enterobacteriaceae.get("state"),
        )
        remaining_lpsn = [
            history
            for history in enterobacteriaceae.get("history", [])
            if history.get("source") == "LPSN"
        ]
        print(
            "Enterobacteriaceae remaining LPSN histories:",
            len(remaining_lpsn),
        )


if __name__ == "__main__":
    main()
