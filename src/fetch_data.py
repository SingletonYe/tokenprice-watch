#!/usr/bin/env python3
"""TokenPrice Watch - data collector.

Pulls the public OpenRouter models endpoint (no API key required), normalises it
into a small, stable schema, writes a dated snapshot, and diffs today against
the previous snapshot to produce a machine-readable change log.

Runs with the Python standard library only, so it works unchanged on a laptop,
in CI (GitHub Actions) and inside a sandboxed agent run.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import urllib.error
import urllib.request

API_URL = "https://openrouter.ai/api/v1/models"
USER_AGENT = "TokenPriceWatch/1.0 (+https://github.com/; daily LLM price snapshot)"

# Fields we track for prices. Order matters: it is the snapshot array order.
PRICE_FIELDS = ("pin", "pout", "pcr", "pcw")
# Fields stored in every (lean) snapshot. id first, then these, in order.
LEAN_FIELDS = ("ctx", "pin", "pout", "pcr", "pcw", "iq", "ci")


def log(msg: str) -> None:
    print(f"[fetch] {msg}", flush=True)


def fetch_models(url: str = API_URL, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.load(resp)
    if not isinstance(payload, dict) or "data" not in payload:
        raise ValueError("unexpected payload shape from models API")
    return payload


def num(value) -> str | None:
    """Normalise a source price string into a compact, deterministic string.

    Negative prices are a sentinel used by router endpoints ("the price depends
    on whichever model gets routed to"), not a real price. They are stored as
    absent, and the endpoint is flagged dynamically priced instead.
    """
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f < 0:
        return None
    if f == 0:
        return "0"
    return f"{f:.10g}"


def is_dynamic_price(pricing: dict) -> bool:
    for key in ("prompt", "completion"):
        try:
            if float(pricing.get(key)) < 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def first(*values):
    for v in values:
        if v not in (None, ""):
            return v
    return None


def normalize(payload: dict) -> list[dict]:
    models: list[dict] = []
    for raw in payload.get("data", []):
        mid = (raw.get("id") or "").strip()
        if not mid:
            continue
        if ":" in mid:
            base, variant = mid.split(":", 1)
        else:
            base, variant = mid, ""
        vendor, _, slug = base.partition("/")
        pricing = raw.get("pricing") or {}
        arch = raw.get("architecture") or {}
        top = raw.get("top_provider") or {}
        aa = ((raw.get("benchmarks") or {}).get("artificial_analysis")) or {}
        desc = (raw.get("description") or "").strip()
        desc = " ".join(desc.split())
        models.append(
            {
                "id": mid,
                "base": base,
                "variant": variant,
                "vendor": vendor,
                "slug": slug or base,
                "name": raw.get("name") or mid,
                "created": raw.get("created"),
                "ctx": first(top.get("context_length"), raw.get("context_length")),
                "max_out": top.get("max_completion_tokens"),
                "modality": arch.get("modality"),
                "in_mod": arch.get("input_modalities") or [],
                "out_mod": arch.get("output_modalities") or [],
                "tokenizer": arch.get("tokenizer"),
                "pin": num(pricing.get("prompt")),
                "pout": num(pricing.get("completion")),
                "pcr": num(pricing.get("input_cache_read")),
                "pcw": num(pricing.get("input_cache_write")),
                "pimg": num(pricing.get("image")),
                "paudio": num(pricing.get("audio")),
                "psearch": num(pricing.get("web_search")),
                "iq": aa.get("intelligence_index"),
                "ci": aa.get("coding_index"),
                "agi": aa.get("agentic_index"),
                "reasoning": bool(raw.get("reasoning")),
                "dynamic": is_dynamic_price(pricing),
                "knowledge_cutoff": raw.get("knowledge_cutoff"),
                "hf": raw.get("hugging_face_id"),
                "endpoints": (raw.get("links") or {}).get("details"),
                "desc": desc[:900],
            }
        )
    models.sort(key=lambda m: m["id"])
    return models


def lean(models: list[dict]) -> list[list]:
    """Compact snapshot rows: [id, ctx, pin, pout, pcr, pcw, iq, ci]."""
    rows = []
    for m in models:
        rows.append([m["id"]] + [m.get(f) for f in LEAN_FIELDS])
    return rows


def index_rows(rows: list[list]) -> dict[str, list]:
    return {r[0]: r for r in rows}


def diff(prev_rows: list[list], cur_rows: list[list], name_of: dict[str, str]) -> dict:
    prev, cur = index_rows(prev_rows), index_rows(cur_rows)
    added = sorted(set(cur) - set(prev))
    removed = sorted(set(prev) - set(cur))

    price_changes = []
    # snapshot row layout: 0=id, then LEAN_FIELDS in order
    idx = {name: i + 1 for i, name in enumerate(LEAN_FIELDS)}
    for mid in sorted(set(prev) & set(cur)):
        old, new = prev[mid], cur[mid]
        for field in PRICE_FIELDS:
            i = idx[field]
            a, b = old[i], new[i]
            if a == b:
                continue

            def as_f(x):
                try:
                    return float(x)
                except (TypeError, ValueError):
                    return None

            fa, fb = as_f(a), as_f(b)
            pct = None
            if fa and fb and fa > 0:
                pct = round((fb - fa) / fa * 100, 1)
            price_changes.append(
                {
                    "id": mid,
                    "name": name_of.get(mid, mid),
                    "field": field,
                    "from": a,
                    "to": b,
                    "pct": pct,
                    "direction": "down" if (fa is not None and fb is not None and fb < fa) else "up",
                }
            )

    return {
        "added": [{"id": i, "name": name_of.get(i, i)} for i in added],
        "removed": [{"id": i, "name": name_of.get(i, i)} for i in removed],
        "price_changes": price_changes,
        "counts": {
            "models": len(cur_rows),
            "added": len(added),
            "removed": len(removed),
            "price_changes": len(price_changes),
            "drops": sum(1 for c in price_changes if c["direction"] == "down"),
            "hikes": sum(1 for c in price_changes if c["direction"] == "up"),
        },
    }


def latest_snapshot(root: pathlib.Path, before: str | None = None) -> pathlib.Path | None:
    """Most recent snapshot, optionally the most recent one strictly older than `before`.

    The diff baseline must be the *previous day*, never the current day's own
    snapshot: otherwise a second collection run on the same day reports only the
    movement since the first run instead of the movement since yesterday, and the
    day's published change log silently shrinks.
    """
    snaps = sorted((root / "data" / "snapshots").glob("*.json"))
    if before:
        snaps = [s for s in snaps if s.stem < before]
    return snaps[-1] if snaps else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Collect and snapshot LLM API pricing")
    ap.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parent.parent))
    ap.add_argument("--date", default=None, help="override snapshot date (YYYY-MM-DD), default: today UTC")
    ap.add_argument("--api-url", default=API_URL)
    ap.add_argument("--dry-run", action="store_true", help="fetch and report, write nothing")
    ap.add_argument("--if-missing", action="store_true",
                    help="skip collection entirely when today already has a snapshot; used by both "
                         "daily pipelines so the day's published numbers are written once and every "
                         "later run republishes the same figures instead of shifting them")
    args = ap.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    today = args.date or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    fetched_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    log(f"fetching {args.api_url}")
    payload = fetch_models(args.api_url)
    models = normalize(payload)
    if len(models) < 50:
        log(f"ABORT: only {len(models)} models returned, refusing to overwrite data")
        return 2
    rows = lean(models)
    name_of = {m["id"]: m["name"] for m in models}
    log(f"normalised {len(models)} endpoints / {len({m['base'] for m in models})} distinct models")

    existing_today = root / "data" / "snapshots" / f"{today}.json"
    if args.if_missing and existing_today.exists() and not args.dry_run:
        log(f"{today} already collected ({existing_today.name}); nothing to do "
            "(the day's snapshot is written once, so published figures stay stable)")
        return 0

    prev_path = latest_snapshot(root, before=today)
    prev_rows: list[list] = []
    prev_date = None
    if prev_path:
        prev = json.loads(prev_path.read_text())
        prev_date = prev.get("date")
        prev_rows = prev.get("models", [])
        if prev_date == today and not args.dry_run:
            log(f"snapshot for {today} already exists; it will be replaced")

    changes = diff(prev_rows, rows, name_of) if prev_rows else {
        "added": [], "removed": [], "price_changes": [],
        "counts": {"models": len(rows), "added": 0, "removed": 0, "price_changes": 0, "drops": 0, "hikes": 0},
    }
    changes["baseline"] = prev_date  # None on the very first run
    log(
        "changes vs {prev} (day-to-day baseline): {a} added, {r} removed, {c} price moves ({d} down / {u} up)".format(
            prev=prev_date or "baseline",
            a=changes["counts"]["added"], r=changes["counts"]["removed"],
            c=changes["counts"]["price_changes"], d=changes["counts"]["drops"], u=changes["counts"]["hikes"],
        )
    )
    if args.dry_run:
        log("dry run, nothing written")
        return 0

    (root / "data" / "snapshots").mkdir(parents=True, exist_ok=True)
    (root / "data" / "changes").mkdir(parents=True, exist_ok=True)

    snapshot = {
        "date": today,
        "fetched_at": fetched_at,
        "source": args.api_url,
        "count": len(models),
        "fields": ["id"] + list(LEAN_FIELDS),
        "models": rows,
    }
    snap_path = root / "data" / "snapshots" / f"{today}.json"
    snap_path.write_text(json.dumps(snapshot, separators=(",", ":"), sort_keys=False) + "\n")
    log(f"wrote {snap_path.relative_to(root)} ({snap_path.stat().st_size / 1024:.0f} KiB)")

    # maintain an append-only archive of retired endpoints so old URLs keep working
    archive_path = root / "data" / "archive.json"
    archive = json.loads(archive_path.read_text()) if archive_path.exists() else []
    known = {e["id"] for e in archive}
    prev_rows_by_id = index_rows(prev_rows)
    now_active = {r[0] for r in rows}
    archive = [e for e in archive if e["id"] not in now_active]
    known = {e["id"] for e in archive}
    for gone in changes["removed"]:
        if gone["id"] in known:
            continue
        row = prev_rows_by_id.get(gone["id"], [])
        archive.append({
            "id": gone["id"],
            "name": gone["name"],
            "last_seen": prev_date or today,
            "ctx": row[1] if len(row) > 1 else None,
            "pin": row[2] if len(row) > 2 else None,
            "pout": row[3] if len(row) > 3 else None,
            "pcr": row[4] if len(row) > 4 else None,
            "pcw": row[5] if len(row) > 5 else None,
            "iq": row[6] if len(row) > 6 else None,
            "ci": row[7] if len(row) > 7 else None,
        })
    if archive or archive_path.exists():
        archive_path.write_text(json.dumps(sorted(archive, key=lambda e: e["id"]), indent=1) + "\n")
        log(f"archive holds {len(archive)} retired endpoints")

    latest = {
        "date": today,
        "fetched_at": fetched_at,
        "source": args.api_url,
        "count": len(models),
        "prev_date": prev_date,
        "changes": changes,
        "models": models,
    }
    (root / "data" / "latest.json").write_text(json.dumps(latest, separators=(",", ":")) + "\n")

    chg_path = root / "data" / "changes" / f"{today}.json"
    chg_path.write_text(json.dumps({"date": today, **changes}, indent=1) + "\n")
    log(f"wrote {chg_path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
