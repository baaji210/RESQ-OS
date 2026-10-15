import json
import urllib.request
import urllib.error

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

def run_tests():
    results = {}
    print("==================================================")
    print("RESQ-OS INCIDENT-TO-RESCUE-TEAM WORKFLOW E2E TEST")
    print("==================================================")

    # 0. Clean slate / Free up Swiftwater unit if committed
    status, resources = request_json(f"{BASE_URL}/resources")
    water_unit = next((r for r in resources if "Swiftwater" in r["name"]), None)
    assert water_unit is not None, "Swiftwater unit not found"
    
    if water_unit["availability"] != "Available" and water_unit["current_incident_id"]:
        print(f"[*] Unit {water_unit['name']} is currently busy with Incident #{water_unit['current_incident_id']}. Releasing it for clean test...")
        request_json(f"{BASE_URL}/incidents/{water_unit['current_incident_id']}/unassign", method="POST")

    # Step 1: Submit new incident and save to backend database
    print("\n--- STEP 1: Submit new fictional flood incident ---")
    flood_payload = {
        "incident_type": "Flood",
        "location": "North River Levee Sector 9, West Pier Access",
        "description": "Rapid levee breach causing 4.5 feet of fast-moving water. 4 citizens trapped on commercial rooftop.",
        "people_affected": 4,
        "latitude": 37.7712,
        "longitude": -122.4041
    }
    status, created_inc = request_json(f"{BASE_URL}/incidents", method="POST", data=flood_payload)
    print(f"HTTP Status: {status}")
    print(f"Created Incident ID: {created_inc.get('id')}")
    print(f"Type: {created_inc.get('incident_type')}, Urgency: {created_inc.get('urgency')}, Status: {created_inc.get('status')}")
    print(f"Coordinates: [{created_inc.get('latitude')}, {created_inc.get('longitude')}]")
    print(f"People Affected: {created_inc.get('people_affected')}")
    
    inc_id = created_inc["id"]
    step1_pass = (
        status == 201 and 
        inc_id is not None and 
        created_inc["incident_type"] == "Flood" and
        created_inc["location"] == flood_payload["location"] and
        created_inc["latitude"] == flood_payload["latitude"] and
        created_inc["longitude"] == flood_payload["longitude"] and
        created_inc["people_affected"] == 4 and
        created_inc["status"] == "Reported" and
        created_inc["urgency"] in ["Critical", "High"]
    )
    results["Step 1: Save Incident in DB"] = "PASS" if step1_pass else "FAIL"
    print(f"Result Step 1: {results['Step 1: Save Incident in DB']}")

    # Step 2: Show the new incident in the Dispatcher Console (GET /incidents)
    print("\n--- STEP 2: Verify incident appears in Dispatcher Queue ---")
    status, all_incidents = request_json(f"{BASE_URL}/incidents")
    found_in_queue = next((i for i in all_incidents if i["id"] == inc_id), None)
    step2_pass = (
        status == 200 and
        found_in_queue is not None and
        found_in_queue["location"] == flood_payload["location"] and
        found_in_queue["latitude"] == flood_payload["latitude"] and
        found_in_queue["longitude"] == flood_payload["longitude"]
    )
    results["Step 2: Show in Dispatcher Console"] = "PASS" if step2_pass else "FAIL"
    print(f"Result Step 2: {results['Step 2: Show in Dispatcher Console']}")

    # Step 3: Dispatcher approves suitable resource assignment
    print("\n--- STEP 3: Dispatcher assigns Swiftwater Rescue Boat to incident ---")
    # Get recommendations
    status, recs = request_json(f"{BASE_URL}/incidents/{inc_id}/recommendations")
    print(f"Recommendations found: {len(recs.get('recommendations', []))}")
    water_rec = next((r for r in recs["recommendations"] if r["resource"]["id"] == water_unit["id"]), None)
    print(f"Water unit match score: {water_rec['match_score']}%, is_suitable: {water_rec['is_suitable']}, is_available: {water_rec['is_available']}")
    
    # Assign resource
    assign_payload = {
        "resource_id": water_unit["id"],
        "dispatcher_notes": "Urgent swiftwater deployment approved by Dispatcher Lead",
        "dispatcher_actor": "Dispatcher Lead"
    }
    status, assigned_inc = request_json(f"{BASE_URL}/incidents/{inc_id}/assignments", method="POST", data=assign_payload)
    print(f"Assignment response status: {status}, Incident status: {assigned_inc.get('status')}, Assigned Resource ID: {assigned_inc.get('assigned_resource_id')}")
    
    step3_pass = (
        status == 200 and 
        assigned_inc["assigned_resource_id"] == water_unit["id"] and
        assigned_inc["status"] == "Assigned"
    )
    results["Step 3: Dispatcher Assignment Approval"] = "PASS" if step3_pass else "FAIL"
    print(f"Result Step 3: {results['Step 3: Dispatcher Assignment Approval']}")

    # Step 4: Display exact reported address, GPS, description, priority, hazards, skills, map marker & nav url
    print("\n--- STEP 4: Inspect Rescue Team View mission order payload ---")
    status, team_mission = request_json(f"{BASE_URL}/resources/{water_unit['id']}/mission")
    print(f"Has active mission: {team_mission.get('has_active_mission')}")
    mission_inc = team_mission.get("incident")
    print(f"Mission Incident ID: {mission_inc.get('id')} (Matches target: {mission_inc.get('id') == inc_id})")
    print(f"Exact Address: {mission_inc.get('location')}")
    print(f"GPS Coordinates: [{mission_inc.get('latitude')}, {mission_inc.get('longitude')}]")
    print(f"Description: {mission_inc.get('description')}")
    print(f"Priority: {mission_inc.get('effective_urgency')}")
    print(f"Hazards (Key Risks): {mission_inc.get('key_risks')}")
    print(f"Recommended Skills: {mission_inc.get('recommended_capabilities')}")
    print(f"Navigation URL: {team_mission.get('navigation_url')}")
    
    step4_pass = (
        status == 200 and
        team_mission["has_active_mission"] is True and
        mission_inc is not None and
        mission_inc["id"] == inc_id and
        mission_inc["location"] == flood_payload["location"] and
        mission_inc["latitude"] == flood_payload["latitude"] and
        mission_inc["longitude"] == flood_payload["longitude"] and
        mission_inc["description"] == flood_payload["description"] and
        len(mission_inc["key_risks"]) > 0 and
        len(mission_inc["recommended_capabilities"]) > 0 and
        team_mission["navigation_url"] is not None and
        "google.com/maps/dir" in team_mission["navigation_url"]
    )
    results["Step 4: Display Exact Fields & Nav Link"] = "PASS" if step4_pass else "FAIL"
    print(f"Result Step 4: {results['Step 4: Display Exact Fields & Nav Link']}")

    # Step 5: Show only missions assigned to selected team (other teams have no active mission)
    print("\n--- STEP 5: Verify other simulated rescue teams do not show this mission ---")
    status, other_mission = request_json(f"{BASE_URL}/resources/2/mission") # US&R Task Force Squad 7
    print(f"Team 2 ({other_mission['resource']['name']}) has active mission: {other_mission.get('has_active_mission')}")
    print(f"Team 2 incident: {other_mission.get('incident')}")
    
    step5_pass = (
        status == 200 and
        other_mission["has_active_mission"] is False and
        other_mission["incident"] is None
    )
    results["Step 5: Mission Isolation per Team"] = "PASS" if step5_pass else "FAIL"
    print(f"Result Step 5: {results['Step 5: Mission Isolation per Team']}")

    # Step 6: Team updates status to Accepted, En Route, Arrived
    print("\n--- STEP 6: Team status transitions in database ---")
    # 6a. Accepted
    status, resp_acc = request_json(
        f"{BASE_URL}/resources/{water_unit['id']}/mission-status", 
        method="POST", 
        data={"status": "Accepted", "notes": "Boat team prepped and boat launched"}
    )
    acc_ok = (status == 200 and resp_acc["incident"]["status"] == "Accepted")
    print(f"Transition 1 -> Accepted: {acc_ok} (Status: {resp_acc.get('incident', {}).get('status')})")

    # 6b. En Route
    status, resp_enroute = request_json(
        f"{BASE_URL}/resources/{water_unit['id']}/mission-status", 
        method="POST", 
        data={"status": "En Route", "notes": "Navigating flood waters towards levee breach"}
    )
    enroute_ok = (status == 200 and resp_enroute["incident"]["status"] == "En Route")
    print(f"Transition 2 -> En Route: {enroute_ok} (Status: {resp_enroute.get('incident', {}).get('status')})")

    # 6c. Arrived
    status, resp_arrived = request_json(
        f"{BASE_URL}/resources/{water_unit['id']}/mission-status", 
        method="POST", 
        data={"status": "Arrived", "notes": "On scene at levee. Beginning rooftop extraction."}
    )
    arrived_ok = (status == 200 and resp_arrived["incident"]["status"] == "Arrived")
    print(f"Transition 3 -> Arrived: {arrived_ok} (Status: {resp_arrived.get('incident', {}).get('status')})")

    # Check dispatcher view reflects Arrived and audit logs
    status, disp_check = request_json(f"{BASE_URL}/incidents/{inc_id}")
    disp_ok = (disp_check["status"] == "Arrived" and len(disp_check["action_logs"]) >= 4)
    print(f"Dispatcher View Synced: status={disp_check['status']}, Action Logs={len(disp_check['action_logs'])}")
    for log in disp_check["action_logs"][:3]:
        print(f"   - Log: [{log['action_type']}] by {log['actor']}: {log['details']}")

    step6_pass = acc_ok and enroute_ok and arrived_ok and disp_ok
    results["Step 6: Team Lifecycle Status Updates in DB"] = "PASS" if step6_pass else "FAIL"
    print(f"Result Step 6: {results['Step 6: Team Lifecycle Status Updates in DB']}")

    # Step 7: Persistence check (simulated page refresh)
    print("\n--- STEP 7: Persistence across simulated refresh ---")
    status, refreshed_inc = request_json(f"{BASE_URL}/incidents/{inc_id}")
    status, refreshed_mission = request_json(f"{BASE_URL}/resources/{water_unit['id']}/mission")
    
    step7_pass = (
        refreshed_inc["id"] == inc_id and
        refreshed_inc["status"] == "Arrived" and
        refreshed_inc["assigned_resource_id"] == water_unit["id"] and
        refreshed_mission["has_active_mission"] is True and
        refreshed_mission["incident"]["status"] == "Arrived" and
        refreshed_mission["incident"]["id"] == inc_id
    )
    results["Step 7: Refresh & DB Persistence"] = "PASS" if step7_pass else "FAIL"
    print(f"Result Step 7: {results['Step 7: Refresh & DB Persistence']}")

    print("\n==================================================")
    print("FINAL SUMMARY OF STEPS:")
    print("==================================================")
    all_passed = True
    for step, res in results.items():
        print(f"{step}: {res}")
        if res != "PASS":
            all_passed = False
    
    return all_passed

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
