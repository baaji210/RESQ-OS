import json
import urllib.request
import urllib.error
import sqlite3

BASE_URL = "http://localhost:8000/api"

def request_json(url, method="GET", data=None):
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(error_body)
        except Exception:
            return e.code, {"detail": error_body}

def test_full_scenario():
    print("=" * 60)
    print("RESQ-OS SCENARIO TEST: FIRE REPORT IN BALAJI COLONY, TIRUPATI")
    print("=" * 60)

    # 1. Submit a new Fire report for Balaji Colony, Tirupati
    print("\n[Step 1 & 2] Submit new Fire report for Balaji Colony, Tirupati...")
    fire_payload = {
        "incident_type": "Fire",
        "location": "Balaji Colony, Tirupati, Andhra Pradesh",
        "description": "High-voltage transformer burst into heavy flames with dense toxic smoke near residential block. 3 residents needing emergency evacuation.",
        "people_affected": 3,
        "latitude": 13.6325,
        "longitude": 79.4150
    }
    status, created_inc = request_json(f"{BASE_URL}/incidents", method="POST", data=fire_payload)
    assert status == 201, f"Expected 201 Created, got {status}"
    inc_id = created_inc["id"]
    print(f"-> Created Incident ID: {inc_id}")
    print(f"-> Disaster Type: {created_inc['incident_type']}")
    print(f"-> Address: {created_inc['location']}")
    print(f"-> GPS: [{created_inc['latitude']}, {created_inc['longitude']}]")
    print(f"-> Urgency: {created_inc['effective_urgency']}")
    print(f"-> Next Action: {created_inc.get('recommended_next_action')}")
    print(f"-> Missing Info: {created_inc.get('missing_information')}")
    print(f"-> Status: {created_inc['status']}")
    
    assert inc_id is not None, "Missing incident ID"
    assert created_inc["status"] == "Reported", f"Expected status 'Reported', got {created_inc['status']}"
    assert created_inc["assigned_resource_id"] is None, "Reported incident should be unassigned initially"

    # Verify directly in SQLite database
    con = sqlite3.connect("backend/resq_os.db")
    cur = con.cursor()
    db_row = cur.execute("SELECT id, incident_type, location, status, assigned_resource_id FROM incidents WHERE id=?", (inc_id,)).fetchone()
    con.close()
    assert db_row is not None, f"Incident {inc_id} not found in SQLite resq_os.db"
    assert db_row[3] == "Reported", "DB status should be Reported"
    print(f"-> SQLite DB verification: Verified {db_row}")

    # 3. Confirm it appears in Dispatcher Console as pending
    print("\n[Step 3] Confirm incident appears in Dispatcher Console queue as pending...")
    status, all_incidents = request_json(f"{BASE_URL}/incidents")
    assert status == 200
    found_in_dispatcher = next((i for i in all_incidents if i["id"] == inc_id), None)
    assert found_in_dispatcher is not None, f"Incident {inc_id} not returned by GET /incidents"
    assert found_in_dispatcher["status"] == "Reported"
    assert found_in_dispatcher["assigned_resource_id"] is None
    print(f"-> Found in Dispatcher queue: ID #{found_in_dispatcher['id']} | Status: {found_in_dispatcher['status']}")

    # 4. Open Rescue Team View and confirm the new report appears in All Reports even before approval
    print("\n[Step 4] Verify Rescue Team View 'All Reports' includes this new unassigned report...")
    # RescueTeamView fetches /api/incidents
    status, rescue_view_incidents = request_json(f"{BASE_URL}/incidents")
    assert status == 200
    rescue_report = next((i for i in rescue_view_incidents if i["id"] == inc_id), None)
    assert rescue_report is not None, f"Report {inc_id} not present in Rescue Team View incident source"
    print(f"-> Rescue Team View reports list contains Signal #{rescue_report['id']} before approval")
    assert rescue_report["status"] == "Reported"
    assert rescue_report["assigned_resource_id"] is None

    # 5. Confirm address, coordinates, priority, analysis, and recommendations match the saved report
    print("\n[Step 5] Verify analysis, risks, capabilities, and resource recommendations...")
    assert rescue_report["location"] == fire_payload["location"]
    assert rescue_report["latitude"] == fire_payload["latitude"]
    assert rescue_report["longitude"] == fire_payload["longitude"]
    assert len(rescue_report["key_risks"]) > 0
    assert len(rescue_report["recommended_capabilities"]) > 0
    print(f"-> Priority: {rescue_report['effective_urgency']}")
    print(f"-> Risks: {rescue_report['key_risks']}")
    print(f"-> Capabilities: {rescue_report['recommended_capabilities']}")

    # Get recommendations
    status, recs = request_json(f"{BASE_URL}/incidents/{inc_id}/recommendations")
    assert status == 200
    print(f"-> Recommendations found: {len(recs['recommendations'])}")
    primary_rec = recs["recommendations"][0]
    print(f"-> Top recommended unit: {primary_rec['resource']['name']} ({primary_rec['resource']['contact_callsign']}) - Match: {primary_rec['match_score']}% ({primary_rec['priority_level']})")
    print(f"-> Reason: {primary_rec['recommendation_reason']}")
    assert primary_rec["is_suitable"] is True, "Top recommendation should be suitable for Fire"
    fire_unit_id = primary_rec["resource"]["id"]

    # 6. Approve and assign a suitable simulated resource
    print(f"\n[Step 6] Dispatcher approves and assigns {primary_rec['resource']['name']} (ID {fire_unit_id})...")
    assign_payload = {
        "resource_id": fire_unit_id,
        "dispatcher_notes": "Urgent structural and electrical fire deployment approved by Dispatcher Lead",
        "dispatcher_actor": "Dispatcher Lead",
        "reassign": True
    }
    status, assigned_inc = request_json(f"{BASE_URL}/incidents/{inc_id}/assignments", method="POST", data=assign_payload)
    assert status == 200, f"Assignment failed with status {status}: {assigned_inc}"
    assert assigned_inc["assigned_resource_id"] == fire_unit_id
    assert assigned_inc["status"] == "Assigned"
    print(f"-> Assignment successful: Incident #{assigned_inc['id']} status is now [{assigned_inc['status']}] with assigned unit ID {fire_unit_id}")

    # 7. Confirm the mission appears in Assigned Missions with the same incident ID
    print("\n[Step 7] Confirm mission appears in Assigned Missions for the selected unit...")
    status, team_mission = request_json(f"{BASE_URL}/resources/{fire_unit_id}/mission")
    assert status == 200
    assert team_mission["has_active_mission"] is True
    assert team_mission["incident"]["id"] == inc_id, f"Expected mission incident ID {inc_id}, got {team_mission['incident']['id']}"
    assert team_mission["incident"]["location"] == fire_payload["location"]
    assert team_mission["navigation_url"] is not None
    print(f"-> Unit {team_mission['resource']['name']} active mission is confirmed: Signal #{team_mission['incident']['id']}")
    print(f"-> Ingress address: {team_mission['incident']['location']}")
    print(f"-> Nav link: {team_mission['navigation_url']}")

    # 8. Update the mission status and confirm the change persists after refreshing
    print("\n[Step 8] Test team status progression (Accepted -> En Route -> Arrived) & persistence...")
    # Accept
    status, resp_acc = request_json(f"{BASE_URL}/resources/{fire_unit_id}/mission-status", method="POST", data={"status": "Accepted", "notes": "Engine team rolling out"})
    assert status == 200 and resp_acc["incident"]["status"] == "Accepted"
    print(f"-> Status transition 1 -> Accepted: {resp_acc['incident']['status']}")

    # En Route
    status, resp_enroute = request_json(f"{BASE_URL}/resources/{fire_unit_id}/mission-status", method="POST", data={"status": "En Route", "notes": "Sirens active on bypass"})
    assert status == 200 and resp_enroute["incident"]["status"] == "En Route"
    print(f"-> Status transition 2 -> En Route: {resp_enroute['incident']['status']}")

    # Arrived
    status, resp_arrived = request_json(f"{BASE_URL}/resources/{fire_unit_id}/mission-status", method="POST", data={"status": "Arrived", "notes": "On scene at Balaji colony"})
    assert status == 200 and resp_arrived["incident"]["status"] == "Arrived"
    print(f"-> Status transition 3 -> Arrived: {resp_arrived['incident']['status']}")

    # Persistence verification (simulated browser reload)
    status, reload_inc = request_json(f"{BASE_URL}/incidents/{inc_id}")
    status, reload_mission = request_json(f"{BASE_URL}/resources/{fire_unit_id}/mission")
    assert reload_inc["status"] == "Arrived"
    assert reload_inc["assigned_resource_id"] == fire_unit_id
    assert reload_mission["has_active_mission"] is True
    assert reload_mission["incident"]["status"] == "Arrived"
    print(f"-> Reload persistence confirmed: Incident #{inc_id} status is [{reload_inc['status']}] with unit #{reload_inc['assigned_resource_id']}")

    # 9. Confirm previous incidents remain visible and no duplicates appear
    print("\n[Step 9] Confirm previous incidents remain intact and no duplicates exist...")
    status, final_incidents = request_json(f"{BASE_URL}/incidents")
    ids = [i["id"] for i in final_incidents]
    assert len(ids) == len(set(ids)), f"Duplicate incident IDs detected: {ids}"
    assert inc_id in ids, f"Current incident {inc_id} not in final list"
    assert len(final_incidents) >= 6, f"Previous incident history preserved ({len(final_incidents)} total incidents)"
    print(f"-> All {len(final_incidents)} incidents verified unique and fully preserved across database.")

    print("\n" + "=" * 60)
    print("ALL SCENARIO CRITERIA PASSED SUCCESSFULLY (100% PASS)")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_full_scenario()
    exit(0 if success else 1)
