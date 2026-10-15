from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Action Log
class ActionLogResponse(BaseModel):
    id: int
    incident_id: int
    action_type: str
    actor: str
    details: str
    timestamp: datetime

    class Config:
        from_attributes = True


# Resource Schemas
class ResourceBase(BaseModel):
    name: str
    resource_type: str
    capabilities: List[str]
    simulated_lat: float
    simulated_lng: float
    simulated_location_name: str
    availability: str
    capacity: int = 4
    contact_callsign: str


class ResourceResponse(BaseModel):
    id: int
    name: str
    resource_type: str
    capabilities: List[str]
    simulated_lat: float
    simulated_lng: float
    simulated_location_name: str
    availability: str
    current_incident_id: Optional[int] = None
    capacity: int
    contact_callsign: str
    created_at: datetime

    class Config:
        from_attributes = True


# Incident Intake
class IncidentCreate(BaseModel):
    incident_type: str = Field(..., example="Flood")
    location: str = Field(..., min_length=2, example="Riverdale North Levee, Sector 4")
    description: str = Field(..., min_length=5, example="Water rising rapidly, 3 families trapped on roofs.")
    people_affected: int = Field(default=1, ge=0)
    latitude: Optional[float] = Field(default=None, example=37.7749)
    longitude: Optional[float] = Field(default=None, example=-122.4194)
    reported_time: Optional[datetime] = None


class IncidentStatusUpdate(BaseModel):
    status: str = Field(..., example="Verified")  # Reported, Verified, Assigned, En Route, Resolved
    dispatcher_notes: Optional[str] = None
    dispatcher_actor: Optional[str] = "Dispatcher Ops"


class IncidentUrgencyOverride(BaseModel):
    urgency_override: str = Field(..., example="Critical")  # Critical, High, Medium, Low
    reason: Optional[str] = "Dispatcher situational review and local telemetry"
    dispatcher_actor: Optional[str] = "Dispatcher Ops"


class IncidentResponse(BaseModel):
    id: int
    incident_type: str
    location: str
    description: str
    people_affected: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    reported_time: datetime

    urgency: str
    dispatcher_urgency_override: Optional[str] = None
    effective_urgency: str
    urgency_explanation: Optional[str] = None
    key_risks: List[str]
    recommended_capabilities: List[str]
    uncertainty_score: float
    uncertainty_note: Optional[str] = None
    assessment_method: str

    recommended_next_action: Optional[str] = None
    missing_information: List[str] = []

    status: str
    assigned_resource_id: Optional[int] = None
    assigned_resource: Optional[ResourceResponse] = None

    created_at: datetime
    updated_at: datetime
    action_logs: List[ActionLogResponse] = []

    class Config:
        from_attributes = True


# Recommendation Schemas
class RecommendationItem(BaseModel):
    resource: ResourceResponse
    match_score: int  # 0 to 100
    is_available: bool
    is_suitable: bool = True
    distance_km: Optional[float] = None
    matched_capabilities: List[str]
    recommendation_reason: str
    priority_level: str  # Primary, Secondary, Standby, Unavailable, Unsuitable


class RecommendationResponse(BaseModel):
    incident_id: int
    incident_urgency: str
    required_capabilities: List[str]
    has_coordinates: bool
    recommendations: List[RecommendationItem]
    explanation: str


class ResourceAssignmentRequest(BaseModel):
    resource_id: int
    dispatcher_notes: Optional[str] = None
    dispatcher_actor: Optional[str] = "Dispatcher Ops"
    reassign: Optional[bool] = False


# Dashboard Stats
class DashboardStats(BaseModel):
    total_incidents: int
    critical_high_count: int
    active_incidents: int
    resolved_incidents: int
    total_resources: int
    available_resources: int
    assigned_resources: int
    simulation_mode: bool


# Rescue Team Terminal Schemas
class TeamStatusUpdatePayload(BaseModel):
    status: str  # Accepted, En Route, Arrived, Resolved
    notes: Optional[str] = None


class TeamMissionResponse(BaseModel):
    resource: ResourceResponse
    has_active_mission: bool
    incident: Optional[IncidentResponse] = None
    navigation_url: Optional[str] = None


# Rescue Prioritizer Schemas
class PrioritizedResourceSuggestion(BaseModel):
    resource_id: int
    resource_name: str
    contact_callsign: str
    resource_type: str
    availability: str
    is_available: bool
    is_suitable: bool
    match_score: int
    matched_capabilities: List[str] = []
    suitability_explanation: str
    priority_level: str


class PrioritizedIncidentItem(BaseModel):
    incident_id: int
    incident_type: str
    location: str
    description: str
    people_affected: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: str
    assigned_resource_id: Optional[int] = None
    assigned_resource_callsign: Optional[str] = None

    priority_rank: int
    urgency: str
    priority_score: float
    urgency_reason: str
    life_threat_indicators: List[str] = []
    reported_hazards: List[str] = []
    worsening_factors: List[str] = []
    suggested_action: str
    missing_information: List[str] = []
    uncertainty_score: float = 0.15
    uncertainty_note: Optional[str] = None

    suggested_resources: List[PrioritizedResourceSuggestion] = []
    resource_availability_summary: str


class PrioritizationResponse(BaseModel):
    assessment_method: str
    total_incidents_analyzed: int
    timestamp: datetime
    summary: str
    prioritized_incidents: List[PrioritizedIncidentItem]

