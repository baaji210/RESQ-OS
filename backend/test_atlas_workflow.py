"""
RESQ-OS MongoDB Atlas Workflow & Persistence Verification Script
Executes all checks specified in Step 6:
1. Backend database verification
2. Real ping check
3. Incident creation & verification
4. Document inspection in RESQ_OS -> incidents
5. Status update and persistence check
6. Connection failure handling (secret-free error reporting)
"""

import json
import time
import httpx
import os
import sys

BASE_URL = "http://127.0.0.1:8000/api"


def run_checks():
    print("=" * 65)
    print("RESQ-OS MONGODB ATLAS CONNECTIVITY & PERSISTENCE VERIFICATION")
    print("=" * 65)

    client = httpx.Client(timeout=10.0)

    # 1. Health & Database Status
    print("\n[Check 1 & 2] Querying /api/health and /api/database/status...")
    health_resp = client.get(f"{BASE_URL}/health")
    assert health_resp.status_code == 200, f"Health check failed with {health_resp.status_code}"
    health_data = health_resp.json()
    
    db_resp = client.get(f"{BASE_URL}/database/status?force=true")
    assert db_resp.status_code == 200, f"DB status failed with {db_resp.status_code}"
    db_status = db_resp.json()

    print(f"-> Active Backend: {db_status.get('active_backend')}")
    print(f"-> Display Name: {db_status.get('display_name')}")
    print(f"-> Is MongoDB Connected: {db_status.get('is_mongodb_connected')}")
    print(f"-> Target Cluster (sanitized): {db_status.get('target_cluster')}")
    print(f"-> Latency: {db_status.get('latency_ms')} ms")
    if db_status.get('error'):
        print(f"-> Status / Error Info: {db_status.get('error')}")

    # 2. Connection Failure Test (Check 9)
    print("\n[Check 9] Verifying Connection Failure Handling & Truthful Fallback...")
    from app.database import ping_mongodb, reset_mongo_client
    from app.config import sanitize_uri
    
    # Save original URI
    original_uri = os.environ.get("MONGODB_URI", "")
    try:
        # Simulate invalid host
        os.environ["MONGODB_URI"] = "mongodb+srv://mock_invalid_user:mock_invalid_pass@cluster0.nonexistent999.mongodb.net/?retryWrites=true"
        reset_mongo_client()
        fail_ping = ping_mongodb(force=True)
        assert fail_ping["connected"] is False, "Ping should fail for nonexistent cluster"
        assert "mock_invalid_pass" not in str(fail_ping), "SECURITY ALERT: Password leaked in ping result!"
        print("-> Failure handled gracefully. Connected: False.")
        print(f"-> Sanitized target: {fail_ping.get('target')}")
        print(f"-> Secret leakage check: PASSED (Zero passwords exposed in error)")
    finally:
        os.environ["MONGODB_URI"] = original_uri
        reset_mongo_client()

    # 3. Check if real MongoDB Atlas is currently connected
    if not db_status.get("is_mongodb_connected"):
        print("\n" + "*" * 65)
        print("NOTICE: MongoDB Atlas is not yet connected in backend/.env.")
        print("The system is truthfully using SQLite fallback without false claims.")
        print("To complete Checks 3-8 on live MongoDB Atlas:")
        print("Please enter your MONGODB_URI in 'backend/.env' and re-run this test.")
        print("*" * 65)
        return False

    # If MongoDB Atlas is connected, run Checks 3-8!
    print("\n[Check 3] Creating identifiable test incident on MongoDB Atlas...")
    test_payload = {
        "incident_type": "Flood / Water Rescue",
        "location": "TEST-LOCATION-ATLAS-SECTOR-1",
        "description": "VERIFICATION-TEST-INCIDENT: Flash flood containment test for MongoDB Atlas persistence.",
        "people_affected": 2,
        "latitude": 37.7749,
        "longitude": -122.4194
    }
    create_resp = client.post(f"{BASE_URL}/incidents", json=test_payload)
    assert create_resp.status_code == 201, f"Failed to create incident: {create_resp.text}"
    created_inc = create_resp.json()
    test_id = created_inc["id"]
    print(f"-> Created Test Incident ID: #{test_id}")
    print(f"-> Status: {created_inc['status']}")

    # [Check 4] Read incident back through API
    print(f"\n[Check 4] Reading Incident #{test_id} back through API...")
    get_resp = client.get(f"{BASE_URL}/incidents/{test_id}")
    assert get_resp.status_code == 200, f"Failed to get incident: {get_resp.text}"
    fetched_inc = get_resp.json()
    assert fetched_inc["id"] == test_id
    assert fetched_inc["location"] == test_payload["location"]
    print(f"-> API Readback verified successfully for Incident #{test_id}")

    # [Check 5] Verify document in MongoDB Atlas under RESQ_OS -> incidents
    print(f"\n[Check 5] Directly inspecting document in MongoDB Atlas RESQ_OS -> incidents...")
    from app.mongo_service import get_incidents_collection
    coll = get_incidents_collection()
    assert coll is not None, "Failed to get MongoDB collection handle"
    atlas_doc = coll.find_one({"id": test_id})
    assert atlas_doc is not None, f"Document #{test_id} not found in Atlas collection!"
    print(f"-> Verified document in Atlas RESQ_OS.incidents:")
    print(f"   _id: {atlas_doc.get('_id')}")
    print(f"   id: {atlas_doc.get('id')}")
    print(f"   location: {atlas_doc.get('location')}")
    print(f"   action_logs count: {len(atlas_doc.get('action_logs', []))}")

    # [Check 6] Update status and confirm change persists
    print(f"\n[Check 6] Updating status of Incident #{test_id} to 'Verified'...")
    update_resp = client.patch(f"{BASE_URL}/incidents/{test_id}/status", json={
        "status": "Verified",
        "dispatcher_actor": "Atlas Test Lead",
        "dispatcher_notes": "Verification check: Updating status via Atlas API"
    })
    assert update_resp.status_code == 200, f"Failed to update status: {update_resp.text}"
    updated_inc = update_resp.json()
    assert updated_inc["status"] == "Verified", f"Expected 'Verified', got {updated_inc['status']}"
    
    # Verify in MongoDB Atlas
    updated_atlas_doc = coll.find_one({"id": test_id})
    assert updated_atlas_doc["status"] == "Verified"
    print(f"-> Status update confirmed in MongoDB Atlas. Current status: [{updated_atlas_doc['status']}]")
    print(f"-> Audit trail in Atlas contains {len(updated_atlas_doc['action_logs'])} entries")

    # [Check 8] Check Dispatcher Console and Rescue Team View queries
    print(f"\n[Check 8] Checking Dispatcher and Rescue Team incident feeds...")
    all_resp = client.get(f"{BASE_URL}/incidents")
    assert all_resp.status_code == 200
    all_incidents = all_resp.json()
    found = [i for i in all_incidents if i["id"] == test_id]
    assert len(found) == 1, f"Expected 1 matching record, found {len(found)}"
    print(f"-> Incident #{test_id} verified in unified feed returned to both Dispatcher Console & Rescue Team View")

    print("\n" + "=" * 65)
    print("ALL MONGODB ATLAS VERIFICATION CHECKS COMPLETED SUCCESSFULLY!")
    print("=" * 65)
    return True


if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 2)
