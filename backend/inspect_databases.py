"""
Database Inspection Utility for RESQ-OS
Inspects both MongoDB Atlas ('RESQ_OS') and SQLite ('backend/resq_os.db')
Outputs record counts, breakdown of seeded vs test records, and action logs.
"""

import json
import sqlite3
from app.database import get_mongo_client, get_active_database_info
from app.config import MONGODB_DB_NAME

def inspect_all():
    print("=" * 70)
    print("RESQ-OS DATABASE AUDIT: MONGODB ATLAS & SQLITE")
    print("=" * 70)

    # 1. MongoDB Atlas Audit
    print("\n--- 1. MONGODB ATLAS CLUSTER AUDIT ---")
    client = get_mongo_client()
    atlas_docs = []
    if client:
        try:
            db = client[MONGODB_DB_NAME]
            collections = db.list_collection_names()
            print(f"Database: {MONGODB_DB_NAME}")
            print(f"Collections present: {collections}")
            if "incidents" in collections:
                cursor = db["incidents"].find({}).sort("id", 1)
                atlas_docs = list(cursor)
                print(f"Total documents in 'incidents' collection: {len(atlas_docs)}")
                for d in atlas_docs:
                    print(f"  • ID #{d.get('id')} [{d.get('_id')}]:")
                    print(f"    Type: {d.get('incident_type')} | Urgency: {d.get('urgency')} (Override: {d.get('dispatcher_urgency_override')})")
                    print(f"    Location: {d.get('location')}")
                    print(f"    Status: {d.get('status')} | Assigned Resource ID: {d.get('assigned_resource_id')}")
                    print(f"    Action Logs: {len(d.get('action_logs', []))} entries")
                    print(f"    Description: {d.get('description')[:80]}...")
            else:
                print("No 'incidents' collection found.")
        except Exception as e:
            print(f"MongoDB inspection error: {e}")
    else:
        print("Could not connect to MongoDB Atlas.")

    # 2. SQLite Database Audit
    print("\n--- 2. LOCAL SQLITE DATABASE AUDIT (backend/resq_os.db) ---")
    con = sqlite3.connect("backend/resq_os.db")
    cur = con.cursor()

    # Tables list
    tables = [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"Tables present: {tables}")

    # Count records
    incident_count = cur.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    resource_count = cur.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
    log_count = cur.execute("SELECT COUNT(*) FROM action_logs").fetchone()[0]

    print(f"Record counts:")
    print(f"  • incidents: {incident_count}")
    print(f"  • resources: {resource_count}")
    print(f"  • action_logs: {log_count}")

    # Fetch all incidents
    incidents = cur.execute(
        "SELECT id, incident_type, location, status, urgency, dispatcher_urgency_override, people_affected, assigned_resource_id, description FROM incidents ORDER BY id"
    ).fetchall()

    print("\nSQLite Incidents Breakdown:")
    for inc in incidents:
        inc_id, inc_type, location, status, urgency, override, people, assigned_id, desc = inc
        # Check logs count for this incident
        inc_logs = cur.execute("SELECT COUNT(*) FROM action_logs WHERE incident_id=?", (inc_id,)).fetchone()[0]
        print(f"  • ID #{inc_id:2d} | Type: {inc_type:<20} | Status: {status:<10} | Urg: {urgency:<8} (Override: {str(override):<8}) | Logs: {inc_logs} | Loc: {location}")
        print(f"      Desc: {desc[:80]}...")

    # Resources
    resources = cur.execute("SELECT id, name, availability, current_incident_id FROM resources ORDER BY id").fetchall()
    print("\nSQLite Resource Inventory Status:")
    for r in resources:
        r_id, r_name, avail, cur_inc = r
        print(f"  • Resource #{r_id}: {r_name:<35} | Status: {avail:<12} | Assigned Incident: {cur_inc}")

    con.close()

if __name__ == "__main__":
    inspect_all()
