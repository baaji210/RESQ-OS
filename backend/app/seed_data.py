import datetime
import json
from sqlalchemy.orm import Session
from .models import Incident, Resource, ActionLog
from .triage_engine import evaluate_incident_triage

DEMO_RESOURCES = [
    {
        "name": "Swiftwater Rescue Boat Alpha-1",
        "resource_type": "Water Rescue",
        "capabilities": [
            "Water Rescue",
            "Swiftwater Boat",
            "Thermal Imaging Aerial Drone",
            "Emergency Medical Evacuation",
        ],
        "simulated_lat": 37.7725,
        "simulated_lng": -122.4095,
        "simulated_location_name": "Pier 40 Marina Depot",
        "availability": "Available",
        "capacity": 6,
        "contact_callsign": "WATER-RESCUE-1",
    },
    {
        "name": "US&R Task Force Squad 7",
        "resource_type": "Heavy Urban Search & Rescue",
        "capabilities": [
            "Heavy Urban Search & Rescue",
            "Acoustic Listening Sensors",
            "Hydraulic Cutting Equipment",
            "Structural Shoring",
            "K-9 Search Unit",
        ],
        "simulated_lat": 37.7833,
        "simulated_lng": -122.4167,
        "simulated_location_name": "Central Emergency Logistics Yard",
        "availability": "Available",
        "capacity": 12,
        "contact_callsign": "TASKFORCE-7",
    },
    {
        "name": "Paramedic ALS Squad 19",
        "resource_type": "Medical / Paramedic",
        "capabilities": [
            "Advanced Life Support (ALS)",
            "Paramedic Ambulance",
            "Defibrillator / Resuscitation",
            "Rapid Patient Transport",
            "Emergency Medical Evacuation",
        ],
        "simulated_lat": 37.7610,
        "simulated_lng": -122.4350,
        "simulated_location_name": "Mission District Fire Station 7",
        "availability": "Available",
        "capacity": 3,
        "contact_callsign": "MEDIC-19",
    },
    {
        "name": "HAZMAT HazChem Intercept Team 3",
        "resource_type": "HAZMAT Unit",
        "capabilities": [
            "HAZMAT Containment",
            "Decontamination Unit",
            "Air Quality Spectrometry",
            "Chemical Protective Gear",
        ],
        "simulated_lat": 37.7550,
        "simulated_lng": -122.3900,
        "simulated_location_name": "Port Logistics Safety Depot",
        "availability": "Available",
        "capacity": 5,
        "contact_callsign": "HAZMAT-3",
    },
    {
        "name": "SkyWatch Aerial Recon Drone Wing",
        "resource_type": "Aerial Recon / Drone",
        "capabilities": [
            "Thermal Imaging Aerial Drone",
            "Rapid Reconnaissance",
            "Drone Topographical Mapping",
            "Night Vision Optics",
        ],
        "simulated_lat": 37.7900,
        "simulated_lng": -122.4000,
        "simulated_location_name": "Downtown Rooftop Heliport",
        "availability": "Available",
        "capacity": 2,
        "contact_callsign": "SKYWATCH-AIR",
    },
    {
        "name": "Wildland Heavy Engine 42",
        "resource_type": "Fire Suppression",
        "capabilities": [
            "Fire Suppression",
            "Wildfire Engine",
            "Smoke Ventilation",
            "High-Clearance Transport",
        ],
        "simulated_lat": 37.7450,
        "simulated_lng": -122.4450,
        "simulated_location_name": "Twin Peaks Fire Substation",
        "availability": "Available",
        "capacity": 4,
        "contact_callsign": "ENGINE-42",
    },
]

DEMO_INCIDENTS = [
    {
        "incident_type": "Flood",
        "location": "Mission Creek Channel & 6th St",
        "description": "Flash flooding breached low-lying retaining barrier. Water rising rapidly, 8 people trapped inside vehicle and elevated walkway.",
        "people_affected": 8,
        "latitude": 37.7711,
        "longitude": -122.4022,
        "status": "Reported",
    },
    {
        "incident_type": "Structural Collapse",
        "location": "450 Howard St Commerce Corridor",
        "description": "Partial facade collapse at commercial structure following strong tremor. Bystanders report 3 people trapped beneath debris with structural shoring needed.",
        "people_affected": 3,
        "latitude": 37.7885,
        "longitude": -122.3980,
        "status": "Verified",
    },
    {
        "incident_type": "Chemical Spill",
        "location": "Islais Creek Industrial Park Gate 4",
        "description": "Overturned freight container leaking noxious chemical plume. Eye irritation reported across adjacent workshop, 12 workers evacuating.",
        "people_affected": 12,
        "latitude": 37.7480,
        "longitude": -122.3850,
        "status": "Reported",
    },
    {
        "incident_type": "Medical Emergency",
        "location": "Civic Center Plaza Transit Concourse",
        "description": "Multiple individuals experiencing heat exhaustion and fainting amid power disruption. 2 elderly patients requiring cardiac monitoring.",
        "people_affected": 4,
        "latitude": 37.7795,
        "longitude": -122.4170,
        "status": "Assigned",
    },
    {
        "incident_type": "Fire",
        "location": "Potrero Hill Warehouse Row",
        "description": "Commercial timber yard fire spreading towards adjacent storage sheds. Dense black smoke billowing, zero injuries confirmed so far.",
        "people_affected": 0,
        "latitude": 37.7580,
        "longitude": -122.4010,
        "status": "En Route",
    },
    {
        "incident_type": "Landslide",
        "location": "Twin Peaks Crest View Overlook",
        "description": "Fallen boulders and mud blocking secondary evacuation arterial. Roadway impassable; small passenger vehicle diverted safely.",
        "people_affected": 2,
        "latitude": 37.7540,
        "longitude": -122.4470,
        "status": "Resolved",
    },
]


def seed_database_if_empty(db: Session):
    """
    Seeds simulated incidents and rescue resources if the database is currently empty.
    All records are clearly marked as simulated/demo data.
    """
    # Check resources
    res_count = db.query(Resource).count()
    if res_count == 0:
        created_resources = []
        for r_data in DEMO_RESOURCES:
            res = Resource(
                name=r_data["name"],
                resource_type=r_data["resource_type"],
                capabilities=json.dumps(r_data["capabilities"]),
                simulated_lat=r_data["simulated_lat"],
                simulated_lng=r_data["simulated_lng"],
                simulated_location_name=r_data["simulated_location_name"],
                availability=r_data["availability"],
                capacity=r_data["capacity"],
                contact_callsign=r_data["contact_callsign"],
            )
            db.add(res)
            created_resources.append(res)
        db.commit()

    # Check incidents
    inc_count = db.query(Incident).count()
    if inc_count == 0:
        # Load resources for potential assignment demo
        all_resources = db.query(Resource).all()

        for idx, inc_data in enumerate(DEMO_INCIDENTS):
            # Evaluate triage
            triage = evaluate_incident_triage(
                incident_type=inc_data["incident_type"],
                location=inc_data["location"],
                description=inc_data["description"],
                people_affected=inc_data["people_affected"],
                latitude=inc_data["latitude"],
                longitude=inc_data["longitude"],
            )

            # Assign resource if demo status is Assigned or En Route
            assigned_res_id = None
            if inc_data["status"] in ["Assigned", "En Route"] and all_resources:
                assigned_res = all_resources[idx % len(all_resources)]
                assigned_res_id = assigned_res.id
                assigned_res.availability = "Assigned"
                assigned_res.current_incident_id = idx + 1

            inc = Incident(
                incident_type=inc_data["incident_type"],
                location=inc_data["location"],
                description=inc_data["description"],
                people_affected=inc_data["people_affected"],
                latitude=inc_data["latitude"],
                longitude=inc_data["longitude"],
                urgency=triage["urgency"],
                urgency_explanation=triage["urgency_explanation"],
                key_risks=json.dumps(triage["key_risks"]),
                recommended_capabilities=json.dumps(triage["recommended_capabilities"]),
                uncertainty_score=triage["uncertainty_score"],
                uncertainty_note=triage["uncertainty_note"],
                assessment_method=triage["assessment_method"],
                status=inc_data["status"],
                assigned_resource_id=assigned_res_id,
                reported_time=datetime.datetime.utcnow() - datetime.timedelta(minutes=15 * (idx + 1)),
            )
            db.add(inc)
            db.flush()

            # Add initial action log
            log = ActionLog(
                incident_id=inc.id,
                action_type="CREATED",
                actor="System Intake Daemon",
                details=f"Simulated incident intake registered. AI triage evaluated as {triage['urgency']}.",
            )
            db.add(log)

            if assigned_res_id:
                assign_log = ActionLog(
                    incident_id=inc.id,
                    action_type="RESOURCE_ASSIGNED",
                    actor="Dispatcher Bravo",
                    details=f"Assigned simulated unit {assigned_res.name} ({assigned_res.contact_callsign}).",
                )
                db.add(assign_log)

        db.commit()
