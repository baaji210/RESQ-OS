"""
RESQ-OS Database Cleanup & Migration Script (Approved Option A)
Executes:
1. Verification of Canonical Demonstration Incidents (IDs 1-6)
2. Removal of SQLite test records (IDs 7-33) and their action logs
3. Reset of SQLite resources to initial standby/assigned states
4. Removal of Atlas test incident 'TEST-LOCATION-ATLAS-SECTOR-1'
5. Migration of canonical demonstration incidents (1-6) into MongoDB Atlas RESQ_OS.incidents
6. Verification of consistency across both databases
"""

import json
import sqlite3
import datetime
from bson import json_util
from app.database import get_mongo_client
from app.config import MONGODB_DB_NAME, MONGODB_INCIDENTS_COLLECTION

def run_cleanup():
    print("=" * 70)
    print("EXECUTING APPROVED RESQ-OS DATABASE CLEANUP (OPTION A)")
    print("=" * 70)

    # 1. Connect to SQLite
    con = sqlite3.connect("backend/resq_os.db")
    cur = con.cursor()

    # Pre-cleanup count
    pre_incidents = cur.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    pre_logs = cur.execute("SELECT COUNT(*) FROM action_logs").fetchone()[0]
    print(f"\n[Pre-Cleanup SQLite State]: {pre_incidents} incidents, {pre_logs} action logs")

    # 2. Verify Canonical IDs 1-6
    canonical_rows = cur.execute(
        "SELECT id, incident_type, location, status, urgency, assigned_resource_id FROM incidents WHERE id <= 6 ORDER BY id"
    ).fetchall()
    assert len(canonical_rows) == 6, f"Expected 6 canonical incidents, found {len(canonical_rows)}"
    print("\nVerified Canonical Demonstration Incidents (IDs 1-6):")
    for r in canonical_rows:
        print(f"  • ID #{r[0]}: {r[1]:<20} | Status: {r[3]:<10} | Urg: {r[4]:<8} | Assigned Unit: {r[5]} | Loc: {r[2]}")

    # 3. Delete SQLite Test Incidents & Logs (IDs 7 to 33)
    test_incidents_deleted = cur.execute("DELETE FROM incidents WHERE id > 6").rowcount
    test_logs_deleted = cur.execute("DELETE FROM action_logs WHERE incident_id > 6").rowcount
    con.commit()
    print(f"\n[SQLite Cleanup]:")
    print(f"  • Deleted {test_incidents_deleted} test incidents (IDs 7 to {pre_incidents})")
    print(f"  • Deleted {test_logs_deleted} orphaned test action logs")

    # 4. Reset Rescue Fleet Resource Availability
    # Unit 4 is Assigned to Incident 4 (Medical Emergency)
    # Unit 5 is En Route to Incident 5 (Fire)
    # Units 1, 2, 3, 6 are Available on standby
    cur.execute("UPDATE resources SET availability='Available', current_incident_id=NULL WHERE id NOT IN (4, 5)")
    cur.execute("UPDATE resources SET availability='Assigned', current_incident_id=4 WHERE id=4")
    cur.execute("UPDATE resources SET availability='En Route', current_incident_id=5 WHERE id=5")
    con.commit()

    print("\n[Resource Fleet Reset]:")
    res_rows = cur.execute("SELECT id, name, availability, current_incident_id FROM resources ORDER BY id").fetchall()
    for r in res_rows:
        print(f"  • Unit #{r[0]}: {r[1]:<35} | Status: {r[2]:<12} | Assigned Incident: {r[3]}")

    # 5. Fetch clean canonical data for migration to Atlas
    incidents_data = cur.execute("""
        SELECT id, incident_type, location, description, people_affected, latitude, longitude,
               reported_time, urgency, dispatcher_urgency_override, urgency_explanation,
               key_risks, recommended_capabilities, uncertainty_score, uncertainty_note,
               assessment_method, status, assigned_resource_id, created_at, updated_at
        FROM incidents WHERE id <= 6 ORDER BY id
    """).fetchall()

    # 6. MongoDB Atlas Cleanup & Migration
    print("\n[MongoDB Atlas Migration]:")
    client = get_mongo_client()
    assert client is not None, "Could not connect to MongoDB Atlas"
    db = client[MONGODB_DB_NAME]
    coll = db[MONGODB_INCIDENTS_COLLECTION]

    # Delete existing test document
    del_res = coll.delete_many({"location": "TEST-LOCATION-ATLAS-SECTOR-1"})
    print(f"  • Removed {del_res.deleted_count} test document(s) ('TEST-LOCATION-ATLAS-SECTOR-1') from Atlas")

    # Migrate the 6 canonical incidents
    migrated_count = 0
    for row in incidents_data:
        (
            inc_id, inc_type, location, description, people_affected, latitude, longitude,
            reported_time, urgency, dispatcher_urgency_override, urgency_explanation,
            key_risks, recommended_capabilities, uncertainty_score, uncertainty_note,
            assessment_method, status, assigned_resource_id, created_at, updated_at
        ) = row

        # Fetch logs for this incident
        logs_rows = cur.execute(
            "SELECT id, action_type, actor, details, timestamp FROM action_logs WHERE incident_id=? ORDER BY id",
            (inc_id,)
        ).fetchall()

        logs_list = [
            {
                "id": l[0],
                "incident_id": inc_id,
                "action_type": l[1],
                "actor": l[2],
                "details": l[3],
                "timestamp": l[4],
            }
            for l in logs_rows
        ]

        # Parse JSON fields safely
        try:
            parsed_risks = json.loads(key_risks) if key_risks else []
        except Exception:
            parsed_risks = [key_risks] if key_risks else []

        try:
            parsed_caps = json.loads(recommended_capabilities) if recommended_capabilities else []
        except Exception:
            parsed_caps = [recommended_capabilities] if recommended_capabilities else []

        doc = {
            "id": inc_id,
            "incident_type": inc_type,
            "location": location,
            "description": description,
            "people_affected": people_affected or 1,
            "latitude": latitude,
            "longitude": longitude,
            "reported_time": reported_time,
            "urgency": urgency,
            "dispatcher_urgency_override": dispatcher_urgency_override,
            "urgency_explanation": urgency_explanation or "",
            "key_risks": parsed_risks,
            "recommended_capabilities": parsed_caps,
            "uncertainty_score": uncertainty_score or 0.2,
            "uncertainty_note": uncertainty_note,
            "assessment_method": assessment_method or "rule_based_fallback",
            "status": status,
            "assigned_resource_id": assigned_resource_id,
            "created_at": created_at,
            "updated_at": updated_at,
            "action_logs": logs_list,
        }

        # Upsert into Atlas
        coll.replace_one({"id": inc_id}, doc, upsert=True)
        migrated_count += 1
        print(f"  -> Migrated Incident #{inc_id} ({inc_type}) into Atlas with {len(logs_list)} action logs")

    con.close()

    # 7. Post-Verification
    final_atlas_count = coll.count_documents({})
    print(f"\n[Post-Cleanup Verification]:")
    print(f"  • MongoDB Atlas 'RESQ_OS.incidents' total count: {final_atlas_count} (Expected: 6)")
    assert final_atlas_count == 6, f"Expected 6 documents in Atlas, found {final_atlas_count}"

    atlas_ids = [d["id"] for d in coll.find({}, {"id": 1}).sort("id", 1)]
    print(f"  • Atlas Incident IDs present: {atlas_ids}")
    assert atlas_ids == [1, 2, 3, 4, 5, 6], f"Unexpected Atlas IDs: {atlas_ids}"

    print("\n" + "=" * 70)
    print("DATABASE CLEANUP & MIGRATION COMPLETED SUCCESSFULLY (100% PASS)")
    print("=" * 70)

if __name__ == "__main__":
    run_cleanup()
