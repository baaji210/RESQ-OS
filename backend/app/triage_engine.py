import json
import logging
import re
from typing import Dict, Any, List, Optional
from .config import OPENAI_API_KEY, GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Capability dictionary by incident type
TYPE_CAPABILITIES = {
    "flood": [
        "Water Rescue",
        "Swiftwater Boat",
        "Thermal Imaging Aerial Drone",
        "Emergency Medical Evacuation",
    ],
    "flash flood": [
        "Water Rescue",
        "Swiftwater Boat",
        "High-Clearance Transport",
        "Emergency Medical Evacuation",
    ],
    "fire": [
        "Fire Suppression",
        "Smoke Ventilation",
        "Thermal Drone Recon",
        "Paramedic Ambulance",
    ],
    "wildfire": [
        "Wildfire Engine",
        "Fire Break Trenching",
        "Aerial Recon / Drone",
        "Evacuation Transport",
    ],
    "earthquake": [
        "Heavy Urban Search & Rescue",
        "Structural Shoring",
        "K-9 Search Unit",
        "Advanced Life Support (ALS)",
    ],
    "structural collapse": [
        "Heavy Urban Search & Rescue",
        "Acoustic Listening Sensors",
        "Hydraulic Cutting Equipment",
        "Paramedic Ambulance",
    ],
    "chemical spill": [
        "HAZMAT Containment",
        "Decontamination Unit",
        "Air Quality Spectrometry",
        "Chemical Protective Gear",
    ],
    "hazmat": [
        "HAZMAT Containment",
        "Decontamination Unit",
        "Perimeter Lockdown",
        "Paramedic Ambulance",
    ],
    "medical emergency": [
        "Advanced Life Support (ALS)",
        "Paramedic Ambulance",
        "Defibrillator / Resuscitation",
        "Rapid Patient Transport",
    ],
    "landslide": [
        "Heavy Earth Moving",
        "Urban Search & Rescue",
        "Drone Topographical Mapping",
        "Paramedic Ambulance",
    ],
    "severe storm": [
        "Utility Repair / Clearing",
        "High-Clearance Transport",
        "Emergency Shelter Setup",
        "Paramedic Ambulance",
    ],
}

DEFAULT_CAPABILITIES = [
    "Rapid Reconnaissance",
    "Paramedic Ambulance",
    "Emergency Transport",
    "Mobile Command Unit",
]

# Keywords for risk extraction
CRITICAL_TRIGGERS = [
    r"\btrapped\b",
    r"\bdrowning\b",
    r"\bunconscious\b",
    r"\bcardiac\b",
    r"\bsevere bleeding\b",
    r"\bcollapse\b",
    r"\bexplosion\b",
    r"\brising rapidly\b",
    r"\bswept away\b",
    r"\broof\b",
    r"\bgas leak\b",
    r"\btoxic\b",
    r"\binfant\b",
    r"\bchild(ren)?\b",
    r"\bcritical\b",
    r"\bsuffocat(ing|ion)\b",
]

HIGH_TRIGGERS = [
    r"\binjured\b",
    r"\bfire spreading\b",
    r"\bwater entering\b",
    r"\bstranded\b",
    r"\bpower down\b",
    r"\bblocked exit\b",
    r"\bchemical odor\b",
    r"\bcracked wall\b",
    r"\bhyperthermia\b",
    r"\bhypothermia\b",
]


def deterministic_triage(
    incident_type: str,
    location: str,
    description: str,
    people_affected: int,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Transparent, explainable, deterministic rule-based triage fallback engine.
    Computes an urgency score, identifies risk indicators, determines required capabilities,
    and calculates an uncertainty index with clear justification.
    """
    text = f"{incident_type} {description} {location}".lower()
    score = 0  # 0-100 scale
    risks: List[str] = []
    explanation_parts: List[str] = []

    # 1. Base score by incident type severity
    inc_type_lower = incident_type.lower()
    if any(k in inc_type_lower for k in ["collapse", "explosion", "hazmat", "chemical"]):
        score += 35
        risks.append(f"High-hazard domain ({incident_type})")
        explanation_parts.append(f"Baseline high-risk classification for '{incident_type}'")
    elif any(k in inc_type_lower for k in ["flood", "fire", "earthquake", "landslide"]):
        score += 25
        risks.append(f"Environmental danger scenario ({incident_type})")
        explanation_parts.append(f"Active environmental threat pattern detected")
    elif any(k in inc_type_lower for k in ["medical"]):
        score += 20
        risks.append("Immediate medical attention required")
        explanation_parts.append("Direct medical emergency report")
    else:
        score += 10
        explanation_parts.append("General emergency intake baseline")

    # 2. Critical keywords inspection
    crit_matches = [p for p in CRITICAL_TRIGGERS if re.search(p, text)]
    if crit_matches:
        score += len(crit_matches) * 15
        for m in crit_matches:
            clean_term = m.replace(r"\b", "").replace("(", "").replace(")?", "").replace("|ren", "")
            risks.append(f"Life safety trigger: '{clean_term}' detected")
        explanation_parts.append(f"Found {len(crit_matches)} high-severity life-threat indicators in call text")

    # 3. High keywords inspection
    high_matches = [p for p in HIGH_TRIGGERS if re.search(p, text)]
    if high_matches:
        score += len(high_matches) * 8
        for m in high_matches:
            clean_term = m.replace(r"\b", "")
            risks.append(f"Escalation factor: '{clean_term}'")
        explanation_parts.append(f"Found {len(high_matches)} situational escalation indicators")

    # 4. Impact scale (People affected)
    if people_affected >= 50:
        score += 35
        risks.append(f"Mass-casualty scale: ~{people_affected} people affected")
        explanation_parts.append(f"Severe casualty volume ({people_affected} affected) mandates surge response")
    elif people_affected >= 10:
        score += 25
        risks.append(f"Multi-victim incident: {people_affected} individuals")
        explanation_parts.append(f"Multi-person exposure ({people_affected} affected)")
    elif people_affected >= 3:
        score += 15
        risks.append(f"Multiple individuals involved ({people_affected})")
    elif people_affected == 0:
        explanation_parts.append("Affected count unspecified; default conservative assumption applied")

    # 5. Determine Urgency Classification
    if score >= 65:
        urgency = "Critical"
    elif score >= 45:
        urgency = "High"
    elif score >= 25:
        urgency = "Medium"
    else:
        urgency = "Low"

    # 6. Capabilities extraction
    caps: List[str] = []
    for k, v in TYPE_CAPABILITIES.items():
        if k in inc_type_lower or k in text:
            for item in v:
                if item not in caps:
                    caps.append(item)
    if not caps:
        caps = list(DEFAULT_CAPABILITIES)

    # Add specific medical or water rescue capabilities if triggered
    if "trapped" in text and "Heavy Urban Search & Rescue" not in caps:
        caps.insert(0, "Heavy Urban Search & Rescue")
    if ("flood" in text or "water" in text) and "Water Rescue" not in caps:
        caps.insert(0, "Water Rescue")

    # 7. Uncertainty estimation
    uncertainty = 0.15
    uncertainty_reasons = []

    if latitude is None or longitude is None:
        uncertainty += 0.20
        uncertainty_reasons.append("Exact GPS coordinates unavailable (manual address only)")

    if len(description.split()) < 8:
        uncertainty += 0.20
        uncertainty_reasons.append("Brief description lacks detailed physical scene metrics")

    if people_affected == 0 or people_affected == 1:
        uncertainty += 0.10
        uncertainty_reasons.append("Casualty estimate may be unverified preliminary headcount")

    uncertainty = round(min(0.85, max(0.10, uncertainty)), 2)
    uncertainty_note = "; ".join(uncertainty_reasons) if uncertainty_reasons else "Telemetry and description provide high contextual confidence"

    explanation = (
        f"Assessed as [{urgency.upper()}] (Heuristic Score: {score}/100). "
        + ". ".join(explanation_parts)
        + ". Recommendations emphasize rapid containment and specialized resource mobilization."
    )

    return {
        "urgency": urgency,
        "urgency_explanation": explanation,
        "key_risks": risks[:6],  # top risks
        "recommended_capabilities": caps[:5],
        "uncertainty_score": uncertainty,
        "uncertainty_note": uncertainty_note,
        "assessment_method": "rule_based_fallback",
    }


def call_llm_triage(
    incident_type: str,
    location: str,
    description: str,
    people_affected: int,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Attempts to call OpenAI or Gemini if API keys are set.
    Returns structured dictionary or None on failure/unconfigured.
    """
    if not OPENAI_API_KEY and not GEMINI_API_KEY:
        return None

    # OpenAI integration when API key is provided
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY, timeout=5.0)

            system_prompt = (
                "You are RESQ-OS AI Triage Engine, an autonomous disaster response triage assistant. "
                "Analyze the emergency incident report and return ONLY a valid JSON object with these keys:\n"
                "- urgency: 'Critical', 'High', 'Medium', or 'Low'\n"
                "- urgency_explanation: 2-3 concise factual sentences explaining the urgency\n"
                "- key_risks: list of 3-5 concise risk phrases\n"
                "- recommended_capabilities: list of 3-5 operational capabilities required\n"
                "- uncertainty_score: float between 0.05 and 0.85 representing uncertainty\n"
                "- uncertainty_note: concise explanation of confidence limitations\n"
                "IMPORTANT: This is for simulated dispatcher coordination only."
            )

            user_msg = (
                f"Incident Type: {incident_type}\n"
                f"Location: {location} (Lat: {latitude}, Lng: {longitude})\n"
                f"Description: {description}\n"
                f"People Affected: {people_affected}\n"
            )

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=500,
            )

            raw = response.choices[0].message.content
            parsed = json.loads(raw)
            parsed["assessment_method"] = "ai_generated"
            return parsed
        except Exception as e:
            logger.warning(f"LLM API call failed, safely falling back to rule-based engine: {e}")
            return None

    return None


def evaluate_incident_triage(
    incident_type: str,
    location: str,
    description: str,
    people_affected: int,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Main triage coordinator: Attempts LLM if credentials exist,
    otherwise uses the deterministic rule-based fallback.
    """
    llm_result = call_llm_triage(
        incident_type=incident_type,
        location=location,
        description=description,
        people_affected=people_affected,
        latitude=latitude,
        longitude=longitude,
    )
    if llm_result:
        return llm_result

    return deterministic_triage(
        incident_type=incident_type,
        location=location,
        description=description,
        people_affected=people_affected,
        latitude=latitude,
        longitude=longitude,
    )
