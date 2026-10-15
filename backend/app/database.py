import os
import time
import logging
import re
from typing import Optional, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

import pymongo
from pymongo import MongoClient

from .config import (
    DATABASE_URL,
    MONGODB_URI,
    MONGODB_DB_NAME,
    MONGODB_INCIDENTS_COLLECTION,
    sanitize_uri,
)

logger = logging.getLogger(__name__)

# --- SQLAlchemy (SQLite & SQL engines) ---
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency that yields an active database session for SQL / SQLite."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- MongoDB Atlas Connection Management ---
_mongo_client: Optional[MongoClient] = None
_last_ping_result: Optional[Dict[str, Any]] = None
_last_ping_time: float = 0.0
PING_CACHE_TTL = 5.0  # seconds cache for low-overhead status polling


def get_mongodb_uri() -> str:
    from . import config
    return os.getenv("MONGODB_URI", config.MONGODB_URI or "").strip()


def get_mongo_client() -> Optional[MongoClient]:
    """
    Returns an initialized MongoClient instance if MONGODB_URI is configured.
    Configured with strict 5-second timeouts to prevent blocking.
    """
    global _mongo_client
    uri = get_mongodb_uri()
    if not uri:
        return None

    if _mongo_client is None:
        try:
            _mongo_client = MongoClient(
                uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
                appname="RESQ-OS-Core",
            )
        except Exception as e:
            sanitized_err = sanitize_error_message(str(e))
            logger.error("Failed to initialize MongoClient: %s", sanitized_err)
            return None
    return _mongo_client


def reset_mongo_client():
    """Closes and resets the cached MongoClient instance (e.g. after config changes)."""
    global _mongo_client, _last_ping_result, _last_ping_time
    if _mongo_client is not None:
        try:
            _mongo_client.close()
        except Exception:
            pass
    _mongo_client = None
    _last_ping_result = None
    _last_ping_time = 0.0


def sanitize_error_message(err_msg: str) -> str:
    """Removes passwords or user credentials from error strings to prevent secret leakage."""
    if not err_msg:
        return ""
    # Strip passwords in mongodb:// or mongodb+srv://
    sanitized = re.sub(r'(mongodb(?:\+srv)?://[^:]+:)([^@]+)(@)', r'\1*****\3', err_msg)
    # Strip any user:pass pairs in quotes or URLs
    sanitized = re.sub(r'([a-zA-Z0-9_\-\.]+):([a-zA-Z0-9_\-\.]{4,})@', r'\1:*****@', sanitized)
    return sanitized


def ping_mongodb(force: bool = False) -> Dict[str, Any]:
    """
    Verifies live connectivity to the MongoDB Atlas cluster by issuing a real 'ping' command.
    Returns structured results and guarantees no credentials or secret tokens are leaked.
    """
    global _last_ping_result, _last_ping_time
    now = time.time()
    if not force and _last_ping_result is not None and (now - _last_ping_time) < PING_CACHE_TTL:
        return _last_ping_result

    uri = get_mongodb_uri()
    # 1. Check if configured
    if not uri:
        _last_ping_result = {
            "configured": False,
            "connected": False,
            "database_name": MONGODB_DB_NAME,
            "collection": MONGODB_INCIDENTS_COLLECTION,
            "latency_ms": None,
            "error": "MONGODB_URI is not set in backend/.env",
            "target": None,
        }
        _last_ping_time = now
        return _last_ping_result

    client = get_mongo_client()
    if client is None:
        _last_ping_result = {
            "configured": True,
            "connected": False,
            "database_name": MONGODB_DB_NAME,
            "collection": MONGODB_INCIDENTS_COLLECTION,
            "latency_ms": None,
            "error": "Could not create MongoDB client instance",
            "target": sanitize_uri(uri),
        }
        _last_ping_time = now
        return _last_ping_result

    # 2. Execute real database ping
    try:
        t0 = time.perf_counter()
        db = client[MONGODB_DB_NAME]
        db.command("ping")
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        _last_ping_result = {
            "configured": True,
            "connected": True,
            "database_name": MONGODB_DB_NAME,
            "collection": MONGODB_INCIDENTS_COLLECTION,
            "latency_ms": elapsed_ms,
            "error": None,
            "target": sanitize_uri(uri),
        }
    except Exception as e:
        sanitized_err = sanitize_error_message(str(e))
        _last_ping_result = {
            "configured": True,
            "connected": False,
            "database_name": MONGODB_DB_NAME,
            "collection": MONGODB_INCIDENTS_COLLECTION,
            "latency_ms": None,
            "error": sanitized_err,
            "target": sanitize_uri(uri),
        }

    _last_ping_time = now
    return _last_ping_result


def get_active_database_info() -> Dict[str, Any]:
    """
    Truthful assessment of which database backend is actively serving records.
    Never claims MongoDB is active when fallback to SQLite is in effect.
    """
    ping_res = ping_mongodb()
    if ping_res["connected"]:
        return {
            "active_backend": "mongodb",
            "display_name": f"MongoDB Atlas ({MONGODB_DB_NAME})",
            "status": "connected",
            "database_name": MONGODB_DB_NAME,
            "collection": MONGODB_INCIDENTS_COLLECTION,
            "latency_ms": ping_res["latency_ms"],
            "error": None,
            "is_mongodb_connected": True,
        }
    elif ping_res["configured"]:
        return {
            "active_backend": "sqlite",
            "display_name": "SQLite (resq_os.db) [Atlas Disconnected]",
            "status": "fallback_sqlite",
            "database_name": "resq_os.db",
            "collection": None,
            "latency_ms": None,
            "error": ping_res["error"],
            "is_mongodb_connected": False,
        }
    else:
        return {
            "active_backend": "sqlite",
            "display_name": "SQLite (resq_os.db) [Local Default]",
            "status": "sqlite_default",
            "database_name": "resq_os.db",
            "collection": None,
            "latency_ms": None,
            "error": None,
            "is_mongodb_connected": False,
        }
