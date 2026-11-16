"""FastAPI backend over DuckDB - HiTeckNuMinfo (No Token & Custom Key version)."""
from contextlib import asynccontextmanager
import json
import threading
import traceback
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from fastapi import FastAPI, Query, Response

HF_FILE = "https://huggingface.co/buckets/sarveshmgkvp/UsersData/resolve/users_data.parquet"

VALID_KEYS = {
    "my_custom_secret_key_123": {"user": "admin"},
    "another_key_456": {"user": "client"},
    "jnvvaranasi": {"user": "jnv"},
}

_conn: duckdb.DuckDBPyConnection | None = None
_conn_lock = threading.Lock()


def _get_base_conn() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is not None:
        return _conn

    with _conn_lock:
        if _conn is not None:
            return _conn

        con = duckdb.connect()
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute("INSTALL parquet; LOAD parquet;")

        # Required for Hugging Face / CDN range requests
        con.execute("SET unsafe_disable_etag_checks = true;")
        con.execute("SET enable_http_metadata_cache = true;")
        con.execute("SET http_keep_alive = true;")
        con.execute("SET http_timeout = 600000;")
        con.execute("SET threads = 4;")

        con.execute(f"""
            CREATE OR REPLACE VIEW users AS
            SELECT * FROM read_parquet('{HF_FILE}')
        """)

        print("DuckDB ready (remote range-query mode)", flush=True)
        _conn = con
        return con


def _get_cursor() -> duckdb.DuckDBPyCursor:
    # Thread-safe lightweight cursor sharing the global HTTP metadata cache
    return _get_base_conn().cursor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        _get_base_conn()
    except Exception as e:
        print(f"Startup warm-up failed: {e}", flush=True)
    yield
    if _conn is not None:
        _conn.close()


app = FastAPI(title="HiTeckNuMinfo Search API", lifespan=lifespan)


def _check_key(key: str | None) -> tuple[bool, dict | None]:
    if not key or key not in VALID_KEYS:
        return False, {"message": "Provide correct key", "contact": "@dmforbans"}
    return True, VALID_KEYS[key]


def _pretty(data: dict[str, Any], pretty: bool = True) -> Response:
    content = json.dumps(data, indent=2 if pretty else None, ensure_ascii=False)
    return Response(content=content, media_type="application/json")


@app.get("/")
def home():
    return {"app": "HiTeckNuMinfo Search API", "status": "active", "contact": "@dmforbans"}


@app.get("/health")
def health():
    return {"status": "ok", "protected": False, "mode": "remote"}


# Use `def` (not `async def`) so blocking DuckDB HTTP range reads run in FastAPI's threadpool
@app.get("/search")
def search(
    mobile: str = Query(..., description="10 digit mobile number"),
    key: str = Query(..., description="API Key"),
    pretty: bool = Query(True),
):
    valid, err = _check_key(key)
    if not valid:
        return Response(
            content=json.dumps(err, ensure_ascii=False),
            status_code=403,
            media_type="application/json",
        )

    m = (mobile or "").strip()
    if not m.isdigit() or len(m) != 10:
        return Response(
            content=json.dumps(
                {"message": "Provide valid 10 digit mobile number", "contact": "@dmforbans"},
                ensure_ascii=False,
            ),
            status_code=400,
            media_type="application/json",
        )

    try:
        with _get_cursor() as cur:
            # NOTE: If `mobile` in your Parquet schema is BIGINT/INT64, pass `int(m)` instead of `m`
            # so Parquet row-group pruning works and doesn't scan the whole file.
            df = cur.execute("SELECT * FROM users WHERE mobile = ?", [m]).fetchdf()

        if df is None or df.empty:
            return _pretty(
                {"query": m, "found": 0, "data": [], "developer": "@dmforbans"},
                pretty,
            )

        df = df.drop_duplicates()
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.where(pd.notnull(df), None)

        records = [remove_credits(r) for r in df.to_dict(orient="records")]

        return _pretty(
            {"query": m, "found": len(records), "data": records, "developer": "@dmforbans"},
            pretty,
        )

    except Exception:
        traceback.print_exc()
        return Response(
            content=json.dumps(
                {
                    "query": m,
                    "found": 0,
                    "data": [],
                    "developer": "@dmforbans",
                    "message": "Internal query error",
                },
                ensure_ascii=False,
            ),
            status_code=500,
            media_type="application/json",
        )


def remove_credits(row: dict) -> dict:
    if not isinstance(row, dict):
        return row
    cleaned = {}
    for k, v in row.items():
        lk = str(k).lower()
        if lk in (
            "credit", "credits", "developer", "author",
            "created_by", "powered_by", "source", "src",
            "hiteckgroup", "hiteck",
        ):
            continue
        if isinstance(v, str):
            vl = v.lower()
            if (
                "hiteckgroup" in vl
                or "hiteck" in vl
                or "t.me/" in vl
                or "@hiteck" in vl
            ):
                continue
        cleaned[k] = v
    return cleaned
