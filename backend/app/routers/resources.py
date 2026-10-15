import json
import datetime
import urllib.parse
from typing import List, Optional
from types import SimpleNamespace
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db, get_active_database_info
from ..models import Incident, Resource, ActionLog
from ..schemas import (
    ResourceResponse,
    RecommendationResponse,
    RecommendationItem,
    ResourceAssignmentRequest,
    IncidentResponse,
    TeamMissionResponse,
    TeamStatusUpdatePayload,
)
from ..resource_engine import rank_resources_for_incident
from .incidents import incident_to_response
from ..mongo_service import (
    mongo_get_incident_by_id,
    mongo_get_incidents,
    mongo_assign_resource,
    mongo_unassign_resource,
    mongo_update_incident_status,
)

router = APIRouter(prefix="/api", tags=["resources"])


def resource_to_response(res: Resource) -> ResourceResponse:
    caps = []
    if res.capabilities:
        try:
            caps = json.loads(res.capabilities)
        except Exception:
            caps = [res.capabilities]
    return ResourceResponse(
        id=res.id,
        name=res.name,
        resource_type=res.resource_type,
        capabilities=caps,
        simulated_lat=res.simulated_lat,
        simulated_lng=res.simulated_lng,
        simulated_location_name=res.simulated_location_name,
        availability=res.availability,
        current_incident_id=res.current_incident_id,
        capacity=res.capacity,
        contact_callsign=res.contact_callsign,
        created_at=res.created_at,
    )


@router.get("/resources", response_model=List[ResourceResponse])
def get_resources(
    availability: Optional[str] = None,
    resource_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Retrieve all simulated rescue resources with optional filters."""
    query = db.query(Resource)

    if availability and availability != "All":
        query = query.filter(Resource.availability == availability)

    if resource_type and resource_type != "All":
        query = query.filter(Resource.resource_type == resource_type)

    resources = query.order_by(Resource.name).all()
    return [resource_to_response(r) for r in resources]


@router.get("/incidents/{incident_id}/recommendations", response_model=RecommendationResponse)
def get_incident_recommendations(incident_id: int, db: Session = Depends(get_db)):
    """
    Computes explainable resource recommendations for an emergency incident.
    - Matches required capabilities with resource skills
    - Evaluates live availability status
    - Calculates real Haversine distance only when GPS coordinates are available
    - Transparently presents reasoning for each match
    """
    db_info = get_active_database_info()
    if db_info["active_backend"] == "mongodb":
        inc_doc = mongo_get_incident_by_id(incident_id)
        if not inc_doc:
            raise HTTPException(status_code=404, detail="Incident not found in MongoDB Atlas")
        inc = SimpleNamespace(**inc_doc)
    else:
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            raise HTTPException(status_code=404, detail="Incident not found")

    resources = db.query(Resource).all()
    ranked = rank_resources_for_incident(inc, resources)

    raw_req_caps = getattr(inc, "recommended_capabilities", [])
    if isinstance(raw_req_caps, list):
        req_caps = raw_req_caps
    elif isinstance(raw_req_caps, str):
        try:
            req_caps = json.loads(raw_req_caps)
        except Exception:
            req_caps = [raw_req_caps] if raw_req_caps else []
    else:
        req_caps = []

    has_coords = inc.latitude is not None and inc.longitude is not None

    recommendation_items = [
        RecommendationItem(
            resource=resource_to_response(item["resource"]),
            match_score=item["match_score"],
            is_available=item["is_available"],
            is_suitable=item["is_suitable"],
            distance_km=item["distance_km"],
            matched_capabilities=item["matched_capabilities"],
            recommendation_reason=item["recommendation_reason"],
            priority_level=item["priority_level"],
        )
        for item in ranked
    ]

    top_recs_count = len([r for r in recommendation_items if r.priority_level == "Primary Recommendation"])
    explanation = (
        f"Calculated recommendations for Incident #{inc.id} ({inc.incident_type}). "
        f"Identified {top_recs_count} primary operational match(es) across simulated fleet. "
        + ("GPS proximity incorporated." if has_coords else "GPS coordinates absent; ranked purely by capability compatibility.")
    )

    effective_urgency = getattr(inc, "dispatcher_urgency_override", None) or getattr(inc, "urgency", "Medium")

    return RecommendationResponse(
        incident_id=inc.id,
        incident_urgency=effective_urgency,
        required_capabilities=req_caps,
        has_coordinates=has_coords,
        recommendations=recommendation_items,
        explanation=explanation,
    )


@router.post("/incidents/{incident_id}/assignments", response_model=IncidentResponse)
def assign_resource_to_incident(
    incident_id: int,
    payload: ResourceAssignmentRequest,
    db: Session = Depends(get_db),
):
    """
    Human dispatcher control: Approves and assigns a simulated resource to an incident.
    Validates:
    - Unit must not be in Maintenance
    - Unit must not be already deployed to another active incident
    - Unit must be suitable for incident needs
    - Human dispatcher approval required
    """
    db_info = get_active_database_info()
    is_mongo = db_info["active_backend"] == "mongodb"

    if is_mongo:
        inc_doc = mongo_get_incident_by_id(incident_id)
        if not inc_doc:
            raise HTTPException(status_code=404, detail="Incident not found in MongoDB Atlas")
        inc = SimpleNamespace(**inc_doc)
    else:
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            raise HTTPException(status_code=404, detail="Incident not found")

    res = db.query(Resource).filter(Resource.id == payload.resource_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="Resource not found")

    # 1. Check Maintenance status
    if (res.availability or "").lower() == "maintenance":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot assign unit '{res.name}': Unit is currently offline for maintenance.",
        )

    # 2. Check if already committed to another incident
    if (
        (res.availability or "").lower() in ["assigned", "dispatched", "on scene"]
        and res.current_incident_id
        and res.current_incident_id != inc.id
    ):
        if not payload.reassign:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot assign unit '{res.name}': Unit is currently committed to Incident #{res.current_incident_id}. Please release it first or select reassign.",
            )
        # Handle reassign cleanly
        if is_mongo:
            prev_doc = mongo_get_incident_by_id(res.current_incident_id)
            if prev_doc:
                release_log = {
                    "id": len(prev_doc.get("action_logs", [])) + 1,
                    "incident_id": res.current_incident_id,
                    "action_type": "RESOURCE_RELEASED",
                    "actor": payload.dispatcher_actor or "Dispatcher Lead",
                    "details": f"Unit '{res.name}' was diverted and reassigned to Incident #{inc.id}.",
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                }
                mongo_unassign_resource(res.current_incident_id, action_log=release_log)
        else:
            prev_inc = db.query(Incident).filter(Incident.id == res.current_incident_id).first()
            if prev_inc:
                prev_inc.assigned_resource_id = None
                if prev_inc.status in ["Assigned", "Accepted", "En Route", "Arrived"]:
                    prev_inc.status = "Verified"
                prev_inc.updated_at = datetime.datetime.utcnow()
                db.add(ActionLog(
                    incident_id=prev_inc.id,
                    action_type="RESOURCE_RELEASED",
                    actor=payload.dispatcher_actor or "Dispatcher Lead",
                    details=f"Unit '{res.name}' was diverted and reassigned to Incident #{inc.id}.",
                ))

    # 3. Check suitability
    ranked = rank_resources_for_incident(inc, [res])
    if ranked and not ranked[0]["is_suitable"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot assign unit '{res.name}': Unit lacks suitable capabilities for '{inc.incident_type}' missions.",
        )

    # If another resource was previously assigned, release it
    current_assigned = getattr(inc, "assigned_resource_id", None)
    if current_assigned and current_assigned != res.id:
        old_res = db.query(Resource).filter(Resource.id == current_assigned).first()
        if old_res:
            old_res.availability = "Available"
            old_res.current_incident_id = None

    # Update Resource
    res.availability = "Assigned"
    res.current_incident_id = inc.id
    db.commit()

    # Log action
    actor = payload.dispatcher_actor or "Human Dispatcher"
    note_details = f"Dispatcher approved assignment of unit '{res.name}' ({res.contact_callsign}). Resource deployed."
    if payload.dispatcher_notes:
        note_details += f" Dispatch note: {payload.dispatcher_notes}"

    if is_mongo:
        assign_log = {
            "id": len(inc_doc.get("action_logs", [])) + 1,
            "incident_id": inc.id,
            "action_type": "RESOURCE_ASSIGNED",
            "actor": actor,
            "details": note_details,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }
        updated = mongo_assign_resource(inc.id, res.id, action_log=assign_log)
        return incident_to_response(updated, db=db)
    else:
        inc.assigned_resource_id = res.id
        if inc.status in ["Reported", "Verified"]:
            inc.status = "Assigned"
        inc.updated_at = datetime.datetime.utcnow()

        log = ActionLog(
            incident_id=inc.id,
            action_type="RESOURCE_ASSIGNED",
            actor=actor,
            details=note_details,
        )
        db.add(log)
        db.commit()
        db.refresh(inc)
        return incident_to_response(inc, db=db)


@router.post("/incidents/{incident_id}/unassign", response_model=IncidentResponse)
def unassign_resource_from_incident(
    incident_id: int,
    db: Session = Depends(get_db),
):
    """
    Human dispatcher control: Unassigns or releases a resource from an incident.
    """
    db_info = get_active_database_info()
    is_mongo = db_info["active_backend"] == "mongodb"

    if is_mongo:
        inc_doc = mongo_get_incident_by_id(incident_id)
        if not inc_doc:
            raise HTTPException(status_code=404, detail="Incident not found in MongoDB Atlas")

        assigned_id = inc_doc.get("assigned_resource_id")
        if not assigned_id:
            return incident_to_response(inc_doc, db=db)

        res = db.query(Resource).filter(Resource.id == assigned_id).first()
        if res:
            res.availability = "Available"
            res.current_incident_id = None
            db.commit()

        unassign_log = {
            "id": len(inc_doc.get("action_logs", [])) + 1,
            "incident_id": incident_id,
            "action_type": "RESOURCE_RELEASED",
            "actor": "Human Dispatcher",
            "details": f"Resource '{res.name if res else 'Unknown'}' was unassigned and returned to Available status.",
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }
        updated = mongo_unassign_resource(incident_id, action_log=unassign_log)
        return incident_to_response(updated, db=db)
    else:
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            raise HTTPException(status_code=404, detail="Incident not found")

        if not inc.assigned_resource_id:
            return incident_to_response(inc, db=db)

        res = db.query(Resource).filter(Resource.id == inc.assigned_resource_id).first()
        if res:
            res.availability = "Available"
            res.current_incident_id = None

        inc.assigned_resource_id = None
        if inc.status == "Assigned":
            inc.status = "Verified"
        inc.updated_at = datetime.datetime.utcnow()

        log = ActionLog(
            incident_id=inc.id,
            action_type="RESOURCE_RELEASED",
            actor="Human Dispatcher",
            details=f"Resource '{res.name if res else 'Unknown'}' was unassigned and returned to Available status.",
        )
        db.add(log)
        db.commit()
        db.refresh(inc)

        return incident_to_response(inc, db=db)


@router.get("/resources/{resource_id}/mission", response_model=TeamMissionResponse)
def get_team_mission(resource_id: int, db: Session = Depends(get_db)):
    """
    Rescue Team Terminal (MDT) Endpoint:
    Returns the selected rescue team profile and active assigned emergency mission.
    """
    res = db.query(Resource).filter(Resource.id == resource_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="Rescue team resource not found")

    db_info = get_active_database_info()
    is_mongo = db_info["active_backend"] == "mongodb"

    target_inc = None
    has_mission = False
    nav_url = None
    inc_resp = None

    if is_mongo:
        if res.current_incident_id:
            doc = mongo_get_incident_by_id(res.current_incident_id)
            if doc and doc.get("status") == "Resolved":
                res.current_incident_id = None
                res.availability = "Available"
                db.commit()
                doc = None
            if doc:
                target_inc = doc

        if not target_inc:
            all_active = [
                d for d in mongo_get_incidents()
                if d.get("assigned_resource_id") == res.id and d.get("status") != "Resolved"
            ]
            if all_active:
                target_inc = all_active[0]
                res.current_incident_id = target_inc["id"]
                if res.availability == "Available":
                    res.availability = "Assigned"
                db.commit()

        if target_inc:
            inc_resp = incident_to_response(target_inc, db=db)
            has_mission = True
            lat = target_inc.get("latitude")
            lng = target_inc.get("longitude")
            if lat is not None and lng is not None:
                nav_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"
            else:
                encoded_loc = urllib.parse.quote(target_inc.get("location", ""))
                nav_url = f"https://www.google.com/maps/dir/?api=1&destination={encoded_loc}"
    else:
        if res.current_incident_id:
            active_target = db.query(Incident).filter(Incident.id == res.current_incident_id).first()
            if active_target and active_target.status == "Resolved":
                res.current_incident_id = None
                res.availability = "Available"
                db.commit()
                active_target = None
            target_inc = active_target

        if not target_inc:
            active_inc = (
                db.query(Incident)
                .filter(Incident.assigned_resource_id == res.id, Incident.status != "Resolved")
                .order_by(Incident.updated_at.desc())
                .first()
            )
            if active_inc:
                target_inc = active_inc
                res.current_incident_id = active_inc.id
                if res.availability == "Available":
                    res.availability = "Assigned"
                db.commit()

        if target_inc:
            inc_resp = incident_to_response(target_inc, db=db)
            has_mission = True
            if target_inc.latitude is not None and target_inc.longitude is not None:
                nav_url = f"https://www.google.com/maps/dir/?api=1&destination={target_inc.latitude},{target_inc.longitude}"
            else:
                encoded_loc = urllib.parse.quote(target_inc.location)
                nav_url = f"https://www.google.com/maps/dir/?api=1&destination={encoded_loc}"

    return TeamMissionResponse(
        resource=resource_to_response(res),
        has_active_mission=has_mission,
        incident=inc_resp,
        navigation_url=nav_url,
    )


@router.post("/resources/{resource_id}/mission-status", response_model=TeamMissionResponse)
def update_team_mission_status(
    resource_id: int,
    payload: TeamStatusUpdatePayload,
    db: Session = Depends(get_db),
):
    """
    Rescue Team Terminal (MDT) Action:
    Allows field rescue teams to update mission status:
    - Accepted, En Route, Arrived, Resolved
    """
    valid_statuses = ["Accepted", "En Route", "Arrived", "Resolved"]
    if payload.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid team status '{payload.status}'. Allowed: {', '.join(valid_statuses)}",
        )

    res = db.query(Resource).filter(Resource.id == resource_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="Rescue team not found")

    if not res.current_incident_id:
        raise HTTPException(
            status_code=400,
            detail=f"Team '{res.name}' currently has no active assigned mission to update.",
        )

    db_info = get_active_database_info()
    is_mongo = db_info["active_backend"] == "mongodb"

    if is_mongo:
        inc_doc = mongo_get_incident_by_id(res.current_incident_id)
        if not inc_doc:
            raise HTTPException(status_code=404, detail="Assigned incident not found in MongoDB Atlas")

        old_status = inc_doc.get("status")

        # Synchronize team resource availability
        if payload.status == "Accepted":
            res.availability = "Assigned"
        elif payload.status == "En Route":
            res.availability = "En Route"
        elif payload.status == "Arrived":
            res.availability = "On Scene"
        elif payload.status == "Resolved":
            res.availability = "Available"
            res.current_incident_id = None
        db.commit()

        notes_suffix = f" Field report: {payload.notes}" if payload.notes else ""
        field_log = {
            "id": len(inc_doc.get("action_logs", [])) + 1,
            "incident_id": inc_doc["id"],
            "action_type": "FIELD_STATUS_UPDATE",
            "actor": f"Team {res.contact_callsign}",
            "details": f"Rescue team advanced status from {old_status} to [{payload.status}] in MongoDB Atlas.{notes_suffix}",
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

        mongo_update_incident_status(inc_doc["id"], payload.status, action_log=field_log)
        return get_team_mission(resource_id=resource_id, db=db)
    else:
        inc = db.query(Incident).filter(Incident.id == res.current_incident_id).first()
        if not inc:
            raise HTTPException(status_code=404, detail="Assigned incident not found")

        old_status = inc.status
        inc.status = payload.status
        inc.updated_at = datetime.datetime.utcnow()

        if payload.status == "Accepted":
            res.availability = "Assigned"
        elif payload.status == "En Route":
            res.availability = "En Route"
        elif payload.status == "Arrived":
            res.availability = "On Scene"
        elif payload.status == "Resolved":
            res.availability = "Available"
            res.current_incident_id = None

        notes_suffix = f" Field report: {payload.notes}" if payload.notes else ""
        log = ActionLog(
            incident_id=inc.id,
            action_type="FIELD_STATUS_UPDATE",
            actor=f"Team {res.contact_callsign}",
            details=f"Rescue team advanced status from {old_status} to [{payload.status}].{notes_suffix}",
        )
        db.add(log)
        db.commit()
        db.refresh(res)

        return get_team_mission(resource_id=resource_id, db=db)
