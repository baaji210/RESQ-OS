import json
import datetime
from typing import List, Optional, Union, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db, get_active_database_info
from ..models import Incident, Resource, ActionLog
from ..schemas import (
    IncidentCreate,
    IncidentResponse,
    IncidentStatusUpdate,
    IncidentUrgencyOverride,
    ResourceResponse,
    ActionLogResponse,
    PrioritizationResponse,
)
from ..triage_engine import evaluate_incident_triage
from ..geocoding import geocode_address
from ..seed_data import seed_database_if_empty, DEMO_RESOURCES, DEMO_INCIDENTS
from ..prioritizer import prioritize_all_incidents
from ..mongo_service import (
    mongo_create_incident,
    mongo_get_incidents,
    mongo_get_incident_by_id,
    mongo_update_incident_status,
    mongo_override_urgency,
)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("/geocode")
def geocode_address_endpoint(q: str = Query(..., min_length=2)):
    """Geocode an address to lat/lng using OpenStreetMap Nominatim with caching."""
    lat, lng, display_name = geocode_address(q)
    return {
        "found": lat is not None and lng is not None,
        "latitude": lat,
        "longitude": lng,
        "display_name": display_name,
        "query": q,
    }


def incident_to_response(inc: Union[Incident, Dict[str, Any]], db: Optional[Session] = None) -> IncidentResponse:
    """
    Unified helper to convert either an Incident SQLAlchemy model or
    a MongoDB Atlas dictionary record to a standardized Pydantic IncidentResponse.
    """
    # 1. Normalize fields across SQLAlchemy Model and MongoDB Document
    if isinstance(inc, dict):
        inc_id = int(inc.get("id", 0))
        inc_type = inc.get("incident_type", "")
        location = inc.get("location", "")
        description = inc.get("description", "")
        people_affected = inc.get("people_affected", 1)
        latitude = inc.get("latitude")
        longitude = inc.get("longitude")
        reported_time = inc.get("reported_time")
        if isinstance(reported_time, str):
            try:
                reported_time = datetime.datetime.fromisoformat(reported_time.replace("Z", "+00:00"))
            except Exception:
                reported_time = datetime.datetime.utcnow()

        urgency = inc.get("urgency", "Medium")
        dispatcher_urgency_override = inc.get("dispatcher_urgency_override")
        urgency_explanation = inc.get("urgency_explanation")
        
        raw_risks = inc.get("key_risks", [])
        if isinstance(raw_risks, str):
            try:
                key_risks_list = json.loads(raw_risks)
            except Exception:
                key_risks_list = [raw_risks]
        elif isinstance(raw_risks, list):
            key_risks_list = raw_risks
        else:
            key_risks_list = []

        raw_caps = inc.get("recommended_capabilities", [])
        if isinstance(raw_caps, str):
            try:
                capabilities_list = json.loads(raw_caps)
            except Exception:
                capabilities_list = [raw_caps]
        elif isinstance(raw_caps, list):
            capabilities_list = raw_caps
        else:
            capabilities_list = []

        uncertainty_score = inc.get("uncertainty_score") or 0.2
        uncertainty_note = inc.get("uncertainty_note")
        assessment_method = inc.get("assessment_method") or "rule_based_fallback"
        status = inc.get("status", "Reported")
        assigned_resource_id = inc.get("assigned_resource_id")

        created_at = inc.get("created_at") or datetime.datetime.utcnow()
        if isinstance(created_at, str):
            try:
                created_at = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except Exception:
                created_at = datetime.datetime.utcnow()

        updated_at = inc.get("updated_at") or datetime.datetime.utcnow()
        if isinstance(updated_at, str):
            try:
                updated_at = datetime.datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except Exception:
                updated_at = datetime.datetime.utcnow()

        # Action logs from MongoDB embedded array
        action_logs_resp = []
        for idx, log in enumerate(inc.get("action_logs", [])):
            log_time = log.get("timestamp") or datetime.datetime.utcnow()
            if isinstance(log_time, str):
                try:
                    log_time = datetime.datetime.fromisoformat(log_time.replace("Z", "+00:00"))
                except Exception:
                    log_time = datetime.datetime.utcnow()
            action_logs_resp.append(
                ActionLogResponse(
                    id=log.get("id") or (idx + 1),
                    incident_id=inc_id,
                    action_type=log.get("action_type", "EVENT"),
                    actor=log.get("actor", "System"),
                    details=log.get("details", ""),
                    timestamp=log_time,
                )
            )

        # Lookup assigned resource in fleet if assigned
        assigned_res = None
        if assigned_resource_id and db is not None:
            res_model = db.query(Resource).filter(Resource.id == assigned_resource_id).first()
            if res_model:
                res_caps = []
                if res_model.capabilities:
                    try:
                        res_caps = json.loads(res_model.capabilities)
                    except Exception:
                        res_caps = []
                assigned_res = ResourceResponse(
                    id=res_model.id,
                    name=res_model.name,
                    resource_type=res_model.resource_type,
                    capabilities=res_caps,
                    simulated_lat=res_model.simulated_lat,
                    simulated_lng=res_model.simulated_lng,
                    simulated_location_name=res_model.simulated_location_name,
                    availability=res_model.availability,
                    current_incident_id=res_model.current_incident_id,
                    capacity=res_model.capacity,
                    contact_callsign=res_model.contact_callsign,
                    created_at=res_model.created_at,
                )
    else:
        # Standard SQLAlchemy Incident instance
        inc_id = inc.id
        inc_type = inc.incident_type
        location = inc.location
        description = inc.description
        people_affected = inc.people_affected
        latitude = inc.latitude
        longitude = inc.longitude
        reported_time = inc.reported_time
        urgency = inc.urgency
        dispatcher_urgency_override = inc.dispatcher_urgency_override
        urgency_explanation = inc.urgency_explanation
        
        key_risks_list = []
        if inc.key_risks:
            try:
                key_risks_list = json.loads(inc.key_risks)
            except Exception:
                key_risks_list = [inc.key_risks]

        capabilities_list = []
        if inc.recommended_capabilities:
            try:
                capabilities_list = json.loads(inc.recommended_capabilities)
            except Exception:
                capabilities_list = [inc.recommended_capabilities]

        uncertainty_score = inc.uncertainty_score or 0.2
        uncertainty_note = inc.uncertainty_note
        assessment_method = inc.assessment_method or "rule_based_fallback"
        status = inc.status
        assigned_resource_id = inc.assigned_resource_id
        created_at = inc.created_at
        updated_at = inc.updated_at

        assigned_res = None
        if inc.assigned_resource:
            res_caps = []
            if inc.assigned_resource.capabilities:
                try:
                    res_caps = json.loads(inc.assigned_resource.capabilities)
                except Exception:
                    res_caps = []
            assigned_res = ResourceResponse(
                id=inc.assigned_resource.id,
                name=inc.assigned_resource.name,
                resource_type=inc.assigned_resource.resource_type,
                capabilities=res_caps,
                simulated_lat=inc.assigned_resource.simulated_lat,
                simulated_lng=inc.assigned_resource.simulated_lng,
                simulated_location_name=inc.assigned_resource.simulated_location_name,
                availability=inc.assigned_resource.availability,
                current_incident_id=inc.assigned_resource.current_incident_id,
                capacity=inc.assigned_resource.capacity,
                contact_callsign=inc.assigned_resource.contact_callsign,
                created_at=inc.assigned_resource.created_at,
            )

        action_logs_resp = [
            ActionLogResponse(
                id=log.id,
                incident_id=log.incident_id,
                action_type=log.action_type,
                actor=log.actor,
                details=log.details,
                timestamp=log.timestamp,
            )
            for log in (inc.action_logs or [])
        ]

    effective_urg = dispatcher_urgency_override or urgency

    # Derive missing information
    missing_info = []
    if latitude is None or longitude is None:
        missing_info.append("Exact GPS coordinates not confirmed (manual address only; verify landmark coordinates)")
    if (people_affected or 0) <= 1:
        missing_info.append("Specific count of trapped, injured, or vulnerable individuals unconfirmed")
    if len((description or "").split()) < 8:
        missing_info.append("Detailed physical scene dimensions and ingress route accessibility")
    inc_type_lower = (inc_type or "").lower()
    if any(k in inc_type_lower for k in ["flood", "water"]):
        missing_info.append("Current flood water depth, current velocity, and rate of rise")
    elif any(k in inc_type_lower for k in ["fire", "smoke"]):
        missing_info.append("Structure occupancy status and presence of hazardous/combustible accelerants")
    elif any(k in inc_type_lower for k in ["medical"]):
        missing_info.append("Patient vital signs, consciousness level, and immediate airway stability")
    elif any(k in inc_type_lower for k in ["collapse", "earthquake"]):
        missing_info.append("Secondary collapse hazards and void space survivability indicators")
    elif any(k in inc_type_lower for k in ["chemical", "hazmat"]):
        missing_info.append("Chemical UN number / SDS identification and downwind plume dispersion direction")

    # Derive recommended next action
    if status == "Reported":
        if any(k in inc_type_lower for k in ["flood", "water"]):
            next_action = "Review flood water ingress telemetry and approve swiftwater rescue boat deployment in Dispatcher Console."
        elif any(k in inc_type_lower for k in ["fire", "smoke"]):
            next_action = "Establish perimeter safety buffer and authorize primary fire suppression unit dispatch."
        elif any(k in inc_type_lower for k in ["medical"]):
            next_action = "Authorize Advanced Life Support (ALS) paramedic ambulance deployment with rapid transit priority."
        elif any(k in inc_type_lower for k in ["collapse", "earthquake"]):
            next_action = "Authorize Heavy Urban Search & Rescue and K-9 team deployment for structural breach extraction."
        elif any(k in inc_type_lower for k in ["chemical", "hazmat"]):
            next_action = "Enforce exclusion perimeter and approve HAZMAT containment unit deployment."
        else:
            next_action = "Dispatcher review required: Authorize qualified simulated rescue asset deployment."
    elif status in ("Assigned", "Accepted"):
        unit_callsign = assigned_res.contact_callsign if assigned_res else "Assigned Unit"
        next_action = f"{unit_callsign} must confirm mission order, verify ingress route navigation, and report En Route."
    elif status == "En Route":
        unit_callsign = assigned_res.contact_callsign if assigned_res else "Unit"
        next_action = f"{unit_callsign} in transit. Establish incident ground tactical frequency and report on-scene arrival."
    elif status == "Arrived":
        next_action = "Execute rapid tactical triage on scene, initiate victim extrication, and transmit regular sitreps."
    elif status == "Resolved":
        next_action = "Incident resolved. Finalize operational debrief and return unit to Available standby."
    else:
        next_action = "Monitor situation telemetry and coordinate with incident command."

    return IncidentResponse(
        id=inc_id,
        incident_type=inc_type,
        location=location,
        description=description,
        people_affected=people_affected,
        latitude=latitude,
        longitude=longitude,
        reported_time=reported_time,
        urgency=urgency,
        dispatcher_urgency_override=dispatcher_urgency_override,
        effective_urgency=effective_urg,
        urgency_explanation=urgency_explanation,
        key_risks=key_risks_list,
        recommended_capabilities=capabilities_list,
        uncertainty_score=uncertainty_score,
        uncertainty_note=uncertainty_note,
        assessment_method=assessment_method,
        recommended_next_action=next_action,
        missing_information=missing_info,
        status=status,
        assigned_resource_id=assigned_resource_id,
        assigned_resource=assigned_res,
        created_at=created_at,
        updated_at=updated_at,
        action_logs=action_logs_resp,
    )


@router.get("", response_model=List[IncidentResponse])
def get_incidents(
    status: Optional[str] = None,
    urgency: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Retrieve list of incidents with optional filtering and search.
    Reads from MongoDB Atlas when connected; falls back to SQLite seamlessly.
    """
    db_info = get_active_database_info()
    if db_info["active_backend"] == "mongodb":
        mongo_docs = mongo_get_incidents(status=status, urgency=urgency, search=search)
        return [incident_to_response(doc, db=db) for doc in mongo_docs]

    # SQLite query fallback
    query = db.query(Incident)

    if status and status != "All":
        query = query.filter(Incident.status == status)

    if urgency and urgency != "All":
        query = query.filter(
            or_(
                Incident.dispatcher_urgency_override == urgency,
                Incident.urgency == urgency,
            )
        )

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Incident.location.ilike(search_filter),
                Incident.description.ilike(search_filter),
                Incident.incident_type.ilike(search_filter),
            )
        )

    incidents = query.order_by(Incident.reported_time.desc(), Incident.id.desc()).all()
    return [incident_to_response(i, db=db) for i in incidents]


@router.post("", response_model=IncidentResponse, status_code=201)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)):
    """
    Intake a new emergency incident:
    - Runs AI / Rule-based triage engine
    - Computes urgency, key risks, capabilities, and uncertainty score
    - Saves incident to the active database (MongoDB Atlas RESQ_OS.incidents or SQLite)
    - Records audit log entry
    """
    reported_time = payload.reported_time or datetime.datetime.utcnow()

    # Determine coordinates
    latitude = payload.latitude
    longitude = payload.longitude
    geocode_info = None

    if latitude is None or longitude is None:
        geo_lat, geo_lng, geo_name = geocode_address(payload.location)
        if geo_lat is not None and geo_lng is not None:
            latitude = geo_lat
            longitude = geo_lng
            geocode_info = f"Address successfully geocoded to [{latitude}, {longitude}] ({geo_name})."
        else:
            geocode_info = f"Map location coordinates could not be resolved from address '{payload.location}'. Plotted location unavailable."
    else:
        geocode_info = f"Using manual/preset coordinates [{latitude}, {longitude}]."

    triage = evaluate_incident_triage(
        incident_type=payload.incident_type,
        location=payload.location,
        description=payload.description,
        people_affected=payload.people_affected,
        latitude=latitude,
        longitude=longitude,
    )

    db_info = get_active_database_info()
    if db_info["active_backend"] == "mongodb":
        # Save directly to MongoDB Atlas
        action_log_entry = {
            "id": 1,
            "action_type": "CREATED",
            "actor": "Intake Dispatch Portal",
            "details": f"Incident registered in MongoDB Atlas ({db_info['database_name']}.{db_info['collection']}). Triage assessed as [{triage['urgency']}] via {triage['assessment_method'].replace('_', ' ').title()}. {geocode_info}",
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

        doc_data = {
            "incident_type": payload.incident_type,
            "location": payload.location,
            "description": payload.description,
            "people_affected": payload.people_affected,
            "latitude": latitude,
            "longitude": longitude,
            "reported_time": reported_time,
            "urgency": triage["urgency"],
            "urgency_explanation": triage["urgency_explanation"],
            "key_risks": triage["key_risks"],
            "recommended_capabilities": triage["recommended_capabilities"],
            "uncertainty_score": triage["uncertainty_score"],
            "uncertainty_note": triage["uncertainty_note"],
            "assessment_method": triage["assessment_method"],
            "status": "Reported",
            "assigned_resource_id": None,
            "action_logs": [action_log_entry],
        }

        created_doc = mongo_create_incident(doc_data)
        return incident_to_response(created_doc, db=db)

    # SQLite persistence
    inc = Incident(
        incident_type=payload.incident_type,
        location=payload.location,
        description=payload.description,
        people_affected=payload.people_affected,
        latitude=latitude,
        longitude=longitude,
        reported_time=reported_time,
        urgency=triage["urgency"],
        urgency_explanation=triage["urgency_explanation"],
        key_risks=json.dumps(triage["key_risks"]),
        recommended_capabilities=json.dumps(triage["recommended_capabilities"]),
        uncertainty_score=triage["uncertainty_score"],
        uncertainty_note=triage["uncertainty_note"],
        assessment_method=triage["assessment_method"],
        status="Reported",
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)

    # Add Action Log
    log_details = f"Incident registered. Triage assessed as [{triage['urgency']}] via {triage['assessment_method'].replace('_', ' ').title()}. {geocode_info}"
    log = ActionLog(
        incident_id=inc.id,
        action_type="CREATED",
        actor="Intake Dispatch Portal",
        details=log_details,
    )
    db.add(log)
    db.commit()
    db.refresh(inc)

    return incident_to_response(inc, db=db)


@router.get("/prioritize", response_model=PrioritizationResponse)
@router.post("/prioritize", response_model=PrioritizationResponse)
def get_prioritized_incidents_endpoint(db: Session = Depends(get_db)):
    """
    AI / Rule-Based Rescue Prioritizer endpoint:
    Analyzes all reported emergency incidents across the active database,
    evaluates immediate life danger, casualties, worsening hazards,
    recommends order of attention, and suggests suitable available rescue assets.
    """
    return prioritize_all_incidents(db)


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    """Get single incident by ID with full audit logs and assigned resource."""
    db_info = get_active_database_info()
    if db_info["active_backend"] == "mongodb":
        doc = mongo_get_incident_by_id(incident_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Incident #{incident_id} not found in MongoDB Atlas")
        return incident_to_response(doc, db=db)

    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident_to_response(inc, db=db)


@router.patch("/{incident_id}/status", response_model=IncidentResponse)
def update_incident_status(
    incident_id: int,
    payload: IncidentStatusUpdate,
    db: Session = Depends(get_db),
):
    """
    Update incident status workflow:
    Reported -> Verified -> Assigned -> Accepted -> En Route -> Arrived -> Resolved
    """
    valid_statuses = ["Reported", "Verified", "Assigned", "Accepted", "En Route", "Arrived", "Resolved"]
    if payload.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{payload.status}'. Allowed: {', '.join(valid_statuses)}",
        )

    db_info = get_active_database_info()
    if db_info["active_backend"] == "mongodb":
        existing = mongo_get_incident_by_id(incident_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Incident #{incident_id} not found in MongoDB Atlas")

        old_status = existing.get("status", "Reported")
        actor_name = payload.dispatcher_actor or "Dispatcher Ops"
        note_details = f"Status advanced from {old_status} to {payload.status} in MongoDB Atlas."
        if payload.dispatcher_notes:
            note_details += f" Dispatcher note: {payload.dispatcher_notes}"

        action_log_entry = {
            "id": len(existing.get("action_logs", [])) + 1,
            "incident_id": incident_id,
            "action_type": "STATUS_CHANGE",
            "actor": actor_name,
            "details": note_details,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

        # Synchronize assigned resource availability in SQLite fleet
        assigned_res_id = existing.get("assigned_resource_id")
        if assigned_res_id:
            res = db.query(Resource).filter(Resource.id == assigned_res_id).first()
            if res:
                if payload.status == "Resolved":
                    res.availability = "Available"
                    res.current_incident_id = None
                elif payload.status == "Arrived":
                    res.availability = "On Scene"
                elif payload.status == "En Route":
                    res.availability = "En Route"
                elif payload.status == "Accepted":
                    res.availability = "Assigned"
                db.commit()

        updated_doc = mongo_update_incident_status(incident_id, payload.status, action_log=action_log_entry)
        return incident_to_response(updated_doc, db=db)

    # SQLite status update
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    old_status = inc.status
    inc.status = payload.status
    inc.updated_at = datetime.datetime.utcnow()

    # Synchronize assigned resource availability based on lifecycle
    if inc.assigned_resource_id:
        res = db.query(Resource).filter(Resource.id == inc.assigned_resource_id).first()
        if res:
            if payload.status == "Resolved":
                res.availability = "Available"
                res.current_incident_id = None
            elif payload.status == "Arrived":
                res.availability = "On Scene"
            elif payload.status == "En Route":
                res.availability = "En Route"
            elif payload.status == "Accepted":
                res.availability = "Assigned"

    actor_name = payload.dispatcher_actor or "Dispatcher Ops"
    note_details = f"Status advanced from {old_status} to {payload.status}."
    if payload.dispatcher_notes:
        note_details += f" Dispatcher note: {payload.dispatcher_notes}"

    log = ActionLog(
        incident_id=inc.id,
        action_type="STATUS_CHANGE",
        actor=actor_name,
        details=note_details,
    )
    db.add(log)
    db.commit()
    db.refresh(inc)

    return incident_to_response(inc, db=db)


@router.patch("/{incident_id}/urgency", response_model=IncidentResponse)
def override_incident_urgency(
    incident_id: int,
    payload: IncidentUrgencyOverride,
    db: Session = Depends(get_db),
):
    """
    Allows a human dispatcher to review and override the AI/heuristic urgency level.
    """
    valid_urgencies = ["Critical", "High", "Medium", "Low"]
    if payload.urgency_override not in valid_urgencies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid urgency '{payload.urgency_override}'. Allowed: {', '.join(valid_urgencies)}",
        )

    db_info = get_active_database_info()
    if db_info["active_backend"] == "mongodb":
        existing = mongo_get_incident_by_id(incident_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Incident #{incident_id} not found in MongoDB Atlas")

        old_urg = existing.get("dispatcher_urgency_override") or existing.get("urgency")
        action_log_entry = {
            "id": len(existing.get("action_logs", [])) + 1,
            "incident_id": incident_id,
            "action_type": "TRIAGE_OVERRIDE",
            "actor": payload.dispatcher_actor or "Dispatcher Lead",
            "details": f"Dispatcher manually modified urgency from {old_urg} to {payload.urgency_override} in MongoDB Atlas. Rationale: {payload.reason or 'Field assessment adjustment.'}",
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

        updated_doc = mongo_override_urgency(incident_id, payload.urgency_override, action_log=action_log_entry)
        return incident_to_response(updated_doc, db=db)

    # SQLite urgency override
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    old_urg = inc.dispatcher_urgency_override or inc.urgency
    inc.dispatcher_urgency_override = payload.urgency_override
    inc.updated_at = datetime.datetime.utcnow()

    log = ActionLog(
        incident_id=inc.id,
        action_type="TRIAGE_OVERRIDE",
        actor=payload.dispatcher_actor or "Dispatcher Lead",
        details=f"Dispatcher manually modified urgency from {old_urg} to {payload.urgency_override}. Rationale: {payload.reason or 'Field assessment adjustment.'}",
    )
    db.add(log)
    db.commit()
    db.refresh(inc)

    return incident_to_response(inc, db=db)


@router.post("/reset-demo", response_model=dict)
def reset_demo_data(db: Session = Depends(get_db)):
    """Reset the database to clean fictional demo scenario data."""
    db.query(ActionLog).delete()
    db.query(Incident).delete()
    db.query(Resource).delete()
    db.commit()

    seed_database_if_empty(db)
    return {"status": "success", "message": "Demo data reset successfully in SQLite"}
