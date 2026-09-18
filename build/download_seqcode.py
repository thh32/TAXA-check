#!/usr/bin/env python3
"""Resumable SeqCode downloader tolerant of broken individual API records.

A persistent 4xx/5xx response for one /names/{id}.json record is logged and
skipped. It never aborts the full database build. Failed IDs are kept in a
separate audit file and can be retried later with --retry-failed.
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from urllib.parse import urljoin
import requests

BASE = "https://api.seqco.de/v1/"

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="output/seqcode_names_raw.jsonl")
    p.add_argument("--state", default="output/seqcode_state.json")
    p.add_argument("--failures", default="output/seqcode_failed_records.json")
    p.add_argument("--timeout", type=float, default=90)
    p.add_argument("--retries", type=int, default=5)
    p.add_argument("--delay", type=float, default=0.15)
    p.add_argument("--restart", action="store_true")
    p.add_argument("--retry-failed", action="store_true")
    return p.parse_args()

def atomic_json(path: Path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)

def response_values(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("values", "results", "items", "data", "names"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []

def item_id(item):
    if not isinstance(item, dict):
        return None
    for key in ("id", "name_id", "name-id"):
        if item.get(key) not in (None, ""):
            return str(item[key])
    return None

def request_json(session, url, params, timeout, retries):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json(), None
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(min(30, 2 ** attempt))
    status = getattr(getattr(last_error, "response", None), "status_code", None)
    return None, {"status": status, "error": repr(last_error), "url": url}

def unwrap_detail(payload):
    if not isinstance(payload, dict):
        return None
    for key in ("value", "data", "result"):
        if isinstance(payload.get(key), dict):
            return payload[key]
    return payload

def main():
    args = parse_args()
    output = Path(args.output)
    state_path = Path(args.state)
    failures_path = Path(args.failures)
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.restart:
        output.unlink(missing_ok=True)
        state_path.unlink(missing_ok=True)
        failures_path.unlink(missing_ok=True)

    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {
        "list_page": 1,
        "listed": False,
        "ids": [],
        "completed_ids": [],
        "failed_ids": []
    }
    failures = json.loads(failures_path.read_text(encoding="utf-8")) if failures_path.exists() else {}

    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "User-Agent": "TAXA-check SeqCode builder/2.3"
    })

    # Stage 1: enumerate all name IDs.
    if not state.get("listed", False):
        ids = set(map(str, state.get("ids", [])))
        page = int(state.get("list_page", 1))
        while True:
            payload, error = request_json(
                session, urljoin(BASE, "names.json"), {"page": page},
                args.timeout, args.retries
            )
            if error:
                raise SystemExit(f"SeqCode list page {page} failed after retries: {error}")
            items = response_values(payload)
            if not items:
                state["listed"] = True
                break
            before = len(ids)
            for item in items:
                identifier = item_id(item)
                if identifier is not None:
                    ids.add(identifier)
            print(f"SeqCode list page {page}: {len(items)} rows, {len(ids)-before} new IDs")
            state.update({"ids": sorted(ids), "list_page": page + 1})
            atomic_json(state_path, state)
            total_pages = None
            if isinstance(payload, dict):
                total_pages = payload.get("pages") or payload.get("total_pages") or payload.get("last_page")
            if isinstance(total_pages, int) and page >= total_pages:
                state["listed"] = True
                break
            page += 1
            time.sleep(args.delay)
        state["ids"] = sorted(ids)
        atomic_json(state_path, state)

    completed = set(map(str, state.get("completed_ids", [])))
    previously_failed = set(map(str, state.get("failed_ids", [])))
    if args.retry_failed:
        previously_failed.clear()

    # Stage 2: fetch full detail records. One broken record cannot abort the run.
    with output.open("a", encoding="utf-8") as handle:
        total = len(state.get("ids", []))
        for position, identifier in enumerate(state.get("ids", []), 1):
            identifier = str(identifier)
            if identifier in completed or identifier in previously_failed:
                continue

            detail_url = urljoin(BASE, f"names/{identifier}.json")
            payload, error = request_json(
                session, detail_url, None, args.timeout, args.retries
            )
            if error:
                failures[identifier] = {
                    **error,
                    "id": identifier,
                    "attempted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
                previously_failed.add(identifier)
                state["failed_ids"] = sorted(previously_failed)
                atomic_json(failures_path, failures)
                atomic_json(state_path, state)
                print(f"WARNING: skipped SeqCode record {identifier}: HTTP {error.get('status') or 'error'}")
                continue

            detail = unwrap_detail(payload)
            if not isinstance(detail, dict):
                failures[identifier] = {
                    "id": identifier,
                    "status": None,
                    "error": "Detail endpoint returned no record object",
                    "url": detail_url
                }
                previously_failed.add(identifier)
                state["failed_ids"] = sorted(previously_failed)
                atomic_json(failures_path, failures)
                atomic_json(state_path, state)
                print(f"WARNING: skipped malformed SeqCode record {identifier}")
                continue

            detail.setdefault("id", int(identifier) if identifier.isdigit() else identifier)
            handle.write(json.dumps(detail, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            completed.add(identifier)
            failures.pop(identifier, None)
            state["completed_ids"] = sorted(completed)
            state["failed_ids"] = sorted(previously_failed - completed)
            if position % 25 == 0:
                atomic_json(state_path, state)
                atomic_json(failures_path, failures)
                print(f"SeqCode details: {len(completed)}/{total}; failed: {len(state['failed_ids'])}")
            time.sleep(args.delay)

    atomic_json(state_path, state)
    atomic_json(failures_path, failures)
    print(f"SeqCode detail download complete: {len(completed)} records; {len(state['failed_ids'])} skipped failures")
    print(f"Failure audit: {failures_path}")

if __name__ == "__main__":
    main()
