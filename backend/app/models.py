import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_type = Column(String(100), nullable=False)
    location = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    people_affected = Column(Integer, default=1)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    reported_time = Column(DateTime, default=datetime.datetime.utcnow)

    # AI / Rule-based Triage Fields
    urgency = Column(String(50), default="Medium")  # Critical, High, Medium, Low
    dispatcher_urgency_override = Column(String(50), nullable=True)
    urgency_explanation = Column(Text, nullable=True)
    key_risks = Column(Text, default="[]")  # JSON string list
    recommended_capabilities = Column(Text, default="[]")  # JSON string list
    uncertainty_score = Column(Float, default=0.2)
    uncertainty_note = Column(Text, nullable=True)
    assessment_method = Column(String(50), default="rule_based_fallback")

    # Workflow Status
    # Reported -> Verified -> Assigned -> En Route -> Resolved
    status = Column(String(50), default="Reported")
    assigned_resource_id = Column(Integer, ForeignKey("resources.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    assigned_resource = relationship("Resource", back_populates="incidents", foreign_keys=[assigned_resource_id])
    action_logs = relationship("ActionLog", back_populates="incident", cascade="all, delete-orphan", order_by="ActionLog.timestamp.desc()")


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    resource_type = Column(String(100), nullable=False)
    capabilities = Column(Text, default="[]")  # JSON string list
    simulated_lat = Column(Float, nullable=False)
    simulated_lng = Column(Float, nullable=False)
    simulated_location_name = Column(String(255), nullable=False)
    availability = Column(String(50), default="Available")  # Available, Assigned, En Route, On Scene, Maintenance
    current_incident_id = Column(Integer, nullable=True)
    capacity = Column(Integer, default=4)
    contact_callsign = Column(String(50), default="RESQ-ALPHA")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    incidents = relationship("Incident", back_populates="assigned_resource", foreign_keys=[Incident.assigned_resource_id])


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    action_type = Column(String(50), nullable=False)  # CREATED, STATUS_CHANGE, TRIAGE_OVERRIDE, RESOURCE_ASSIGNED, etc.
    actor = Column(String(100), default="Human Dispatcher")
    details = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    incident = relationship("Incident", back_populates="action_logs")
