import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from .models import Incident, Resource
from .schemas import (
    PrioritizationResponse,
    PrioritizedIncidentItem,
    PrioritizedResourceSuggestion,
)
from .resource_engine import rank_resources_for_incident
from .config import OPENAI_API_KEY, GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Specific life threat regex patterns
LIFE_THREAT_PATTERNS = [
    (r"\btrapped\b", "Trapped victims requiring emergency extrication"),
    (r"\broof(top)?\b", "Victims stranded on rooftop due to rising water/hazard"),
    (r"\bpinned\b", "Victims physically pinned under debris or wreckage"),
    (r"\bunconscious\b", "Unconscious casualty requiring immediate airway support"),
    (r"\bcardiac\b", "Suspected cardiac arrest or acute cardiovascular collapse"),
    (r"\bdrowning\b", "Active drowning or submerged victim emergency"),
    (r"\bsevere bleeding\b", "Severe arterial or uncontrolled hemorrhage"),
    (r"\bsuffocat\w*\b", "Suffocation / respiratory distress from smoke or debris"),
    (r"\basphyxiat\w*\b", "Toxic chemical asphyxiation hazard"),
    (r"\bexplosion\b", "Explosion hazard or active blast blastwave"),
    (r"\btoxic\b", "Toxic gas or poisonous vapor cloud exposure"),
]

# Worsening / Escalation patterns
WORSENING_PATTERNS = [
    (r"\brising rapidly\b", "Floodwater rising rapidly"),
    (r"\bbreach\b", "Levee or structural containment breach"),
    (r"\bfast-moving\b", "Fast-moving water current"),
    (r"\bspreading\b", "Active fire or chemical plume spreading"),
    (r"\bout of control\b", "Fire/hazard burning out of control"),
    (r"\bburst\b", "Transformer or pressure vessel burst"),
    (r"\bcollapse\b", "Structural collapse progression or unstable masonry"),
    (r"\bpower down\b", "Power outage affecting vulnerable facilities"),
    (r"\bclinic|hospital\b", "Critical healthcare facility exposure"),
]


def evaluate_incident_prioritization(
    inc: Incident,
    all_resources: List[Resource]
) -> Dict[str, Any]:
    """
    Evaluates an incident's priority score (0-100) based on:
    - Immediate danger to life
    - People trapped or injured
    - Number of people affected
    - Reported hazards (rising water, spreading fire, collapse, etc.)
    - Worsening factors
    - Workflow status / unmet response need
    - Missing or uncertain information
    """
    text = f"{inc.incident_type or ''} {inc.description or ''} {inc.location or ''}".lower()
    score = 0.0
    life_threats: List[str] = []
    worsening_factors: List[str] = []
    hazards: List[str] = []
    reasons: List[str] = []

    inc_type_lower = (inc.incident_type or "").lower()

    # 1. Immediate danger to life
    for pat, label in LIFE_THREAT_PATTERNS:
        if re.search(pat, text):
            score += 18.0
            life_threats.append(label)

    if life_threats:
        reasons.append(f"Immediate life-safety threats detected: {', '.join(life_threats)}")
    else:
        reasons.append("No direct trapped or acute life-threat keywords reported in intake")

    # 2. Worsening / Escalating hazards
    for pat, label in WORSENING_PATTERNS:
        if re.search(pat, text):
            score += 12.0
            worsening_factors.append(label)

    if worsening_factors:
        reasons.append(f"Hazard escalation indicators: {', '.join(worsening_factors)}")

    # 3. Base hazard domain
    if any(k in inc_type_lower for k in ["collapse", "explosion", "hazmat", "chemical"]):
        score += 20.0
        hazards.append(f"High-consequence domain ({inc.incident_type})")
    elif any(k in inc_type_lower for k in ["flood", "fire"]):
        score += 16.0
        hazards.append(f"Active environmental threat ({inc.incident_type})")
    elif any(k in inc_type_lower for k in ["medical"]):
        score += 15.0
        hazards.append("Medical crisis response")
    else:
        score += 8.0
        hazards.append(f"Emergency intake ({inc.incident_type})")

    # Key risks from existing incident metadata
    try:
        existing_risks = json.loads(inc.key_risks) if inc.key_risks else []
        for r in existing_risks:
            if r not in hazards:
                hazards.append(r)
    except Exception:
        pass

    # 4. People affected / trapped headcount
    affected = inc.people_affected or 0
    if affected >= 50:
        score += 25.0
        reasons.append(f"Mass casualty scale ({affected} people affected)")
    elif affected >= 10:
        score += 20.0
        reasons.append(f"Multi-victim incident ({affected} people affected)")
    elif affected >= 4:
        score += 15.0
        reasons.append(f"Multiple individuals at risk ({affected} people affected)")
    elif affected >= 2:
        score += 10.0
        reasons.append(f"Multiple victims ({affected} people affected)")
    elif affected == 1:
        score += 5.0
        reasons.append(f"Single individual reported at risk ({affected} person)")
    else:
        reasons.append("Headcount unspecified in caller intake")

    # 5. Workflow status / unmet response need
    if inc.status == "Reported":
        score += 14.0
        reasons.append("Status: [Reported] — completely unassigned and awaiting initial dispatch authorization")
    elif inc.status == "Verified":
        score += 12.0
        reasons.append("Status: [Verified] — situational hazard confirmed, awaiting unit assignment")
    elif inc.status == "Assigned":
        score += 6.0
        reasons.append("Status: [Assigned] — resource assigned, awaiting unit acknowledgement")
    elif inc.status == "Accepted":
        score += 4.0
        reasons.append("Status: [Accepted] — unit prepped for mobilization")
    elif inc.status == "En Route":
        score += 2.0
        reasons.append("Status: [En Route] — unit mobilized and actively navigating to coordinates")
    elif inc.status == "Arrived":
        score += 0.0
        reasons.append("Status: [Arrived] — rescue team is already on scene conducting extraction operations")
    elif inc.status == "Resolved":
        score = 0.0
        reasons = ["Status: [Resolved] — emergency concluded, unit returned to standby"]

    # Cap score
    if inc.status != "Resolved":
        score = min(100.0, max(10.0, score))

    # Determine urgency level based on composite score
    if score >= 70.0:
        urgency = "Critical"
    elif score >= 48.0:
        urgency = "High"
    elif score >= 25.0:
        urgency = "Medium"
    else:
        urgency = "Low"

    # Missing information checklist
    missing_info: List[str] = []
    if inc.latitude is None or inc.longitude is None:
        missing_info.append("Exact GPS coordinates unverified (only street address provided; verify landmark coordinates)")
    if affected <= 1:
        missing_info.append("Precise count of trapped or injured individuals unconfirmed")
    if len((inc.description or "").split()) < 8:
        missing_info.append("Detailed physical scene dimensions and ingress road conditions")
    if any(k in inc_type_lower for k in ["flood", "water"]):
        missing_info.append("Current flood water depth, current velocity, and rate of rise")
    elif any(k in inc_type_lower for k in ["fire", "smoke"]):
        missing_info.append("Structure occupancy status and presence of hazardous/combustible accelerants")
    elif any(k in inc_type_lower for k in ["medical"]):
        missing_info.append("Patient vital signs, consciousness level, and immediate airway stability")

    # Suggested next assessment / response action
    if inc.status == "Reported":
        if any(k in inc_type_lower for k in ["flood", "water"]):
            next_action = "Approve swiftwater rescue boat deployment in Dispatcher Console and establish water ingress safety perimeter."
        elif any(k in inc_type_lower for k in ["fire", "smoke"]):
            next_action = "Establish perimeter safety zone and authorize primary fire suppression engine deployment in Dispatcher Console."
        elif any(k in inc_type_lower for k in ["medical"]):
            next_action = "Authorize Advanced Life Support (ALS) paramedic ambulance deployment with rapid transit priority."
        elif any(k in inc_type_lower for k in ["collapse", "earthquake"]):
            next_action = "Authorize Heavy Urban Search & Rescue and K-9 search team for structural breach extraction."
        elif any(k in inc_type_lower for k in ["chemical", "hazmat"]):
            next_action = "Enforce 500m exclusion perimeter and approve HAZMAT containment crew mobilization."
        else:
            next_action = "Dispatcher situational review required: Authorize qualified simulated rescue asset deployment."
    elif inc.status in ("Assigned", "Accepted"):
        unit_callsign = "Assigned Unit"
        if hasattr(inc, "assigned_resource") and inc.assigned_resource:
            unit_callsign = inc.assigned_resource.contact_callsign
        elif getattr(inc, "assigned_resource_id", None):
            m_res = next((r for r in all_resources if r.id == getattr(inc, "assigned_resource_id")), None)
            if m_res:
                unit_callsign = m_res.contact_callsign
        next_action = f"{unit_callsign} must confirm mission order, verify ingress route navigation, and report En Route."
    elif inc.status == "En Route":
        unit_callsign = "Unit"
        if hasattr(inc, "assigned_resource") and inc.assigned_resource:
            unit_callsign = inc.assigned_resource.contact_callsign
        elif getattr(inc, "assigned_resource_id", None):
            m_res = next((r for r in all_resources if r.id == getattr(inc, "assigned_resource_id")), None)
            if m_res:
                unit_callsign = m_res.contact_callsign
        next_action = f"{unit_callsign} in transit. Establish incident ground tactical frequency and report on-scene arrival."
    elif inc.status == "Arrived":
        next_action = "Execute rapid tactical triage on scene, initiate victim extrication, and transmit regular sitreps."
    else:
        next_action = "Monitor situation telemetry and coordinate with incident command."

    # 6. Evaluate Resource Recommendations from actual inventory
    ranked_resources = rank_resources_for_incident(inc, all_resources)
    suggested_resources: List[PrioritizedResourceSuggestion] = []
    available_suitable_count = 0

    for r_item in ranked_resources:
        res = r_item["resource"]
        is_suitable = r_item["is_suitable"]
        is_avail = r_item["is_available"]

        # Only suggest suitable resources (or top domain candidates)
        if is_suitable:
            if is_avail:
                available_suitable_count += 1
            
            # Format suggestion
            suggested_resources.append(
                PrioritizedResourceSuggestion(
                    resource_id=res.id,
                    resource_name=res.name,
                    contact_callsign=res.contact_callsign,
                    resource_type=res.resource_type,
                    availability=res.availability,
                    is_available=is_avail,
                    is_suitable=is_suitable,
                    match_score=r_item["match_score"],
                    matched_capabilities=r_item["matched_capabilities"],
                    suitability_explanation=r_item["recommendation_reason"],
                    priority_level=r_item["priority_level"],
                )
            )

    # Availability summary
    if available_suitable_count > 0:
        top_unit = next(s for s in suggested_resources if s.is_available)
        avail_summary = f"Available suitable asset: {top_unit.resource_name} ({top_unit.contact_callsign}, {top_unit.match_score}% match). Ready for dispatcher deployment."
    elif suggested_resources:
        avail_summary = "ALERT: No suitable units currently available in fleet inventory. All matching units are deployed to other incidents or in maintenance. Dispatcher review or mutual aid override required."
    else:
        avail_summary = "Specialized capability required: No direct matching units found in current fleet roster."

    return {
        "priority_score": score,
        "urgency": urgency,
        "urgency_reason": ". ".join(reasons) + ".",
        "life_threat_indicators": life_threats,
        "reported_hazards": hazards[:6],
        "worsening_factors": worsening_factors,
        "suggested_action": next_action,
        "missing_information": missing_info,
        "uncertainty_score": inc.uncertainty_score or 0.15,
        "uncertainty_note": inc.uncertainty_note,
        "suggested_resources": suggested_resources[:3],
        "resource_availability_summary": avail_summary,
    }


def prioritize_all_incidents(
    db: Session
) -> PrioritizationResponse:
    """
    Prioritizes all active and relevant incidents across the system:
    - Compares immediate danger to life, casualties trapped/injured, worsening hazards
    - Ranks incidents into a recommended order of attention
    - Matches suitable simulated resources from actual live inventory
    - Clearly labels results as Rule-Based Rescue Prioritization
    """
    from .database import get_active_database_info
    from .mongo_service import mongo_get_incidents
    from types import SimpleNamespace

    db_info = get_active_database_info()
    if db_info["active_backend"] == "mongodb":
        raw_docs = mongo_get_incidents()
        incidents = [SimpleNamespace(**d) for d in raw_docs]
    else:
        incidents = db.query(Incident).all()

    all_resources = db.query(Resource).all()

    prioritized_list: List[PrioritizedIncidentItem] = []

    for inc in incidents:
        eval_result = evaluate_incident_prioritization(inc, all_resources)

        assigned_callsign = None
        if hasattr(inc, "assigned_resource") and inc.assigned_resource:
            assigned_callsign = inc.assigned_resource.contact_callsign
        elif getattr(inc, "assigned_resource_id", None):
            res_match = next((r for r in all_resources if r.id == getattr(inc, "assigned_resource_id")), None)
            if res_match:
                assigned_callsign = res_match.contact_callsign

        item = PrioritizedIncidentItem(
            incident_id=inc.id,
            incident_type=inc.incident_type,
            location=inc.location,
            description=inc.description,
            people_affected=inc.people_affected or 0,
            latitude=inc.latitude,
            longitude=inc.longitude,
            status=inc.status,
            assigned_resource_id=inc.assigned_resource_id,
            assigned_resource_callsign=assigned_callsign,
            priority_rank=0,  # Will be assigned after sorting
            urgency=eval_result["urgency"],
            priority_score=eval_result["priority_score"],
            urgency_reason=eval_result["urgency_reason"],
            life_threat_indicators=eval_result["life_threat_indicators"],
            reported_hazards=eval_result["reported_hazards"],
            worsening_factors=eval_result["worsening_factors"],
            suggested_action=eval_result["suggested_action"],
            missing_information=eval_result["missing_information"],
            uncertainty_score=eval_result["uncertainty_score"],
            uncertainty_note=eval_result["uncertainty_note"],
            suggested_resources=eval_result["suggested_resources"],
            resource_availability_summary=eval_result["resource_availability_summary"],
        )
        prioritized_list.append(item)

    # Sort prioritized list:
    # 1. Unresolved before Resolved (Resolved incidents at the bottom)
    # 2. Descending by priority_score
    # 3. Trapped/life threats first
    # 4. Casualty count
    prioritized_list.sort(
        key=lambda x: (
            x.status != "Resolved",
            x.priority_score,
            len(x.life_threat_indicators) > 0,
            x.people_affected,
        ),
        reverse=True,
    )

    # Assign sequential ranks
    for idx, item in enumerate(prioritized_list, 1):
        item.priority_rank = idx

    # Summary statistics
    critical_count = sum(1 for i in prioritized_list if i.urgency == "Critical" and i.status != "Resolved")
    high_count = sum(1 for i in prioritized_list if i.urgency == "High" and i.status != "Resolved")
    pending_count = sum(1 for i in prioritized_list if not i.assigned_resource_id and i.status != "Resolved")

    # Honest labeling
    has_llm = bool(OPENAI_API_KEY or GEMINI_API_KEY)
    assessment_method = "AI Rescue Prioritization" if has_llm else "Rule-Based Rescue Prioritization"

    summary_text = (
        f"Analyzed {len(prioritized_list)} total emergency signals across database. "
        f"Identified {critical_count} Critical and {high_count} High priority incidents requiring immediate attention. "
        f"{pending_count} incident(s) currently pending dispatcher approval and resource assignment."
    )

    return PrioritizationResponse(
        assessment_method=assessment_method,
        total_incidents_analyzed=len(prioritized_list),
        timestamp=datetime.utcnow(),
        summary=summary_text,
        prioritized_incidents=prioritized_list,
    )
