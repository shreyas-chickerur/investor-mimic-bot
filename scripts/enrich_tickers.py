#!/usr/bin/env python3

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from sqlalchemy import create_engine, text


def _normalize_db_url(db_url: str) -> str:
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return db_url


def _load_cache(path: Path) -> Dict[str, Optional[str]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        return {str(k): (str(v) if v is not None else None) for k, v in data.items()}
    return {}


def _save_cache(path: Path, cache: Dict[str, Optional[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True))


def _openfigi_map_cusips(
    cusips: List[str],
    *,
    api_key: Optional[str],
    timeout_s: int,
    max_retries: int,
    backoff_seconds: float,
) -> Dict[str, Dict[str, Optional[str]]]:
    url = "https://api.openfigi.com/v3/mapping"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key

    jobs = [{"idType": "ID_CUSIP", "idValue": c} for c in cusips]

    attempt = 0
    while True:
        attempt += 1
        resp = requests.post(url, headers=headers, json=jobs, timeout=timeout_s)
        if resp.status_code == 429 and attempt <= max_retries:
            retry_after = resp.headers.get("Retry-After")
            try:
                sleep_s = float(retry_after) if retry_after else float(backoff_seconds) * attempt
            except Exception:
                sleep_s = float(backoff_seconds) * attempt
            time.sleep(max(1.0, sleep_s))
            continue

        resp.raise_for_status()
        break

    out: Dict[str, Dict[str, Optional[str]]] = {}
    payload = resp.json()

    # Response is list aligned to jobs
    for i, item in enumerate(payload):
        cusip = cusips[i]
        data = item.get("data") or []
        ticker = None
        isin = None
        for cand in data:
            t = cand.get("ticker")
            if t:
                ticker = str(t).upper()
            ii = cand.get("isin")
            if ii:
                isin = str(ii).upper()
            if ticker:
                break

        out[cusip] = {"ticker": ticker, "isin": isin}

    return out


def _map_with_adaptive_batching(
    cusips: List[str],
    *,
    api_key: Optional[str],
    timeout_s: int,
    max_retries: int,
    backoff_seconds: float,
) -> Dict[str, Dict[str, Optional[str]]]:
    if not cusips:
        return {}

    try:
        return _openfigi_map_cusips(
            cusips,
            api_key=api_key,
            timeout_s=timeout_s,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )
    except requests.exceptions.HTTPError as e:
        resp = getattr(e, "response", None)
        status = getattr(resp, "status_code", None)
        if status == 413 and len(cusips) > 1:
            mid = max(1, len(cusips) // 2)
            left = _map_with_adaptive_batching(
                cusips[:mid],
                api_key=api_key,
                timeout_s=timeout_s,
                max_retries=max_retries,
                backoff_seconds=backoff_seconds,
            )
            right = _map_with_adaptive_batching(
                cusips[mid:],
                api_key=api_key,
                timeout_s=timeout_s,
                max_retries=max_retries,
                backoff_seconds=backoff_seconds,
            )
            left.update(right)
            return left
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich securities.ticker using OpenFIGI CUSIP->ticker mapping")
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/investorbot"),
    )
    parser.add_argument(
        "--cache-file",
        default="data/ticker_cache/openfigi_cusip_to_ticker.json",
    )
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--sleep-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--backoff-seconds", type=float, default=5.0)
    parser.add_argument(
        "--openfigi-api-key",
        default=os.getenv("OPENFIGI_API_KEY", ""),
        help="Optional OpenFIGI API key (recommended for higher limits)",
    )

    args = parser.parse_args()

    db_url = _normalize_db_url(args.db_url)
    engine = create_engine(db_url)

    cache_path = Path(args.cache_file)
    cache = _load_cache(cache_path)

    # Order by importance: highest aggregate value_usd first.
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT s.security_id, s.cusip
                FROM securities s
                JOIN holdings h ON h.security_id = s.security_id
                WHERE (s.ticker IS NULL OR s.ticker = '')
                  AND s.cusip IS NOT NULL AND s.cusip <> ''
                GROUP BY s.security_id, s.cusip
                ORDER BY SUM(h.value_usd) DESC
                LIMIT :limit
                """
            ),
            {"limit": int(args.limit)},
        ).fetchall()

    if not rows:
        print("No securities found requiring ticker enrichment")
        return 0

    security_by_cusip: Dict[str, List[str]] = {}
    for security_id, cusip in rows:
        cusip = str(cusip).strip()
        if not cusip:
            continue
        security_by_cusip.setdefault(cusip, []).append(str(security_id))

    cusips = sorted(security_by_cusip.keys())

    # cache format: {cusip: ticker or null}
    missing = [c for c in cusips if c not in cache]
    print(f"Candidates: {len(cusips)} cusips")
    print(f"Cache hits: {len(cusips) - len(missing)}")
    print(f"To lookup: {len(missing)}")

    api_key = args.openfigi_api_key.strip() or None

    for i in range(0, len(missing), int(args.batch_size)):
        batch = missing[i : i + int(args.batch_size)]
        if not batch:
            continue

        mapped = _map_with_adaptive_batching(
            batch,
            api_key=api_key,
            timeout_s=int(args.timeout_seconds),
            max_retries=int(args.max_retries),
            backoff_seconds=float(args.backoff_seconds),
        )

        # Persist only ticker in cache for backwards compatibility
        for cusip, info in mapped.items():
            cache[cusip] = info.get("ticker")
        _save_cache(cache_path, cache)

        time.sleep(float(args.sleep_seconds))

    updates: List[Tuple[str, str]] = []
    for cusip, ids in security_by_cusip.items():
        ticker = cache.get(cusip)
        if ticker:
            for security_id in ids:
                updates.append((security_id, ticker))

    if not updates:
        print("No tickers found to update")
        return 0

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE securities
                SET ticker = :ticker
                WHERE security_id = :security_id
                """
            ),
            [{"security_id": sid, "ticker": t} for sid, t in updates],
        )

    print(f"Updated {len(updates)} securities with tickers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
