"""FastAPI backend over DuckDB - HiTeckNuMinfo (No Token & Custom Key version)."""
import json
import os
import threading
import traceback
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from fastapi import FastAPI, Query, Response

# Public dataset link (No HF_TOKEN required if the repo is public)
HF_FILE = "https://huggingface.co/buckets/sarveshmgkvp/UsersData/resolve/users_data.parquet"

# OPTION 1: Custom API Keys (Add any keys you want to allow here)
# If you want it completely open without any key at all, see the search endpoint note below.
VALID_KEYS = {
    "my_custom_secret_key_123": {"user": "admin"},
    "another_key_456": {"user": "client"},
    "jnvvaranasi": {"user": "jnv"}
}

app = FastAPI(title="HiTeckNuMinfo Search API")

# ── Global DuckDB connection ──────────────────────────
_conn = None
_conn_lock = threading.Lock()


def _get_conn() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is not None:
        return _conn

    with _conn_lock:
        if _conn is not None:
            return _conn

        con = duckdb.connect()

        # Extensions
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute("INSTALL parquet; LOAD parquet;")

        # NOTE: HF_TOKEN is removed because the dataset is public. 
        # If your dataset becomes private later, you can re-add token logic here.

        # 🔥 SPEED SETTINGS
        con.execute("SET enable_http_metadata_cache = true;")
        con.execute("SET http_keep_alive = true;")
        con.execute("SET http_timeout = 600000;")
        con.execute("SET threads = 4;")

        # Remote view
        con.execute(f"CREATE OR REPLACE VIEW users AS "
                    f"SELECT * FROM read_parquet('{HF_FILE}')")

        print("🌐 DuckDB ready (remote mode - no token)", flush=True)
        _conn = con
        return con


def _check_key(key: str | None) -> tuple[bool, dict | None]:
    """
    If you want to disable API key requirement entirely, 
    you can make this function always return (True, {}).
    """
    if not key or key not in VALID_KEYS:
        return False, {"message": "Provide correct key", "contact": "@dmforbans"}
    return True, VALID_KEYS[key]


def _pretty(data: dict[str, Any], pretty: bool = True) -> Response:
    if pretty:
        return Response(content=json.dumps(data, indent=2, ensure_ascii=False),
                        media_type="application/json")
    return Response(content=json.dumps(data, ensure_ascii=False),
                    media_type="application/json")


@app.on_event("startup")
async def startup_event():
    try:
        _get_conn()
    except Exception as e:
        print(f"Startup warm-up failed: {e}", flush=True)


@app.get("/")
def home():
    return {"app": "HiTeckNuMinfo Search API", "status": "active", "contact": "@dmforbans"}


@app.get("/health")
def health():
    return {"status": "ok", "protected": False, "mode": "remote"}


@app.get("/search")
async def search(
    mobile: str = Query(..., description="10 digit mobile number"),
    # If you want to remove the key requirement from the URL parameters entirely, 
    # delete `key: str = Query(...)` below and the `_check_key` block inside this function.
    key: str = Query(..., description="API Key"),
    pretty: bool = Query(True),
):
    # Uncomment the next 3 lines if you want to bypass API key checking completely:
    # valid, err = True, None
    
    valid, err = _check_key(key)
    if not valid:
        return Response(content=json.dumps(err, ensure_ascii=False),
                        status_code=403, media_type="application/json")

    m = (mobile or "").strip()
    if not m.isdigit() or len(m) != 10:
        return Response(
            content=json.dumps({
                "message": "Provide valid 10 digit mobile number",
                "contact": "@dmforbans"
            }, ensure_ascii=False),
            status_code=400, media_type="application/json"
        )

    try:
        con = _get_conn()
        sql = "SELECT * FROM users WHERE mobile = ?"
        df = con.execute(sql, [m]).fetchdf()

        if df is None or df.empty:
            return _pretty({
                "query": m, "found": 0, "data": [], "developer": "@dmforbans"
            }, pretty)

        df = df.drop_duplicates()
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.where(pd.notnull(df), None)

        records = df.to_dict(orient="records")
        records = [remove_credits(r) for r in records]

        return _pretty({
            "query": m,
            "found": len(records),
            "data": records,
            "developer": "@dmforbans"
        }, pretty)

    except Exception:
        traceback.print_exc()
        return Response(
            content=json.dumps({
                "query": m, "found": 0, "data": [],
                "developer": "@dmforbans", "message": "Data not found"
            }, ensure_ascii=False),
            status_code=500, media_type="application/json"
        )


def remove_credits(row: dict) -> dict:
    if not isinstance(row, dict):
        return row
    cleaned = {}
    for k, v in row.items():
        lk = str(k).lower()
        if lk in ("credit", "credits", "developer", "author",
                  "created_by", "powered_by", "source", "src",
                  "hiteckgroup", "hiteck"):
            continue
        if isinstance(v, str):
            vl = v.lower()
            if ("hiteckgroup" in vl or "hiteck" in vl or
                "t.me/" in vl or "@hiteck" in vl):
                continue
        cleaned[k] = v
    return cleaned
