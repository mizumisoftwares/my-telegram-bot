"""FastAPI backend over DuckDB - HiTeckNuMinfo Email Search."""
import json
import os
import threading
import traceback
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from fastapi import FastAPI, Query, Response

# 🔥 Public Dataset Path (No token required)
HF_FILE = "https://huggingface.co/datasets/sarveshmgkvp/HiTeckNuMinfo-bucket/resolve/main/users_data.parquet"

# 🔑 Hardcoded API Key
API_KEY = "dhakkan"
VALID_KEYS = {API_KEY: {}}

app = FastAPI(title="NuMinfo Email Search API")

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
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute("INSTALL parquet; LOAD parquet;")
        
        # 🚀 Speed settings (Metadata Cache)
        con.execute("SET enable_http_metadata_cache = true;")
        con.execute("SET http_keep_alive = true;")
        con.execute("SET http_timeout = 600000;")
        con.execute("SET threads = 4;")
        
        _conn = con
        print("🌐 DuckDB ready (NuMinfo API)", flush=True)
        return con

def _check_key(key: str | None) -> tuple[bool, dict | None]:
    if not key or key not in VALID_KEYS:
        return False, {"message": "Provide correct key", "contact": "@Endexed"}
    return True, VALID_KEYS[key]

def _pretty(data: dict[str, Any], pretty: bool = True) -> Response:
    if pretty:
        return Response(content=json.dumps(data, indent=2, ensure_ascii=False), media_type="application/json")
    return Response(content=json.dumps(data, ensure_ascii=False), media_type="application/json")

@app.on_event("startup")
async def startup_event():
    try:
        _get_conn()
    except Exception as e:
        print(f"Startup failed: {e}", flush=True)

@app.get("/")
def home():
    return {"app": "NuMinfo Email Search API", "status": "active", "contact": "@Endexed"}

@app.get("/search")
async def search(
    key: str = Query(..., description="API Key"),
    email: str = Query(..., description="Search by Email (exact match)"),
    pretty: bool = Query(True)
):
    # 🔑 Key Check
    valid, err = _check_key(key)
    if not valid:
        return Response(content=json.dumps(err, ensure_ascii=False), status_code=403, media_type="application/json")

    # 🔍 Email Check
    if not email or "@" not in email:
        return Response(content=json.dumps({"message": "Provide valid email address", "contact": "@Endexed"}, ensure_ascii=False), status_code=400, media_type="application/json")

    try:
        con = _get_conn()
        
        query = f"SELECT * FROM read_parquet('{HF_FILE}') WHERE email = ? LIMIT 50"
        
        df = con.execute(query, [email.lower().strip()]).fetchdf()

        if df is None or df.empty:
            return _pretty({"found": 0, "data": [], "developer": "@Endexed"}, pretty)

        # NaN values ko null kar do
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.where(pd.notnull(df), None)
        records = df.to_dict(orient="records")

        return _pretty({
            "status": "success",
            "developer": "@Endexed",
            "found": len(records), 
            "data": records, 
            "contact": "@Endexed"
        }, pretty)

    except Exception:
        traceback.print_exc()
        return Response(content=json.dumps({"status": "error", "message": "Data not found", "contact": "@Endexed"}, ensure_ascii=False), status_code=500, media_type="application/json")
