"""
RESQ-OS MongoDB Service Layer
Handles MongoDB Atlas persistence for incidents and action audit logs under
the database 'RESQ_OS' and collection 'incidents'.
Provides transparent fallbacks, safe serialization, and zero-secret error reporting.
"""

import datetime
import json
import logging
from typing import List, Dict, Any, Optional
from bson import ObjectId

from .config import MONGODB_DB_NAME, MONGODB_INCIDENTS_COLLECTION
from .database import get_mongo_client, ping_mongodb

logger = logging.getLogger(__name__)


def get_incidents_collection():
    """Returns the incidents collection from MongoDB Atlas RESQ_OS database."""
    client = get_mongo_client()
    if not client:
        return None
    try:
        db = client[MONGODB_DB_NAME]
        return db[MONGODB_INCIDENTS_COLLECTION]
    except Exception as e:
        logger.error("Error accessing MongoDB collection: %s", str(e))
        return None


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to convert MongoDB BSON document into JSON-serializable dict."""
    if not doc:
        return doc
    clean = dict(doc)
    if "_id" in clean:
        clean["mongo_id"] = str(clean["_id"])
        del clean["_id"]
    
    # Ensure id is an integer
    if "id" in clean and clean["id"] is not None:
        try:
            clean["id"] = int(clean["id"])
        except (ValueError, TypeError):
            pass

    # Ensure dates are datetime objects or ISO strings
    for dt_field in ["reported_time", "created_at", "updated_at"]:
        if dt_field in clean and isinstance(clean[dt_field], str):
            try:
                clean[dt_field] = datetime.datetime.fromisoformat(clean[dt_field].replace("Z", "+00:00"))
            except Exception:
                pass

    # Ensure key_risks and recommended_capabilities are lists
    if "key_risks" in clean:
        if isinstance(clean["key_risks"], str):
            try:
                clean["key_risks"] = json.loads(clean["key_risks"])
            except Exception:
                clean["key_risks"] = [clean["key_risks"]] if clean["key_risks"] else []
    else:
        clean["key_risks"] = []

    if "recommended_capabilities" in clean:
        if isinstance(clean["recommended_capabilities"], str):
            try:
                clean["recommended_capabilities"] = json.loads(clean["recommended_capabilities"])
            except Exception:
                clean["recommended_capabilities"] = [clean["recommended_capabilities"]] if clean["recommended_capabilities"] else []
    else:
        clean["recommended_capabilities"] = []

    if "action_logs" not in clean or clean["action_logs"] is None:
        clean["action_logs"] = []

    return clean


def mongo_get_next_incident_id() -> int:
    """Find the next integer ID for an incident in MongoDB collection."""
    coll = get_incidents_collection()
    if coll is None:
        return 1
    try:
        highest = coll.find_one(sort=[("id", -1)])
        if highest and "id" in highest and isinstance(highest["id"], (int, float)):
            return int(highest["id"]) + 1
        # Also check count
        count = coll.count_documents({})
        return count + 1
    except Exception as e:
        logger.error("Error determining next incident ID: %s", str(e))
        return 1


def mongo_create_incident(payload_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates and persists a new incident document into MongoDB Atlas RESQ_OS.incidents.
    """
    coll = get_incidents_collection()
    if coll is None:
        raise RuntimeError("MongoDB Atlas collection is not available")

    new_id = mongo_get_next_incident_id()
    now_dt = datetime.datetime.utcnow()

    # Normalize fields
    key_risks = payload_data.get("key_risks", [])
    if isinstance(key_risks, str):
        try:
            key_risks = json.loads(key_risks)
        except Exception:
            key_risks = [key_risks]

    recommended_caps = payload_data.get("recommended_capabilities", [])
    if isinstance(recommended_caps, str):
        try:
            recommended_caps = json.loads(recommended_caps)
        except Exception:
            recommended_caps = [recommended_caps]

    reported_time = payload_data.get("reported_time") or now_dt
    if isinstance(reported_time, str):
        try:
            reported_time = datetime.datetime.fromisoformat(reported_time.replace("Z", "+00:00"))
        except Exception:
            reported_time = now_dt

    action_logs = payload_data.get("action_logs", [])

    doc = {
        "id": new_id,
        "incident_type": payload_data["incident_type"],
        "location": payload_data["location"],
        "description": payload_data["description"],
        "people_affected": payload_data.get("people_affected", 1),
        "latitude": payload_data.get("latitude"),
        "longitude": payload_data.get("longitude"),
        "reported_time": reported_time,
        "urgency": payload_data.get("urgency", "Medium"),
        "dispatcher_urgency_override": payload_data.get("dispatcher_urgency_override"),
        "urgency_explanation": payload_data.get("urgency_explanation", ""),
        "key_risks": key_risks,
        "recommended_capabilities": recommended_caps,
        "uncertainty_score": payload_data.get("uncertainty_score", 0.2),
        "uncertainty_note": payload_data.get("uncertainty_note"),
        "assessment_method": payload_data.get("assessment_method", "rule_based_fallback"),
        "status": payload_data.get("status", "Reported"),
        "assigned_resource_id": payload_data.get("assigned_resource_id"),
        "created_at": now_dt,
        "updated_at": now_dt,
        "action_logs": action_logs,
    }

    result = coll.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


def mongo_get_incidents(
    status: Optional[str] = None,
    urgency: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve all or filtered incidents from MongoDB Atlas collection."""
    coll = get_incidents_collection()
    if coll is None:
        return []

    query = {}
    if status and status != "All":
        query["status"] = status

    if urgency and urgency != "All":
        query["$or"] = [
            {"dispatcher_urgency_override": urgency},
            {"$and": [{"dispatcher_urgency_override": None}, {"urgency": urgency}]},
        ]

    if search and search.strip():
        q_str = search.strip()
        import re
        regex_pat = re.compile(re.escape(q_str), re.IGNORECASE)
        query["$or"] = query.get("$or", []) + [
            {"location": {"$regex": regex_pat}},
            {"description": {"$regex": regex_pat}},
            {"incident_type": {"$regex": regex_pat}},
        ]

    try:
        cursor = coll.find(query).sort([("reported_time", -1), ("id", -1)])
        return [serialize_doc(doc) for doc in cursor]
    except Exception as e:
        logger.error("Error retrieving incidents from MongoDB: %s", str(e))
        return []


def mongo_get_incident_by_id(incident_id: int) -> Optional[Dict[str, Any]]:
    """Find a single incident document by its integer ID."""
    coll = get_incidents_collection()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"id": incident_id})
        if not doc:
            # Fallback check if passed as string ID or ObjectId
            try:
                doc = coll.find_one({"_id": ObjectId(str(incident_id))})
            except Exception:
                pass
        return serialize_doc(doc) if doc else None
    except Exception as e:
        logger.error("Error retrieving incident #%s from MongoDB: %s", incident_id, str(e))
        return None


def mongo_update_incident_status(
    incident_id: int,
    new_status: str,
    action_log: Optional[Dict[str, Any]] = None,
    assigned_resource_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Updates status and appends action log to incident in MongoDB Atlas."""
    coll = get_incidents_collection()
    if coll is None:
        return None

    now_dt = datetime.datetime.utcnow()
    update_ops: Dict[str, Any] = {
        "$set": {
            "status": new_status,
            "updated_at": now_dt,
        }
    }

    if assigned_resource_id is not None:
        update_ops["$set"]["assigned_resource_id"] = assigned_resource_id

    if action_log:
        if "timestamp" not in action_log or not action_log["timestamp"]:
            action_log["timestamp"] = now_dt
        update_ops["$push"] = {"action_logs": action_log}

    try:
        coll.update_one({"id": incident_id}, update_ops)
        return mongo_get_incident_by_id(incident_id)
    except Exception as e:
        logger.error("Error updating incident status in MongoDB: %s", str(e))
        return None


def mongo_override_urgency(
    incident_id: int,
    urgency_override: str,
    action_log: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Updates dispatcher urgency override and audit log in MongoDB Atlas."""
    coll = get_incidents_collection()
    if coll is None:
        return None

    now_dt = datetime.datetime.utcnow()
    update_ops: Dict[str, Any] = {
        "$set": {
            "dispatcher_urgency_override": urgency_override,
            "updated_at": now_dt,
        }
    }

    if action_log:
        if "timestamp" not in action_log or not action_log["timestamp"]:
            action_log["timestamp"] = now_dt
        update_ops["$push"] = {"action_logs": action_log}

    try:
        coll.update_one({"id": incident_id}, update_ops)
        return mongo_get_incident_by_id(incident_id)
    except Exception as e:
        logger.error("Error overriding urgency in MongoDB: %s", str(e))
        return None


def mongo_assign_resource(
    incident_id: int,
    resource_id: int,
    action_log: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Assigns resource ID, updates status to Assigned, and appends audit log."""
    coll = get_incidents_collection()
    if coll is None:
        return None

    now_dt = datetime.datetime.utcnow()
    update_ops: Dict[str, Any] = {
        "$set": {
            "assigned_resource_id": resource_id,
            "status": "Assigned",
            "updated_at": now_dt,
        }
    }

    if action_log:
        if "timestamp" not in action_log or not action_log["timestamp"]:
            action_log["timestamp"] = now_dt
        update_ops["$push"] = {"action_logs": action_log}

    try:
        coll.update_one({"id": incident_id}, update_ops)
        return mongo_get_incident_by_id(incident_id)
    except Exception as e:
        logger.error("Error assigning resource in MongoDB: %s", str(e))
        return None


def mongo_unassign_resource(
    incident_id: int,
    action_log: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Unassigns resource and updates status to Verified in MongoDB."""
    coll = get_incidents_collection()
    if coll is None:
        return None

    now_dt = datetime.datetime.utcnow()
    update_ops: Dict[str, Any] = {
        "$set": {
            "assigned_resource_id": None,
            "status": "Verified",
            "updated_at": now_dt,
        }
    }

    if action_log:
        if "timestamp" not in action_log or not action_log["timestamp"]:
            action_log["timestamp"] = now_dt
        update_ops["$push"] = {"action_logs": action_log}

    try:
        coll.update_one({"id": incident_id}, update_ops)
        return mongo_get_incident_by_id(incident_id)
    except Exception as e:
        logger.error("Error unassigning resource in MongoDB: %s", str(e))
        return None


def mongo_get_incident_stats() -> Dict[str, int]:
    """Calculates aggregate incident statistics from MongoDB Atlas collection."""
    coll = get_incidents_collection()
    if coll is None:
        return {"total": 0, "critical_high": 0, "active": 0, "resolved": 0}

    try:
        total = coll.count_documents({})
        resolved = coll.count_documents({"status": "Resolved"})
        active = total - resolved
        critical_high = coll.count_documents({
            "$or": [
                {"dispatcher_urgency_override": {"$in": ["Critical", "High"]}},
                {"$and": [
                    {"dispatcher_urgency_override": None},
                    {"urgency": {"$in": ["Critical", "High"]}}
                ]}
            ]
        })
        return {
            "total": total,
            "critical_high": critical_high,
            "active": active,
            "resolved": resolved,
        }
    except Exception as e:
        logger.error("Error computing incident stats from MongoDB: %s", str(e))
        return {"total": 0, "critical_high": 0, "active": 0, "resolved": 0}
