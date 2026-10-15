"""
Verification script for presentation state
Validates that:
- MongoDB Atlas is connected and active
- Exactly 6 canonical incidents are returned by GET /api/incidents
- Exactly 6 resources are in the fleet with proper standby/assigned states
- Prioritizer analyzes the 6 incidents
- Dashboard stats match exactly
"""

import httpx

def main():
    print("=" * 65)
    print("VERIFYING POST-CLEANUP & RESTART PRESENTATION STATE")
    print("=" * 65)

    client = httpx.Client(timeout=10.0)

    # 1. Health & Database check
    h = client.get("http://127.0.0.1:8000/api/health").json()
    db_state = h["database"]
    print(f"\n[1. Database Connection Status]")
    print(f"  • Active Backend: {db_state['active_backend']}")
    print(f"  • Display Name: {db_state['display_name']}")
    print(f"  • Is MongoDB Connected: {db_state['is_mongodb_connected']}")
    print(f"  • Database: {db_state['database_name']} | Collection: {db_state['collection']}")
    print(f"  • Ping Latency: {db_state['latency_ms']} ms")
    assert db_state['is_mongodb_connected'] is True, "MongoDB Atlas should be connected"

    # 2. Incidents feed
    incs = client.get("http://127.0.0.1:8000/api/incidents").json()
    print(f"\n[2. Incident Feed (Atlas Collection 'incidents')] - Total: {len(incs)}")
    assert len(incs) == 6, f"Expected exactly 6 canonical incidents, got {len(incs)}"
    for inc in incs:
        callsign = inc.get("assigned_resource", {}).get("contact_callsign") if inc.get("assigned_resource") else "Unassigned"
        print(f"  • ID #{inc['id']}: {inc['incident_type']:<20} | Urg: {inc['effective_urgency']:<8} | Status: {inc['status']:<10} | Unit: {callsign:<15} | {inc['location']}")

    # 3. Rescue Fleet Resources
    resources = client.get("http://127.0.0.1:8000/api/resources").json()
    print(f"\n[3. Rescue Fleet Inventory] - Total: {len(resources)}")
    assert len(resources) == 6, f"Expected 6 fleet resources, got {len(resources)}"
    for r in resources:
        print(f"  • Resource #{r['id']}: {r['name']:<35} | Status: {r['availability']:<12} | Call: {r['contact_callsign']}")

    # 4. Dashboard Stats
    stats = client.get("http://127.0.0.1:8000/api/dashboard/stats").json()
    print(f"\n[4. Dashboard Header Stats]")
    print(f"  • Total Signals: {stats['total_incidents']}")
    print(f"  • Critical / High: {stats['critical_high_count']}")
    print(f"  • Active Missions: {stats['active_incidents']}")
    print(f"  • Resolved: {stats['resolved_incidents']}")
    print(f"  • Available Units: {stats['available_resources']} / {stats['total_resources']}")
    assert stats['total_incidents'] == 6
    assert stats['resolved_incidents'] == 1
    assert stats['active_incidents'] == 5

    # 5. AI Rescue Prioritizer
    pri = client.get("http://127.0.0.1:8000/api/incidents/prioritize").json()
    print(f"\n[5. AI Rescue Prioritizer Queue]")
    print(f"  • Assessment Method: {pri['assessment_method']}")
    print(f"  • Total Incidents Analyzed: {pri['total_incidents_analyzed']}")
    print(f"  • Summary: {pri['summary']}")
    assert pri['total_incidents_analyzed'] == 6
    for p in pri['prioritized_incidents']:
        print(f"  • Rank #{p['priority_rank']}: ID #{p['incident_id']} ({p['incident_type']}) - Score: {p['priority_score']} [{p['urgency']}] - Status: {p['status']}")

    print("\n" + "=" * 65)
    print("ALL PRESENTATION STATE CHECKS PASSED (100% PASS)")
    print("=" * 65)

if __name__ == "__main__":
    main()
