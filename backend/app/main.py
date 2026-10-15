import contextlib
import json
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_

from .config import (
    CORS_ORIGINS,
    OPENAI_API_KEY,
    GEMINI_API_KEY,
    SIMULATION_MODE,
    DATABASE_URL,
    MONGODB_DB_NAME,
    MONGODB_INCIDENTS_COLLECTION,
    sanitize_uri,
)
from .database import (
    engine,
    Base,
    get_db,
    ping_mongodb,
    get_active_database_info,
)
from .models import Incident, Resource, ActionLog
from .seed_data import seed_database_if_empty
from .routers import incidents, resources
from .schemas import DashboardStats
from .mongo_service import (
    mongo_get_incident_stats,
    mongo_create_incident,
    get_incidents_collection,
)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables for local SQLite / resources
    Base.metadata.create_all(bind=engine)
    # Seed SQLite with initial demo scenario if empty
    from .database import SessionLocal
    db = SessionLocal()
    try:
        seed_database_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="RESQ-OS: AI Disaster Response & Rescue Coordination API",
    description="Autonomous AI Disaster Response & Rescue Coordination System — 'Every Signal Matters. Every Response Counts.'",
    version="1.0.0-hackathon-mvp",
    lifespan=lifespan,
)

# Enable CORS for frontend development origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(incidents.router)
app.include_router(resources.router)


@app.get("/", tags=["system"])
def root_info():
    """Root endpoint for status check and API documentation reference."""
    return {
        "service": "RESQ-OS Command Core API",
        "status": "online",
        "tagline": "Every Signal Matters. Every Response Counts.",
        "docs_url": "/docs",
        "health_check": "/api/health",
    }


@app.get("/health", tags=["system"])
def health_alias():
    """Direct /health alias pointing to /api/health for standard platform uptime monitors."""
    return health_check()


@app.get("/api/health", tags=["system"])
def health_check():
    """
    Truthful health check endpoint displaying system state,
    genuine database connection status, and triage engine capability.
    """
    has_llm = bool(OPENAI_API_KEY or GEMINI_API_KEY)
    llm_provider = "OpenAI" if OPENAI_API_KEY else ("Gemini" if GEMINI_API_KEY else "None (Deterministic Rule Fallback Active)")

    db_info = get_active_database_info()
    ping_res = ping_mongodb()

    return {
        "status": "healthy",
        "service": "RESQ-OS Command Core",
        "tagline": "Every Signal Matters. Every Response Counts.",
        "simulation_mode": SIMULATION_MODE,
        "database": {
            "active_backend": db_info["active_backend"],
            "display_name": db_info["display_name"],
            "status": db_info["status"],
            "database_name": db_info["database_name"],
            "collection": db_info["collection"],
            "is_mongodb_connected": db_info["is_mongodb_connected"],
            "latency_ms": db_info["latency_ms"],
            "error": db_info["error"],
            "target": ping_res.get("target"),
        },
        "triage_engine": {
            "llm_configured": has_llm,
            "active_provider": llm_provider,
            "fallback_engine": "Deterministic Heuristic Urgency Scorer",
        },
        "disclaimer": "SIMULATION ONLY: Not for real 911/112 emergency dispatch or certified medical triage.",
    }


@app.get("/api/database/status", tags=["system"])
def get_database_status(force: bool = False):
    """
    Dedicated endpoint reporting whether MongoDB Atlas is genuinely connected,
    ping latency, and active backend without exposing credentials.
    """
    ping_res = ping_mongodb(force=force)
    db_info = get_active_database_info()

    return {
        "active_backend": db_info["active_backend"],
        "display_name": db_info["display_name"],
        "is_mongodb_connected": ping_res["connected"],
        "mongodb_configured": ping_res["configured"],
        "database_name": ping_res["database_name"],
        "collection": ping_res["collection"],
        "latency_ms": ping_res["latency_ms"],
        "target_cluster": ping_res["target"],
        "error": ping_res["error"],
    }


@app.get("/api/dashboard/stats", response_model=DashboardStats, tags=["dashboard"])
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Aggregate statistics for the command center live header."""
    db_info = get_active_database_info()

    if db_info["active_backend"] == "mongodb":
        m_stats = mongo_get_incident_stats()
        total_incidents = m_stats["total"]
        crit_high = m_stats["critical_high"]
        active = m_stats["active"]
        resolved = m_stats["resolved"]
    else:
        total_incidents = db.query(Incident).count()
        crit_high = (
            db.query(Incident)
            .filter(
                or_(
                    Incident.dispatcher_urgency_override.in_(["Critical", "High"]),
                    Incident.urgency.in_(["Critical", "High"]),
                )
            )
            .count()
        )
        resolved = db.query(Incident).filter(Incident.status == "Resolved").count()
        active = total_incidents - resolved

    total_resources = db.query(Resource).count()
    available_res = db.query(Resource).filter(Resource.availability == "Available").count()
    assigned_res = db.query(Resource).filter(Resource.availability == "Assigned").count()

    return DashboardStats(
        total_incidents=total_incidents,
        critical_high_count=crit_high,
        active_incidents=active,
        resolved_incidents=resolved,
        total_resources=total_resources,
        available_resources=available_res,
        assigned_resources=assigned_res,
        simulation_mode=SIMULATION_MODE,
    )


@app.post("/api/database/migrate-to-atlas", tags=["system"])
def migrate_sqlite_to_atlas(confirm: bool = Query(False), db: Session = Depends(get_db)):
    """
    Migration utility: Migrates existing SQLite incidents into MongoDB Atlas RESQ_OS.incidents.
    Requires explicit confirmation to guarantee user approval.
    """
    if not confirm:
        return {
            "status": "pending_approval",
            "message": "Migration requires explicit confirmation. Pass ?confirm=true after reviewing the migration plan.",
            "plan": "Copy all SQLite incident records and their action logs into MongoDB Atlas (database: RESQ_OS, collection: incidents). Preserves existing IDs and timestamps. Does not drop or delete SQLite records.",
        }

    db_info = get_active_database_info()
    if not db_info["is_mongodb_connected"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot migrate: MongoDB Atlas is not connected ({db_info['error'] or 'Connection offline'}).",
        )

    coll = get_incidents_collection()
    if coll is None:
        raise HTTPException(status_code=500, detail="MongoDB collection handle unavailable.")

    # Read SQLite records
    sqlite_incidents = db.query(Incident).order_by(Incident.id).all()
    migrated_count = 0
    skipped_count = 0

    for inc in sqlite_incidents:
        existing = coll.find_one({"id": inc.id})
        if existing:
            skipped_count += 1
            continue

        raw_risks = []
        if inc.key_risks:
            try:
                raw_risks = json.loads(inc.key_risks)
            except Exception:
                raw_risks = [inc.key_risks]

        raw_caps = []
        if inc.recommended_capabilities:
            try:
                raw_caps = json.loads(inc.recommended_capabilities)
            except Exception:
                raw_caps = [inc.recommended_capabilities]

        logs = [
            {
                "id": log.id,
                "incident_id": inc.id,
                "action_type": log.action_type,
                "actor": log.actor,
                "details": log.details,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in inc.action_logs
        ]

        doc = {
            "id": inc.id,
            "incident_type": inc.incident_type,
            "location": inc.location,
            "description": inc.description,
            "people_affected": inc.people_affected or 1,
            "latitude": inc.latitude,
            "longitude": inc.longitude,
            "reported_time": inc.reported_time.isoformat() if inc.reported_time else None,
            "urgency": inc.urgency,
            "dispatcher_urgency_override": inc.dispatcher_urgency_override,
            "urgency_explanation": inc.urgency_explanation,
            "key_risks": raw_risks,
            "recommended_capabilities": raw_caps,
            "uncertainty_score": inc.uncertainty_score,
            "uncertainty_note": inc.uncertainty_note,
            "assessment_method": inc.assessment_method,
            "status": inc.status,
            "assigned_resource_id": inc.assigned_resource_id,
            "created_at": inc.created_at.isoformat() if inc.created_at else None,
            "updated_at": inc.updated_at.isoformat() if inc.updated_at else None,
            "action_logs": logs,
        }
        coll.insert_one(doc)
        migrated_count += 1

    return {
        "status": "success",
        "migrated_count": migrated_count,
        "skipped_existing_count": skipped_count,
        "database": MONGODB_DB_NAME,
        "collection": MONGODB_INCIDENTS_COLLECTION,
        "message": f"Successfully migrated {migrated_count} incidents to MongoDB Atlas ({MONGODB_DB_NAME}.{MONGODB_INCIDENTS_COLLECTION}).",
    }
