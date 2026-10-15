import math
import json
from typing import List, Dict, Any, Optional
from .models import Resource, Incident


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two GPS coordinates in kilometers.
    """
    R = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


def rank_resources_for_incident(
    incident: Incident,
    resources: List[Resource]
) -> List[Dict[str, Any]]:
    """
    Evaluates and ranks resources for an incident based on:
    - Capability overlap with recommended capabilities
    - Current availability status
    - Proximity (Haversine distance) only if both have valid coordinates
    - Returns structured recommendations with transparent reasoning.
    """
    # Parse required capabilities safely whether list or JSON string
    raw_caps = getattr(incident, "recommended_capabilities", None)
    if isinstance(raw_caps, list):
        required_caps = raw_caps
    elif isinstance(raw_caps, str):
        try:
            required_caps = json.loads(raw_caps)
        except Exception:
            required_caps = [raw_caps] if raw_caps else []
    else:
        required_caps = []

    has_incident_coords = (
        incident.latitude is not None and incident.longitude is not None
    )

    scored_items = []

    for res in resources:
        try:
            res_caps: List[str] = (
                json.loads(res.capabilities) if res.capabilities else []
            )
        except Exception:
            res_caps = []

        # 1. Capability match
        matched_caps = [
            c for c in res_caps
            if any(rc.lower() in c.lower() or c.lower() in rc.lower() for rc in required_caps)
        ]
        
        # Check domain suitability (matching capabilities or direct type alignment)
        is_type_match = any(
            rc.lower() in res.resource_type.lower() or res.resource_type.lower() in rc.lower()
            for rc in required_caps
        )
        is_suitable = (len(matched_caps) > 0) or is_type_match
        
        cap_score = min(60, len(matched_caps) * 20)
        if not is_suitable:
            cap_score = 0

        # 2. Availability score
        res_avail_lower = (res.availability or "").lower()
        is_available = res_avail_lower == "available"
        is_maintenance = res_avail_lower == "maintenance"
        
        if is_available:
            avail_score = 30
        elif is_maintenance:
            avail_score = 0
        else:
            avail_score = 5

        # 3. Distance calculation (only when both coordinates exist)
        distance_km: Optional[float] = None
        dist_score = 0
        if has_incident_coords and res.simulated_lat is not None and res.simulated_lng is not None:
            distance_km = haversine_distance(
                incident.latitude,
                incident.longitude,
                res.simulated_lat,
                res.simulated_lng,
            )
            if distance_km <= 5.0:
                dist_score = 15
            elif distance_km <= 15.0:
                dist_score = 10
            elif distance_km <= 35.0:
                dist_score = 5
            else:
                dist_score = 2
        else:
            dist_score = 5  # neutral baseline when coordinates are absent

        total_score = min(100, cap_score + avail_score + dist_score)

        # Build human-readable reason
        reasons = []
        if matched_caps:
            reasons.append(f"Direct capability match: {', '.join(matched_caps)}")
        elif is_suitable:
            reasons.append(f"Domain compatible asset ({res.resource_type})")
        else:
            reasons.append(f"No capability overlap for required {incident.incident_type} needs")

        if is_available:
            reasons.append("Unit is currently Available on standby")
        elif is_maintenance:
            reasons.append("Unit status: In Maintenance (Unavailable)")
        else:
            reasons.append(f"Unit status: {res.availability} (deployed to Incident #{res.current_incident_id or 'active'})")

        if distance_km is not None:
            reasons.append(f"Simulated distance: {distance_km} km from scene coordinates")
        else:
            reasons.append("Distance metric unavailable (coordinates not provided)")

        # Determine priority label
        if not is_available:
            if is_maintenance:
                priority = "Unavailable (Maintenance)"
            else:
                priority = "Unavailable (Deployed)"
        elif not is_suitable:
            priority = "Unsuitable Match"
        elif total_score >= 65:
            priority = "Primary Recommendation"
        elif total_score >= 35:
            priority = "Secondary Response"
        else:
            priority = "Standby / Support"

        scored_items.append({
            "resource": res,
            "match_score": total_score,
            "is_available": is_available,
            "is_suitable": is_suitable,
            "distance_km": distance_km,
            "matched_capabilities": matched_caps,
            "recommendation_reason": ". ".join(reasons) + ".",
            "priority_level": priority,
        })

    # Sort: Available & Suitable first, then descending by match_score, then distance
    scored_items.sort(
        key=lambda x: (
            x["is_available"] and x["is_suitable"],
            x["is_available"],
            x["match_score"],
            -(x["distance_km"] if x["distance_km"] is not None else 9999)
        ),
        reverse=True,
    )

    return scored_items
