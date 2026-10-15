import urllib.request
import json
import sqlite3

BASE_URL = "http://localhost:8000/api"

def test_prioritizer_e2e():
    print("=" * 60)
    print("RESQ-OS AI RESCUE PRIORITIZER VERIFICATION TEST")
    print("=" * 60)

    # 1. Test GET /api/incidents/prioritize
    print("\n[Step 1] Calling GET /api/incidents/prioritize...")
    req = urllib.request.Request(f"{BASE_URL}/incidents/prioritize")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200, f"Expected status 200, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))

    # 2. Validate Assessment Method and Honest Labeling
    print("\n[Step 2] Validating honest labeling and assessment method...")
    print(f"-> Assessment Method: '{data['assessment_method']}'")
    assert data["assessment_method"] in ["Rule-Based Rescue Prioritization", "AI Rescue Prioritization"], "Unexpected assessment method"
    assert data["total_incidents_analyzed"] > 0, "No incidents analyzed"
    print(f"-> Total incidents analyzed: {data['total_incidents_analyzed']}")
    print(f"-> Summary statement: {data['summary']}")

    # 3. Validate Prioritized Order of Attention
    print("\n[Step 3] Checking ranked items structure and ordering...")
    prioritized = data["prioritized_incidents"]
    assert len(prioritized) == data["total_incidents_analyzed"]
    
    # Check that rank is sequential: 1, 2, 3...
    ranks = [item["priority_rank"] for item in prioritized]
    assert ranks == list(range(1, len(prioritized) + 1)), f"Non-sequential ranks: {ranks[:10]}"
    
    # Check top items
    print(f"\nTop 5 Prioritized Incidents:")
    for item in prioritized[:5]:
        print(f"  Rank #{item['priority_rank']}: Signal #{item['incident_id']} ({item['incident_type']}) - [{item['urgency']}] Score: {item['priority_score']:.1f}")
        print(f"     Location: {item['location']}")
        print(f"     Reason: {item['urgency_reason'][:95]}...")
        if item['life_threat_indicators']:
            print(f"     Life Threats: {item['life_threat_indicators']}")
        if item['worsening_factors']:
            print(f"     Escalation: {item['worsening_factors']}")
        print(f"     Action: {item['suggested_action'][:80]}...")
        print(f"     Missing info: {item['missing_information']}")
        print(f"     Resource Summary: {item['resource_availability_summary'][:80]}...")
        print()

    # 4. Validate That Fields Exist for Every Item
    print("[Step 4] Validating schema consistency for all items...")
    for idx, item in enumerate(prioritized):
        assert "incident_id" in item and item["incident_id"] is not None
        assert "incident_type" in item and item["incident_type"]
        assert "priority_rank" in item and item["priority_rank"] == idx + 1
        assert "urgency" in item and item["urgency"] in ["Critical", "High", "Medium", "Low"]
        assert "priority_score" in item and item["priority_score"] >= 0.0
        assert "urgency_reason" in item and len(item["urgency_reason"]) > 5
        assert "suggested_action" in item and len(item["suggested_action"]) > 5
        assert "missing_information" in item and isinstance(item["missing_information"], list)
        assert "suggested_resources" in item and isinstance(item["suggested_resources"], list)
        assert "resource_availability_summary" in item and len(item["resource_availability_summary"]) > 0

        # Check resource suggestions
        for res_sugg in item["suggested_resources"]:
            assert "resource_id" in res_sugg
            assert "resource_name" in res_sugg
            assert "contact_callsign" in res_sugg
            assert "is_available" in res_sugg
            assert "match_score" in res_sugg
            assert "suitability_explanation" in res_sugg

    # 5. Verify compare logic: Trapped life threats rank higher than minor incidents
    print("[Step 5] Checking priority logic: Trapped life threats outrank general/resolved incidents...")
    top_urgencies = [item["urgency"] for item in prioritized[:3]]
    assert all(u in ["Critical", "High"] for u in top_urgencies), f"Top items should be Critical or High, got {top_urgencies}"
    
    # Check that resolved incidents are placed at the bottom
    resolved_ranks = [item["priority_rank"] for item in prioritized if item["status"] == "Resolved"]
    active_ranks = [item["priority_rank"] for item in prioritized if item["status"] != "Resolved"]
    if resolved_ranks and active_ranks:
        min_resolved = min(resolved_ranks)
        max_active = max(active_ranks)
        print(f"-> Min Resolved Rank: {min_resolved}, Max Active/Unresolved Rank: {max_active}")
        assert min_resolved > max_active, "Resolved incidents should be ranked after active/unresolved incidents"

    print("\n" + "=" * 60)
    print("ALL AI RESCUE PRIORITIZER CHECKS PASSED (100% PASS)")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_prioritizer_e2e()
    exit(0 if success else 1)
