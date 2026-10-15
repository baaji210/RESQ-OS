import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { 
  Truck, 
  MapPin, 
  Navigation, 
  ExternalLink, 
  CheckCircle, 
  Radio, 
  ShieldAlert, 
  Clock, 
  Users, 
  Flame, 
  Waves, 
  Activity, 
  AlertTriangle, 
  Check, 
  Send, 
  ArrowRight,
  Info,
  Compass,
  Cpu,
  Bot,
  Building2,
  AlertOctagon,
  Wind,
  Filter,
  Search,
  RefreshCw,
  Sparkles,
  HelpCircle,
  CheckCircle2,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  X,
  AlertCircle,
  Zap,
  Award
} from 'lucide-react';
import { api } from '../services/api';

// Map controller to center on the active incident/mission coordinates
function MissionMapFocus({ lat, lng }) {
  const map = useMap();
  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize();
      if (lat !== null && lng !== null && !isNaN(lat) && !isNaN(lng)) {
        map.flyTo([lat, lng], 14, { duration: 0.8 });
      }
    }, 150);
    return () => clearTimeout(timer);
  }, [lat, lng, map]);
  return null;
}

// Marker icon for incident
function createIncidentPin(urgency) {
  const color = urgency === 'Critical' ? '#dc2626' : urgency === 'High' ? '#ea580c' : urgency === 'Medium' ? '#d97706' : '#0284c7';
  const html = `
    <div style="position: relative; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">
      <div style="position: absolute; inset: -4px; border-radius: 50%; background-color: ${color}; opacity: 0.35;" class="pulse-indicator"></div>
      <div style="
        width: 32px; 
        height: 32px; 
        border-radius: 50%; 
        background-color: ${color}; 
        border: 2px solid #ffffff; 
        box-shadow: 0 2px 8px rgba(0,0,0,0.3); 
        display: flex; 
        align-items: center; 
        justify-content: center; 
        color: #ffffff; 
        font-weight: 800; 
        font-size: 13px;
      ">!</div>
    </div>
  `;
  return L.divIcon({
    html,
    className: 'custom-leaflet-marker',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });
}

// Marker icon for team base / vehicle
function createTeamPin(isDeployed = false) {
  const bgColor = isDeployed ? '#0284c7' : '#16a34a';
  const html = `
    <div style="
      width: 28px; 
      height: 28px; 
      border-radius: 6px; 
      background-color: ${bgColor}; 
      border: 2px solid #ffffff; 
      box-shadow: 0 2px 6px rgba(0,0,0,0.25); 
      display: flex; 
      align-items: center; 
      justify-content: center; 
      color: #ffffff; 
      font-weight: 700; 
      font-size: 12px;
    ">⛑</div>
  `;
  return L.divIcon({
    html,
    className: 'custom-resource-marker',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function getIncidentIcon(type) {
  const t = (type || '').toLowerCase();
  if (t.includes('flood') || t.includes('water')) return <Waves size={15} className="text-cyan shrink-0" />;
  if (t.includes('fire')) return <Flame size={15} className="text-critical shrink-0" />;
  if (t.includes('collapse') || t.includes('earthquake')) return <Building2 size={15} className="text-high shrink-0" />;
  if (t.includes('chemical') || t.includes('hazmat')) return <AlertOctagon size={15} className="text-medium shrink-0" />;
  if (t.includes('medical')) return <Activity size={15} className="text-critical shrink-0" />;
  if (t.includes('storm')) return <Wind size={15} className="text-cyan shrink-0" />;
  return <AlertTriangle size={15} className="text-secondary shrink-0" />;
}

export default function RescueTeamView({ 
  health,
  incidents = [],
  resources = [], 
  selectedTeamId = null,
  onSelectTeamId,
  onSwitchToDispatcher,
  onMissionUpdated 
}) {
  // Local incidents state to guarantee live synchronization with persistent backend database
  const [localIncidents, setLocalIncidents] = useState(incidents);
  const [selectedResourceId, setSelectedResourceId] = useState(selectedTeamId);
  const [missionData, setMissionData] = useState(null);
  const [loadingMission, setLoadingMission] = useState(false);
  const [syncingAll, setSyncingAll] = useState(false);
  const [error, setError] = useState(null);
  const [fieldNote, setFieldNote] = useState('');
  const [updatingStatus, setUpdatingStatus] = useState(false);

  // Inspected incident for AI-assisted analysis and tactical inspection
  const [inspectedIncidentId, setInspectedIncidentId] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [recLoading, setRecLoading] = useState(false);

  // Overview Filters: 'all' | 'pending' | 'assigned' | 'active' | 'resolved'
  const [overviewFilter, setOverviewFilter] = useState('all');
  const [overviewSearch, setOverviewSearch] = useState('');

  // AI Rescue Prioritizer State
  const [prioritizerData, setPrioritizerData] = useState(null);
  const [prioritizing, setPrioritizing] = useState(false);
  const [prioritizerError, setPrioritizerError] = useState(null);
  const [showPrioritizerPanel, setShowPrioritizerPanel] = useState(false);
  const [prioritizerTab, setPrioritizerTab] = useState('all'); // 'all', 'critical', 'pending'

  // Keep local incidents in sync with props
  useEffect(() => {
    if (incidents && incidents.length > 0) {
      setLocalIncidents(incidents);
    }
  }, [incidents]);

  // Synchronize fresh incident data from persistent backend database
  const fetchAllIncidents = useCallback(async () => {
    setSyncingAll(true);
    try {
      const data = await api.getIncidents();
      setLocalIncidents(data);
      if (onMissionUpdated) onMissionUpdated();
    } catch (err) {
      console.warn('Background sync error:', err);
    } finally {
      setSyncingAll(false);
    }
  }, [onMissionUpdated]);

  // Periodic polling every 6 seconds to ensure new reports appear immediately
  useEffect(() => {
    const timer = setInterval(() => {
      fetchAllIncidents();
    }, 6000);
    return () => clearInterval(timer);
  }, [fetchAllIncidents]);

  // Trigger AI Rescue Prioritizer
  const handleRunPrioritizer = async () => {
    setPrioritizing(true);
    setPrioritizerError(null);
    try {
      const result = await api.getPrioritizedIncidents();
      setPrioritizerData(result);
      setShowPrioritizerPanel(true);
      // Auto-inspect the top-priority incident
      if (result.prioritized_incidents && result.prioritized_incidents.length > 0) {
        setInspectedIncidentId(result.prioritized_incidents[0].incident_id);
      }
    } catch (err) {
      console.error('Prioritizer execution error:', err);
      setPrioritizerError(err.message || 'Failed to complete incident prioritization analysis');
    } finally {
      setPrioritizing(false);
    }
  };

  // All incidents from database sorted latest (highest ID / newest timestamp) first
  const allIncidentsSorted = useMemo(() => {
    return [...(localIncidents || [])].sort((a, b) => b.id - a.id);
  }, [localIncidents]);

  // Assigned missions (not resolved)
  const activeMissions = useMemo(() => {
    return allIncidentsSorted.filter((i) => i.assigned_resource_id && i.status !== 'Resolved');
  }, [allIncidentsSorted]);

  // Unassigned incidents (pending dispatch)
  const pendingIncidents = useMemo(() => {
    return allIncidentsSorted.filter((i) => !i.assigned_resource_id && i.status !== 'Resolved');
  }, [allIncidentsSorted]);

  // Active missions in progress (En Route or Arrived)
  const inProgressMissions = useMemo(() => {
    return allIncidentsSorted.filter((i) => ['En Route', 'Arrived'].includes(i.status));
  }, [allIncidentsSorted]);

  // Resolved incidents
  const resolvedIncidents = useMemo(() => {
    return allIncidentsSorted.filter((i) => i.status === 'Resolved');
  }, [allIncidentsSorted]);

  // Filtered incidents for the Incident Overview section
  const filteredOverviewIncidents = useMemo(() => {
    return allIncidentsSorted.filter((inc) => {
      // Filter tab
      if (overviewFilter === 'pending') {
        if (inc.status === 'Resolved' || inc.assigned_resource_id) return false;
      } else if (overviewFilter === 'assigned') {
        if (!inc.assigned_resource_id || inc.status === 'Resolved') return false;
      } else if (overviewFilter === 'active') {
        if (!['En Route', 'Arrived'].includes(inc.status)) return false;
      } else if (overviewFilter === 'resolved') {
        if (inc.status !== 'Resolved') return false;
      }

      // Search query
      if (overviewSearch.trim()) {
        const q = overviewSearch.toLowerCase().trim();
        const matchId = String(inc.id).includes(q);
        const matchType = inc.incident_type?.toLowerCase().includes(q);
        const matchLoc = inc.location?.toLowerCase().includes(q);
        const matchDesc = inc.description?.toLowerCase().includes(q);
        const matchUnit = inc.assigned_resource?.name?.toLowerCase().includes(q) || 
                          inc.assigned_resource?.contact_callsign?.toLowerCase().includes(q);
        if (!matchId && !matchType && !matchLoc && !matchDesc && !matchUnit) return false;
      }

      return true;
    });
  }, [allIncidentsSorted, overviewFilter, overviewSearch]);

  // Auto-select latest eligible assigned mission or selectedTeamId
  useEffect(() => {
    if (selectedTeamId) {
      setSelectedResourceId(selectedTeamId);
      return;
    }
    // If no team explicitly passed, auto-select the team with the LATEST active mission
    if (activeMissions.length > 0) {
      const latestTeamId = activeMissions[0].assigned_resource_id;
      setSelectedResourceId(latestTeamId);
      if (onSelectTeamId) onSelectTeamId(latestTeamId);
    } else if (resources && resources.length > 0 && !selectedResourceId) {
      const activeTeam = resources.find((r) => r.current_incident_id);
      const chosen = activeTeam ? activeTeam.id : resources[0].id;
      setSelectedResourceId(chosen);
      if (onSelectTeamId) onSelectTeamId(chosen);
    }
  }, [selectedTeamId, activeMissions.length, resources.length]);

  // Fetch selected team's mission details
  const fetchMission = useCallback(async (resId) => {
    if (!resId) return;
    setLoadingMission(true);
    setError(null);
    try {
      const data = await api.getTeamMission(resId);
      setMissionData(data);
    } catch (err) {
      setError(err.message || 'Failed to fetch team mission data');
    } finally {
      setLoadingMission(false);
    }
  }, []);

  useEffect(() => {
    if (selectedResourceId) {
      fetchMission(selectedResourceId);
    }
  }, [selectedResourceId, fetchMission]);

  // Determine active inspected incident
  const activeIncident = useMemo(() => {
    if (inspectedIncidentId) {
      const found = allIncidentsSorted.find((i) => i.id === inspectedIncidentId);
      if (found) return found;
    }
    if (missionData?.has_active_mission && missionData?.incident) {
      return missionData.incident;
    }
    if (allIncidentsSorted.length > 0) {
      return allIncidentsSorted[0];
    }
    return null;
  }, [inspectedIncidentId, allIncidentsSorted, missionData]);

  // Fetch recommendations for active inspected incident
  useEffect(() => {
    if (!activeIncident?.id) {
      setRecommendations(null);
      return;
    }
    let isMounted = true;
    setRecLoading(true);
    api.getRecommendations(activeIncident.id)
      .then((data) => {
        if (isMounted) setRecommendations(data);
      })
      .catch((err) => {
        console.warn('Recommendations fetch warning:', err);
      })
      .finally(() => {
        if (isMounted) setRecLoading(false);
      });
    return () => { isMounted = false; };
  }, [activeIncident?.id]);

  // Field Team Status Transition handler
  const handleStatusUpdate = async (newStatus) => {
    if (!selectedResourceId) return;
    setUpdatingStatus(true);
    try {
      const updated = await api.updateTeamMissionStatus(selectedResourceId, newStatus, fieldNote);
      setMissionData(updated);
      setFieldNote('');
      // Refresh local incident list and broadcast
      await fetchAllIncidents();
      if (onMissionUpdated) onMissionUpdated();
    } catch (err) {
      alert(`Status update failed: ${err.message}`);
    } finally {
      setUpdatingStatus(false);
    }
  };

  const selectedTeam = resources.find((r) => r.id === Number(selectedResourceId)) || missionData?.resource;
  const teamMissionIncident = missionData?.incident;
  const hasActiveTeamMission = missionData?.has_active_mission && teamMissionIncident;

  const activeEffectiveUrgency = activeIncident 
    ? (activeIncident.dispatcher_urgency_override || activeIncident.urgency) 
    : 'Medium';

  // Filtered list of prioritized items inside the prioritizer panel
  const displayedPrioritizedItems = useMemo(() => {
    if (!prioritizerData || !prioritizerData.prioritized_incidents) return [];
    if (prioritizerTab === 'critical') {
      return prioritizerData.prioritized_incidents.filter((i) => i.urgency === 'Critical' && i.status !== 'Resolved');
    }
    if (prioritizerTab === 'pending') {
      return prioritizerData.prioritized_incidents.filter((i) => !i.assigned_resource_id && i.status !== 'Resolved');
    }
    return prioritizerData.prioritized_incidents;
  }, [prioritizerData, prioritizerTab]);

  return (
    <div style={{ padding: '0.85rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '0.85rem', minHeight: 'calc(100vh - 150px)', overflowY: 'auto', backgroundColor: '#f8fafc' }}>
      
      {/* 1. Simulation Safety Disclaimer Banner */}
      <div style={{
        backgroundColor: '#fffbeb',
        border: '1px solid #fcd34d',
        borderRadius: '6px',
        padding: '0.6rem 1rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '0.75rem',
        color: '#92400e',
        boxShadow: 'var(--shadow-sm)'
      }}>
        <div className="flex items-center gap-2">
          <ShieldAlert size={16} className="shrink-0 text-amber-600" />
          <span>
            <strong>SIMULATED RESPONDER TERMINAL (MDT):</strong> Connected to {health?.database?.display_name || 'Database'}. Real-world 911 dispatch networks not connected. Operational decision support simulation only.
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            style={{ fontSize: '0.7rem', padding: '0.2rem 0.55rem' }}
            onClick={fetchAllIncidents}
            disabled={syncingAll}
            title="Force refresh all incident telemetry from backend database"
          >
            <RefreshCw size={12} className={syncingAll ? 'animate-spin text-cyan' : 'text-secondary'} />
            <span>Sync DB</span>
          </button>
          <span className="badge badge-sim mono text-xs">OFFLINE-SAFE SIM</span>
        </div>
      </div>

      {/* 2. INCIDENT OVERVIEW & AI RESCUE ASSISTANT SECTION */}
      <div className="panel" style={{ padding: '0.9rem 1.25rem', backgroundColor: '#ffffff', border: '1px solid var(--border-subtle)', boxShadow: 'var(--shadow-panel)' }}>
        {/* Header with Title and Prominent AI Rescue Assistant Button */}
        <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <Radio size={16} className="text-cyan animate-pulse" />
            <h2 className="text-sm font-bold text-main uppercase tracking-wider">
              Emergency Incident Overview &amp; Incident Reports ({allIncidentsSorted.length})
            </h2>
            <span className="badge badge-rule text-xs">Persistent DB</span>
          </div>

          {/* Right Action Controls: AI Rescue Assistant button + Search */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* PROMINENT AI RESCUE ASSISTANT BUTTON */}
            <button
              type="button"
              className="btn btn-cyan font-bold flex items-center gap-1.5"
              style={{
                fontSize: '0.75rem',
                padding: '0.4rem 0.9rem',
                backgroundColor: '#0284c7',
                borderColor: '#0369a1',
                boxShadow: '0 2px 4px rgba(2, 132, 199, 0.2)'
              }}
              onClick={handleRunPrioritizer}
              disabled={prioritizing}
              title="Analyze all reported emergencies, recommend order of attention, and suggest suitable resources"
            >
              <Sparkles size={14} className={prioritizing ? "animate-spin text-white" : "text-white"} />
              <span>{prioritizing ? "AI Assistant Analyzing All Reports..." : "AI Rescue Assistant — Analyze All Reports"}</span>
            </button>

            {prioritizerData && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.72rem', padding: '0.35rem 0.65rem' }}
                onClick={() => setShowPrioritizerPanel(!showPrioritizerPanel)}
                title="Toggle Prioritizer Recommendations Panel"
              >
                {showPrioritizerPanel ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                <span>{showPrioritizerPanel ? 'Hide Prioritizer' : 'Show Prioritizer'}</span>
              </button>
            )}

            {/* Search box */}
            <div style={{ position: 'relative', width: '220px' }}>
              <Search size={13} className="text-muted" style={{ position: 'absolute', left: '9px', top: '9px' }} />
              <input
                type="text"
                className="input text-xs"
                style={{ paddingLeft: '28px', height: '32px' }}
                placeholder="Search reports or ID..."
                value={overviewSearch}
                onChange={(e) => setOverviewSearch(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Loading Indicator while Prioritizer runs */}
        {prioritizing && (
          <div style={{
            margin: '0.5rem 0 1rem 0',
            padding: '1rem',
            backgroundColor: '#f0f9ff',
            border: '1px solid #bae6fd',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.75rem',
            color: '#0369a1',
            fontSize: '0.78rem'
          }}>
            <Sparkles size={18} className="animate-spin text-cyan" />
            <div>
              <strong className="text-main">AI Rescue Assistant analyzing {allIncidentsSorted.length} emergency signals...</strong>
              <div className="text-xs text-secondary mt-0.5 font-medium">
                Evaluating immediate life threat, trapped casualties, worsening hazard conditions, and matching suitable simulated fleet assets.
              </div>
            </div>
          </div>
        )}

        {/* Error message if Prioritizer fails */}
        {prioritizerError && (
          <div style={{
            margin: '0.5rem 0 1rem 0',
            padding: '0.75rem 1rem',
            backgroundColor: '#fef2f2',
            border: '1px solid #fca5a5',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            color: '#b91c1c',
            fontSize: '0.75rem'
          }}>
            <div className="flex items-center gap-2">
              <AlertCircle size={16} className="text-critical shrink-0" />
              <span>Prioritization Analysis Error: {prioritizerError}</span>
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              style={{ fontSize: '0.68rem', padding: '0.15rem 0.5rem' }}
              onClick={handleRunPrioritizer}
            >
              Retry Analysis
            </button>
          </div>
        )}

        {/* AI RESCUE PRIORITIZER RECOMMENDATION PANEL (CORE FEATURE) */}
        {showPrioritizerPanel && prioritizerData && (
          <div style={{
            margin: '0.5rem 0 1.25rem 0',
            padding: '1rem',
            backgroundColor: '#ffffff',
            border: '2px solid #0284c7',
            borderRadius: '8px',
            boxShadow: '0 4px 16px rgba(2, 132, 199, 0.1)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.85rem'
          }}>
            {/* Prioritizer Banner Header */}
            <div className="flex items-center justify-between flex-wrap gap-2 pb-2" style={{ borderBottom: '1px solid #e2e8f0' }}>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="badge badge-rule font-bold text-xs flex items-center gap-1.5" style={{ padding: '0.25rem 0.6rem' }}>
                  <Cpu size={14} className="text-cyan" />
                  <span>{prioritizerData.assessment_method.toUpperCase()}</span>
                </span>
                <span className="text-xs text-secondary font-bold uppercase tracking-wider">
                  RECOMMENDED ORDER OF ATTENTION &bull; RESCUE RESOURCE OPTIMIZATION
                </span>
                <span className="badge badge-sim text-xs">
                  {prioritizerData.total_incidents_analyzed} Signals Evaluated
                </span>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-muted mono font-medium">
                  Generated: {new Date(prioritizerData.timestamp).toLocaleTimeString()}
                </span>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ padding: '0.2rem 0.45rem' }}
                  onClick={() => setShowPrioritizerPanel(false)}
                  title="Close Prioritizer Panel"
                >
                  <X size={14} />
                </button>
              </div>
            </div>

            {/* Tactical Summary Statement */}
            <div style={{
              backgroundColor: '#f8fafc',
              padding: '0.65rem 0.9rem',
              borderRadius: '6px',
              border: '1px solid #e2e8f0',
              fontSize: '0.75rem',
              lineHeight: 1.45,
              color: '#1e293b'
            }}>
              <div className="flex items-center gap-2 mb-1">
                <Sparkles size={14} className="text-amber-500" />
                <strong className="text-main">AI Situational Assessment Summary:</strong>
              </div>
              <p style={{ margin: 0 }}>{prioritizerData.summary}</p>
            </div>

            {/* Filter tabs inside Prioritizer */}
            <div className="flex items-center gap-1.5 flex-wrap" style={{ fontSize: '0.72rem' }}>
              <span className="text-xs text-muted font-bold mr-1">Filter Priority Queue:</span>
              <button
                type="button"
                className={`btn btn-sm ${prioritizerTab === 'all' ? 'btn-cyan font-bold' : 'btn-secondary'}`}
                style={{ fontSize: '0.7rem', padding: '0.15rem 0.55rem' }}
                onClick={() => setPrioritizerTab('all')}
              >
                All Ranked ({prioritizerData.prioritized_incidents.length})
              </button>
              <button
                type="button"
                className={`btn btn-sm ${prioritizerTab === 'critical' ? 'btn-cyan font-bold' : 'btn-secondary'}`}
                style={{ fontSize: '0.7rem', padding: '0.15rem 0.55rem' }}
                onClick={() => setPrioritizerTab('critical')}
              >
                Critical Only ({prioritizerData.prioritized_incidents.filter(i => i.urgency === 'Critical' && i.status !== 'Resolved').length})
              </button>
              <button
                type="button"
                className={`btn btn-sm ${prioritizerTab === 'pending' ? 'btn-cyan font-bold' : 'btn-secondary'}`}
                style={{ fontSize: '0.7rem', padding: '0.15rem 0.55rem' }}
                onClick={() => setPrioritizerTab('pending')}
              >
                Pending Dispatch Only ({prioritizerData.prioritized_incidents.filter(i => !i.assigned_resource_id && i.status !== 'Resolved').length})
              </button>
            </div>

            {/* List of Prioritized Cards */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.65rem',
              maxHeight: '380px',
              overflowY: 'auto',
              paddingRight: '4px'
            }}>
              {displayedPrioritizedItems.map((item) => {
                const isSelected = activeIncident?.id === item.incident_id;
                const isAssigned = Boolean(item.assigned_resource_id);
                const urgency = item.urgency;
                const rankColor = urgency === 'Critical' ? '#dc2626' : urgency === 'High' ? '#ea580c' : urgency === 'Medium' ? '#d97706' : '#0284c7';

                return (
                  <div
                    key={item.incident_id}
                    style={{
                      backgroundColor: isSelected ? '#f0f9ff' : '#ffffff',
                      border: isSelected ? '2px solid #0284c7' : '1px solid #e2e8f0',
                      borderLeft: `5px solid ${rankColor}`,
                      borderRadius: '6px',
                      padding: '0.75rem 1rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.5rem',
                      boxShadow: 'var(--shadow-sm)',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {/* Top Row: Rank Badge, ID, Type, Urgency, Score, Status */}
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          style={{
                            backgroundColor: rankColor,
                            color: '#ffffff',
                            fontWeight: 800,
                            fontSize: '0.7rem',
                            padding: '0.15rem 0.55rem',
                            borderRadius: '4px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '3px'
                          }}
                        >
                          <Award size={12} />
                          <span>RANK #{item.priority_rank}</span>
                        </span>

                        <span className="mono text-cyan font-bold text-xs">
                          Signal #{item.incident_id}
                        </span>
                        
                        <span className="font-bold text-main text-xs flex items-center gap-1">
                          {getIncidentIcon(item.incident_type)}
                          <span>{item.incident_type}</span>
                        </span>

                        <span className={`badge badge-${urgency.toLowerCase()}`} style={{ fontSize: '0.65rem' }}>
                          {urgency} PRIORITY
                        </span>

                        <span className="badge badge-rule mono" style={{ fontSize: '0.65rem' }}>
                          Score: {Math.round(item.priority_score)}/100
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5 text-xs">
                        {isAssigned ? (
                          <span className="badge" style={{ backgroundColor: '#f0f9ff', color: '#0369a1', border: '1px solid #bae6fd', fontSize: '0.65rem' }}>
                            ✓ ASSIGNED ({item.assigned_resource_callsign || 'Unit Deployed'})
                          </span>
                        ) : (
                          <span className="badge" style={{ backgroundColor: '#fffbeb', color: '#b45309', border: '1px solid #fcd34d', fontSize: '0.65rem' }}>
                            ⏳ PENDING DISPATCH
                          </span>
                        )}
                        <span className={`badge-status ${item.status}`} style={{ fontSize: '0.65rem' }}>
                          {item.status}
                        </span>
                      </div>
                    </div>

                    {/* Location & GPS */}
                    <div className="text-xs text-secondary flex items-center gap-1.5 truncate font-medium">
                      <MapPin size={12} className={item.latitude && item.longitude ? 'text-cyan shrink-0' : 'text-amber-600 shrink-0'} />
                      <strong className="text-main truncate">{item.location}</strong>
                      {item.latitude && item.longitude ? (
                        <span className="text-cyan mono text-xs shrink-0 font-semibold">
                          [{item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}]
                        </span>
                      ) : (
                        <span className="text-amber-700 text-xs shrink-0 font-medium">(Manual Address)</span>
                      )}
                      <span className="text-muted shrink-0">&bull; {item.people_affected} affected individuals</span>
                    </div>

                    {/* Rationale for Recommended Priority */}
                    <div style={{ backgroundColor: '#f8fafc', padding: '0.55rem 0.75rem', borderRadius: '4px', border: '1px solid #e2e8f0', fontSize: '0.72rem' }}>
                      <div className="text-xs text-cyan font-bold uppercase mb-0.5 flex items-center gap-1">
                        <Zap size={12} />
                        <span>Why This Incident Needs Attention:</span>
                      </div>
                      <p className="text-main font-medium" style={{ margin: 0, lineHeight: 1.45 }}>
                        {item.urgency_reason}
                      </p>

                      {/* Life Threat & Worsening Badges */}
                      {(item.life_threat_indicators.length > 0 || item.worsening_factors.length > 0) && (
                        <div className="flex items-center gap-1.5 flex-wrap mt-1.5 pt-1.5" style={{ borderTop: '1px solid #e2e8f0' }}>
                          {item.life_threat_indicators.map((lt, idx) => (
                            <span key={idx} className="badge badge-critical" style={{ fontSize: '0.62rem', padding: '0.1rem 0.4rem' }}>
                              🚨 {lt}
                            </span>
                          ))}
                          {item.worsening_factors.map((wf, idx) => (
                            <span key={idx} className="badge badge-high" style={{ fontSize: '0.62rem', padding: '0.1rem 0.4rem' }}>
                              ⚡ {wf}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Suggested Next Assessment or Response Action */}
                    <div className="text-xs flex items-start gap-1.5" style={{ color: '#0369a1' }}>
                      <Navigation size={13} className="shrink-0 mt-0.5 text-cyan" />
                      <span><strong>Suggested Action:</strong> {item.suggested_action}</span>
                    </div>

                    {/* Missing Information for Responders */}
                    {item.missing_information && item.missing_information.length > 0 && (
                      <div className="text-xs flex items-start gap-1.5" style={{ color: '#b45309' }}>
                        <HelpCircle size={13} className="shrink-0 mt-0.5 text-amber-600" />
                        <span><strong>Verify on Intake:</strong> {item.missing_information.join(' • ')}</span>
                      </div>
                    )}

                    {/* Suggested Rescue Resources Preview */}
                    <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: '0.45rem' }}>
                      <div className="flex items-center justify-between text-xs text-muted mb-1 flex-wrap gap-1">
                        <span className="flex items-center gap-1 font-semibold text-secondary">
                          <Truck size={12} className="text-cyan" />
                          <span>Suggested Rescue Resources ({item.suggested_resources.length} Suitable Evaluated):</span>
                        </span>
                        <span className="text-muted" style={{ fontSize: '0.68rem' }}>
                          {item.resource_availability_summary}
                        </span>
                      </div>

                      {/* Available units strip */}
                      <div className="flex items-center gap-2 flex-wrap">
                        {item.suggested_resources.map((res) => (
                          <div
                            key={res.resource_id}
                            style={{
                              backgroundColor: res.is_available ? '#f0fdf4' : '#f8fafc',
                              border: `1px solid ${res.is_available ? '#86efac' : '#cbd5e1'}`,
                              borderRadius: '4px',
                              padding: '0.3rem 0.55rem',
                              fontSize: '0.68rem',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.4rem'
                            }}
                          >
                            <span className={res.is_available ? 'text-low font-bold' : 'text-secondary font-medium'}>
                              [{res.contact_callsign}] {res.resource_name}
                            </span>
                            <span className="badge badge-rule" style={{ fontSize: '0.6rem', padding: '0.05rem 0.3rem' }}>
                              {res.match_score}% Match
                            </span>
                            <span className={res.is_available ? 'text-low font-semibold' : 'text-amber-600 font-semibold'}>
                              {res.availability}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Card Action Controls */}
                    <div className="flex items-center justify-between pt-1 mt-0.5" style={{ borderTop: '1px solid #e2e8f0' }}>
                      <button
                        type="button"
                        className="btn btn-sm btn-cyan font-bold"
                        style={{ fontSize: '0.68rem', padding: '0.2rem 0.55rem' }}
                        onClick={() => {
                          setInspectedIncidentId(item.incident_id);
                          if (item.assigned_resource_id) {
                            setSelectedResourceId(item.assigned_resource_id);
                            if (onSelectTeamId) onSelectTeamId(item.assigned_resource_id);
                          }
                        }}
                      >
                        <span>Inspect in Terminal &amp; Map &rarr;</span>
                      </button>

                      <div className="flex items-center gap-2">
                        {!isAssigned && onSwitchToDispatcher && (
                          <button
                            type="button"
                            className="btn btn-sm btn-primary font-bold"
                            style={{ fontSize: '0.68rem', padding: '0.2rem 0.55rem' }}
                            onClick={() => {
                              const incObj = allIncidentsSorted.find((i) => i.id === item.incident_id);
                              if (incObj) onSwitchToDispatcher(incObj);
                            }}
                          >
                            <span>Approve Dispatch in Console &rarr;</span>
                          </button>
                        )}
                        {isAssigned && (
                          <button
                            type="button"
                            className="btn btn-sm btn-secondary font-semibold"
                            style={{ fontSize: '0.68rem', padding: '0.2rem 0.55rem' }}
                            onClick={() => {
                              setSelectedResourceId(item.assigned_resource_id);
                              if (onSelectTeamId) onSelectTeamId(item.assigned_resource_id);
                            }}
                          >
                            <span>View Unit Terminal</span>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Filter Tab Buttons for Incident Overview */}
        <div className="flex items-center gap-1.5 flex-wrap mb-3" style={{ borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
          <button
            type="button"
            className={`btn btn-sm ${overviewFilter === 'all' ? 'btn-cyan font-bold' : 'btn-secondary'}`}
            style={{ fontSize: '0.72rem', padding: '0.25rem 0.65rem' }}
            onClick={() => setOverviewFilter('all')}
          >
            All Reports ({allIncidentsSorted.length})
          </button>
          <button
            type="button"
            className={`btn btn-sm ${overviewFilter === 'pending' ? 'btn-cyan font-bold' : 'btn-secondary'}`}
            style={{ fontSize: '0.72rem', padding: '0.25rem 0.65rem' }}
            onClick={() => setOverviewFilter('pending')}
          >
            Pending Dispatch ({pendingIncidents.length})
          </button>
          <button
            type="button"
            className={`btn btn-sm ${overviewFilter === 'assigned' ? 'btn-cyan font-bold' : 'btn-secondary'}`}
            style={{ fontSize: '0.72rem', padding: '0.25rem 0.65rem' }}
            onClick={() => setOverviewFilter('assigned')}
          >
            Assigned Missions ({activeMissions.length})
          </button>
          <button
            type="button"
            className={`btn btn-sm ${overviewFilter === 'active' ? 'btn-cyan font-bold' : 'btn-secondary'}`}
            style={{ fontSize: '0.72rem', padding: '0.25rem 0.65rem' }}
            onClick={() => setOverviewFilter('active')}
          >
            Active Missions ({inProgressMissions.length})
          </button>
          <button
            type="button"
            className={`btn btn-sm ${overviewFilter === 'resolved' ? 'btn-cyan font-bold' : 'btn-secondary'}`}
            style={{ fontSize: '0.72rem', padding: '0.25rem 0.65rem' }}
            onClick={() => setOverviewFilter('resolved')}
          >
            Resolved ({resolvedIncidents.length})
          </button>
        </div>

        {/* Scrollable Incident Cards Strip / Grid */}
        {filteredOverviewIncidents.length === 0 ? (
          <div className="p-6 text-center text-xs text-muted font-medium">
            No incident reports found matching filter "{overviewFilter}".
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))',
            gap: '0.65rem',
            maxHeight: '260px',
            overflowY: 'auto',
            paddingRight: '4px'
          }}>
            {filteredOverviewIncidents.map((inc) => {
              const isSelected = activeIncident?.id === inc.id;
              const isAssigned = Boolean(inc.assigned_resource_id);
              const urgency = inc.dispatcher_urgency_override || inc.urgency || 'Medium';

              return (
                <div
                  key={inc.id}
                  onClick={() => {
                    setInspectedIncidentId(inc.id);
                    if (inc.assigned_resource_id) {
                      setSelectedResourceId(inc.assigned_resource_id);
                      if (onSelectTeamId) onSelectTeamId(inc.assigned_resource_id);
                    }
                  }}
                  style={{
                    backgroundColor: isSelected ? '#f0f9ff' : '#ffffff',
                    border: isSelected ? '2px solid #0284c7' : '1px solid #e2e8f0',
                    borderRadius: '6px',
                    padding: '0.65rem 0.85rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    boxShadow: isSelected ? '0 0 0 1px #0284c7, var(--shadow-sm)' : 'var(--shadow-sm)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.4rem',
                    position: 'relative'
                  }}
                >
                  {/* Top line: ID, Type, Priority & Status */}
                  <div className="flex items-center justify-between gap-1 flex-wrap">
                    <div className="flex items-center gap-1.5 font-bold text-xs">
                      {getIncidentIcon(inc.incident_type)}
                      <span className="mono text-cyan">Signal #{inc.id}</span>
                      <span className="text-main font-semibold truncate">
                        {inc.incident_type}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className={`badge badge-${urgency.toLowerCase()}`} style={{ fontSize: '0.62rem', padding: '0.1rem 0.4rem' }}>
                        {urgency}
                      </span>
                      <span className={`badge-status ${inc.status}`} style={{ fontSize: '0.62rem', padding: '0.1rem 0.4rem' }}>
                        {inc.status}
                      </span>
                    </div>
                  </div>

                  {/* Distinction Tag: Approved Mission vs Pending Dispatch */}
                  <div className="flex items-center justify-between text-xs">
                    {isAssigned ? (
                      <span className="badge" style={{ backgroundColor: '#f0f9ff', color: '#0369a1', border: '1px solid #bae6fd', fontSize: '0.62rem' }}>
                        ✓ APPROVED MISSION &bull; Unit: {inc.assigned_resource?.contact_callsign || `Team #${inc.assigned_resource_id}`}
                      </span>
                    ) : (
                      <span className="badge" style={{ backgroundColor: '#fffbeb', color: '#b45309', border: '1px solid #fcd34d', fontSize: '0.62rem' }}>
                        ⏳ PENDING DISPATCH
                      </span>
                    )}
                    <span className="text-muted mono font-semibold" style={{ fontSize: '0.62rem' }}>
                      {new Date(inc.reported_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>

                  {/* Location & GPS */}
                  <div className="text-xs text-secondary truncate flex items-center gap-1 font-medium" title={inc.location}>
                    <MapPin size={11} className={inc.latitude && inc.longitude ? 'text-cyan shrink-0' : 'text-amber-600 shrink-0'} />
                    <span className="truncate">{inc.location}</span>
                  </div>

                  {inc.latitude && inc.longitude ? (
                    <div className="text-cyan mono font-semibold" style={{ fontSize: '0.62rem' }}>
                      📍 GPS: [{inc.latitude.toFixed(4)}, {inc.longitude.toFixed(4)}]
                    </div>
                  ) : (
                    <div className="text-amber-700 mono font-medium" style={{ fontSize: '0.62rem' }}>
                      ⚠️ GPS Unplotted (Manual Address Only)
                    </div>
                  )}

                  {/* Description Snippet */}
                  <p className="text-secondary text-xs line-clamp-2" style={{ fontSize: '0.68rem', lineHeight: 1.35, margin: 0 }}>
                    {inc.description}
                  </p>

                  {/* Footer: People affected & selection indicator */}
                  <div className="flex items-center justify-between text-muted pt-1 mt-auto" style={{ borderTop: '1px solid #e2e8f0', fontSize: '0.65rem' }}>
                    <span className="flex items-center gap-1 font-medium text-secondary">
                      <Users size={11} className="text-cyan" />
                      <span>{inc.people_affected} affected</span>
                    </span>
                    {isSelected ? (
                      <span className="text-cyan font-bold flex items-center gap-0.5">
                        <span>INSPECTING</span> &bull;
                      </span>
                    ) : (
                      <span className="text-muted font-medium">Click to inspect</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 3. TEAM SELECTOR & TELEMETRY BAR */}
      <div className="panel" style={{ padding: '0.85rem 1.25rem', backgroundColor: '#ffffff', border: '1px solid var(--border-subtle)', boxShadow: 'var(--shadow-panel)' }}>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center shrink-0" style={{
              width: '38px', 
              height: '38px', 
              backgroundColor: '#0284c7', 
              borderRadius: '6px',
              boxShadow: '0 2px 6px rgba(2, 132, 199, 0.25)'
            }}>
              <Truck size={22} color="#ffffff" />
            </div>
            <div>
              <div className="text-2xs text-muted font-bold uppercase tracking-wider">Selected Rescue Team Terminal (MDT)</div>
              <div className="flex items-center gap-2 mt-0.5">
                <select
                  className="select font-bold text-xs"
                  style={{ width: 'auto', minWidth: '310px', backgroundColor: '#ffffff', borderColor: '#cbd5e1', color: '#0f172a' }}
                  value={selectedResourceId || ''}
                  onChange={(e) => {
                    const newId = Number(e.target.value);
                    setSelectedResourceId(newId);
                    if (onSelectTeamId) onSelectTeamId(newId);
                  }}
                >
                  {resources.map((r) => (
                    <option key={r.id} value={r.id}>
                      [{r.contact_callsign}] {r.name} — {r.availability} {r.current_incident_id ? `(Signal #${r.current_incident_id})` : ''}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ fontSize: '0.72rem' }}
                  onClick={() => {
                    fetchMission(selectedResourceId);
                    fetchAllIncidents();
                  }}
                  title="Refresh mission telemetry"
                >
                  Sync
                </button>
              </div>
            </div>
          </div>

          {/* Selected Team Profile Pills */}
          {selectedTeam && (
            <div className="flex items-center gap-2 flex-wrap text-xs text-secondary font-medium">
              <span className="badge badge-rule">Callsign: {selectedTeam.contact_callsign}</span>
              <span className={`badge-status ${selectedTeam.availability === 'Available' ? 'Resolved' : selectedTeam.availability === 'On Scene' ? 'Verified' : 'Assigned'}`}>
                {selectedTeam.availability}
              </span>
              <span>📍 {selectedTeam.simulated_location_name}</span>
              <span>👥 Crew: {selectedTeam.capacity}</span>
            </div>
          )}
        </div>
      </div>

      {/* 4. MAIN WORKSPACE: AI INCIDENT ANALYSIS & MISSION TERMINAL + TACTICAL MAP */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(420px, 1.2fr) minmax(380px, 0.8fr)', gap: '0.85rem' }}>
        
        {/* Left Column: AI-Assisted Incident Analysis Panel & Field MDT Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          
          {/* AI-ASSISTED INCIDENT ANALYSIS PANEL (FOR INSPECTED INCIDENT) */}
          {activeIncident ? (
            <div className="card" style={{ borderLeft: `5px solid ${activeEffectiveUrgency === 'Critical' ? '#dc2626' : activeEffectiveUrgency === 'High' ? '#ea580c' : '#d97706'}` }}>
              {/* Header */}
              <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
                <div className="flex items-center gap-2">
                  {activeIncident.assessment_method === 'ai_generated' ? (
                    <div className="flex items-center gap-1.5 text-xs font-bold text-cyan">
                      <Bot size={16} />
                      <span>AI INCIDENT ANALYSIS</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5 text-xs font-bold text-cyan">
                      <Cpu size={16} />
                      <span>RULE-BASED INCIDENT ANALYSIS</span>
                    </div>
                  )}
                  <span className="text-muted text-xs">&bull; Signal #{activeIncident.id}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`badge badge-${activeEffectiveUrgency.toLowerCase()} text-xs`}>
                    {activeEffectiveUrgency} PRIORITY
                  </span>
                  <span className={`badge-status ${activeIncident.status} text-xs font-bold`}>
                    {activeIncident.status}
                  </span>
                </div>
              </div>

              {/* Title & Reason for Recommendation */}
              <h3 className="text-base font-bold text-main mb-1">
                {activeIncident.incident_type} &bull; {activeIncident.location}
              </h3>
              
              <div style={{ backgroundColor: '#f8fafc', padding: '0.65rem 0.85rem', borderRadius: '6px', border: '1px solid #e2e8f0', marginBottom: '0.65rem' }}>
                <div className="text-2xs text-muted font-bold uppercase tracking-wider mb-1">Triage Priority Assessment &amp; Reason</div>
                <p className="text-xs text-main font-medium" style={{ lineHeight: 1.45, margin: 0 }}>
                  {activeIncident.urgency_explanation || 'Assessed through deterministic hazard and risk heuristic engine.'}
                </p>
                <div className="flex items-center justify-between mt-1.5 pt-1.5" style={{ borderTop: '1px solid #e2e8f0', fontSize: '0.68rem' }}>
                  <span className="text-cyan font-mono font-bold">
                    Scene Uncertainty: {Math.round((activeIncident.uncertainty_score || 0.15) * 100)}%
                  </span>
                  <span className="text-muted truncate max-w-xs font-medium" title={activeIncident.uncertainty_note}>
                    {activeIncident.uncertainty_note || 'High confidence assessment'}
                  </span>
                </div>
              </div>

              {/* Description & Casualties */}
              <div style={{ marginBottom: '0.65rem' }}>
                <div className="text-2xs text-muted font-bold uppercase tracking-wider mb-0.5">Reported Situation</div>
                <p className="text-xs text-secondary font-medium" style={{ lineHeight: 1.45, margin: 0 }}>
                  {activeIncident.description}
                </p>
                <div className="flex items-center gap-2 mt-1.5 text-xs text-muted">
                  <Users size={13} className="text-cyan" />
                  <span className="font-semibold text-main">{activeIncident.people_affected} affected or trapped individuals</span>
                </div>
              </div>

              {/* Hazards and Operational Skills */}
              <div className="grid grid-cols-2 gap-2 mb-2 pt-2" style={{ borderTop: '1px solid #e2e8f0' }}>
                <div>
                  <div className="text-2xs text-muted uppercase font-bold tracking-wider mb-1">Reported Hazards / Risks</div>
                  <div className="flex flex-wrap gap-1">
                    {activeIncident.key_risks && activeIncident.key_risks.length > 0 ? (
                      activeIncident.key_risks.map((k, i) => (
                        <span key={i} className="badge badge-high" style={{ fontSize: '0.62rem', padding: '0.1rem 0.4rem' }}>{k}</span>
                      ))
                    ) : (
                      <span className="text-xs text-muted font-medium">Standard incident risks</span>
                    )}
                  </div>
                </div>

                <div>
                  <div className="text-2xs text-muted uppercase font-bold tracking-wider mb-1">Required Operational Capabilities</div>
                  <div className="flex flex-wrap gap-1">
                    {activeIncident.recommended_capabilities && activeIncident.recommended_capabilities.length > 0 ? (
                      activeIncident.recommended_capabilities.map((c, i) => (
                        <span key={i} className="badge badge-rule" style={{ fontSize: '0.62rem', padding: '0.1rem 0.4rem' }}>✓ {c}</span>
                      ))
                    ) : (
                      <span className="text-xs text-muted font-medium">General response</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Recommended Next Action */}
              <div style={{ backgroundColor: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: '6px', padding: '0.6rem 0.85rem', marginBottom: '0.65rem' }}>
                <div className="text-xs font-bold text-cyan uppercase mb-1 flex items-center gap-1">
                  <Navigation size={13} />
                  <span>Recommended Next Action</span>
                </div>
                <p className="text-xs text-secondary font-medium" style={{ lineHeight: 1.45, margin: 0 }}>
                  {activeIncident.recommended_next_action || 'Review incident requirements and deploy primary suitable rescue unit.'}
                </p>
              </div>

              {/* Missing Information To Verify */}
              {activeIncident.missing_information && activeIncident.missing_information.length > 0 && (
                <div style={{ backgroundColor: '#fffbeb', border: '1px solid #fcd34d', borderRadius: '6px', padding: '0.6rem 0.85rem', marginBottom: '0.65rem' }}>
                  <div className="text-xs font-bold text-amber-700 uppercase mb-1 flex items-center gap-1">
                    <HelpCircle size={13} />
                    <span>Missing Information for Dispatcher Verification</span>
                  </div>
                  <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.7rem', color: '#92400e', lineHeight: 1.4 }}>
                    {activeIncident.missing_information.map((infoItem, idx) => (
                      <li key={idx}>{infoItem}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Suggested Resource Recommendations Preview */}
              {recommendations && recommendations.recommendations && (
                <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: '0.65rem' }}>
                  <div className="flex items-center justify-between text-xs text-muted font-semibold uppercase mb-1.5">
                    <span className="flex items-center gap-1 text-cyan font-bold">
                      <Truck size={13} />
                      <span>Recommended Response Resources ({recommendations.recommendations.length} Evaluated)</span>
                    </span>
                    {!activeIncident.assigned_resource_id && onSwitchToDispatcher && (
                      <button
                        type="button"
                        className="btn btn-sm btn-cyan font-bold"
                        style={{ fontSize: '0.68rem', padding: '0.2rem 0.55rem' }}
                        onClick={() => onSwitchToDispatcher(activeIncident)}
                      >
                        Approve in Dispatcher Console &rarr;
                      </button>
                    )}
                  </div>
                  <div className="flex flex-col gap-1">
                    {recommendations.recommendations.slice(0, 2).map((rec) => (
                      <div
                        key={rec.resource.id}
                        style={{
                          backgroundColor: '#ffffff',
                          padding: '0.5rem 0.75rem',
                          borderRadius: '6px',
                          border: '1px solid #e2e8f0',
                          fontSize: '0.7rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          boxShadow: 'var(--shadow-sm)'
                        }}
                      >
                        <div>
                          <strong className="text-main">[{rec.resource.contact_callsign}] {rec.resource.name}</strong>
                          <span className="text-muted ml-1.5 font-medium">({rec.priority_level})</span>
                          <div className="text-secondary text-xs truncate max-w-md font-medium">{rec.recommendation_reason}</div>
                        </div>
                        <span className="badge badge-rule font-mono font-bold">{rec.match_score}% Match</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="panel p-6 text-center text-xs text-muted font-medium" style={{ backgroundColor: '#ffffff' }}>
              Select an incident from the overview above to view its AI/Rule-based triage analysis.
            </div>
          )}

          {/* FIELD RESPONDER TERMINAL (MDT) CONTROLS FOR SELECTED TEAM */}
          {hasActiveTeamMission ? (
            <div className="card">
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="flex items-center gap-1.5 text-xs text-main font-bold uppercase">
                  <Radio size={14} className="text-cyan" />
                  <span>Field Team MDT Mission Order &bull; Signal #{teamMissionIncident.id}</span>
                </span>
                <span className={`badge-status ${teamMissionIncident.status} text-xs font-bold`}>
                  {teamMissionIncident.status}
                </span>
              </div>

              {/* Exact Reported Address Box */}
              <div style={{ backgroundColor: '#f8fafc', padding: '0.75rem', borderRadius: '6px', border: '1px solid #e2e8f0', marginBottom: '0.75rem' }}>
                <div className="text-2xs text-muted font-bold uppercase tracking-wider mb-0.5 flex items-center gap-1">
                  <MapPin size={12} className="text-cyan" />
                  <span>Exact Scene Ingress Address</span>
                </div>
                <div className="text-xs font-bold text-main">{teamMissionIncident.location}</div>
                {teamMissionIncident.latitude && teamMissionIncident.longitude ? (
                  <div className="text-xs mono text-cyan mt-0.5 font-semibold">
                    GPS Coordinates: [{teamMissionIncident.latitude.toFixed(5)}, {teamMissionIncident.longitude.toFixed(5)}]
                  </div>
                ) : (
                  <div className="text-xs text-amber-700 mt-0.5 font-medium">Exact GPS unplotted (Manual street address)</div>
                )}
              </div>

              {/* Turn-by-Turn GPS Navigation Link */}
              {missionData?.navigation_url && (
                <div style={{ marginBottom: '0.75rem' }}>
                  <a
                    href={missionData.navigation_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-cyan font-bold"
                    style={{ width: '100%', padding: '0.55rem', fontSize: '0.8rem', textDecoration: 'none' }}
                  >
                    <Navigation size={15} />
                    <span>Open Turn-by-Turn GPS Navigation</span>
                    <ExternalLink size={13} style={{ marginLeft: 'auto' }} />
                  </a>
                </div>
              )}

              {/* Field Team Lifecycle Status Transmission */}
              <div className="text-2xs text-muted uppercase font-bold tracking-wider mb-1.5">
                Field Team Lifecycle Transmission
              </div>
              <div className="grid grid-cols-3 gap-2 mb-2.5">
                {(() => {
                  const isAccepted = teamMissionIncident.status === 'Accepted';
                  const isPastAccepted = ['En Route', 'Arrived', 'Resolved'].includes(teamMissionIncident.status);
                  const isEnRoute = teamMissionIncident.status === 'En Route';
                  const isPastEnRoute = ['Arrived', 'Resolved'].includes(teamMissionIncident.status);
                  const isArrived = teamMissionIncident.status === 'Arrived';
                  const isResolved = teamMissionIncident.status === 'Resolved';

                  return (
                    <>
                      <button
                        type="button"
                        className={`btn ${
                          isAccepted
                            ? 'btn-primary'
                            : isPastAccepted
                            ? 'btn-secondary text-low font-bold'
                            : teamMissionIncident.status === 'Assigned'
                            ? 'btn-cyan font-bold'
                            : 'btn-secondary'
                        }`}
                        style={{ fontSize: '0.72rem', padding: '0.45rem' }}
                        disabled={updatingStatus || isAccepted}
                        onClick={() => handleStatusUpdate('Accepted')}
                        title="Acknowledge dispatch order and accept assignment"
                      >
                        {isPastAccepted ? <Check size={13} className="text-low" /> : <Check size={13} />}
                        <span>{isPastAccepted ? '✓ Accepted' : isAccepted ? '● Accepted' : '1. Accept Order'}</span>
                      </button>

                      <button
                        type="button"
                        className={`btn ${
                          isEnRoute
                            ? 'btn-primary'
                            : isPastEnRoute
                            ? 'btn-secondary text-low font-bold'
                            : isAccepted
                            ? 'btn-cyan font-bold'
                            : 'btn-secondary'
                        }`}
                        style={{ fontSize: '0.72rem', padding: '0.45rem' }}
                        disabled={updatingStatus || isEnRoute}
                        onClick={() => handleStatusUpdate('En Route')}
                        title="Mobilize response unit with sirens/navigation active"
                      >
                        {isPastEnRoute ? <Check size={13} className="text-low" /> : <Navigation size={13} />}
                        <span>{isPastEnRoute ? '✓ En Route' : isEnRoute ? '● En Route' : '2. En Route'}</span>
                      </button>

                      <button
                        type="button"
                        className={`btn ${
                          isArrived
                            ? 'btn-primary'
                            : isResolved
                            ? 'btn-secondary text-low font-bold'
                            : isEnRoute
                            ? 'btn-cyan font-bold'
                            : 'btn-secondary'
                        }`}
                        style={{ fontSize: '0.72rem', padding: '0.45rem' }}
                        disabled={updatingStatus || isArrived}
                        onClick={() => handleStatusUpdate('Arrived')}
                        title="Report arrival on scene and initiation of rescue operations"
                      >
                        {isResolved ? <Check size={14} className="text-low" /> : <MapPin size={13} />}
                        <span>{isResolved ? '✓ Arrived' : isArrived ? '● On Scene' : '3. Arrived'}</span>
                      </button>
                    </>
                  );
                })()}
              </div>

              {/* Field Note / SitRep Input */}
              <div style={{ marginBottom: '0.65rem' }}>
                <label className="label text-xs">Field Team Remarks / Situation Report</label>
                <input
                  type="text"
                  className="input text-xs"
                  placeholder="e.g. Ingress via South road accessible. Setting up triage zone..."
                  value={fieldNote}
                  onChange={(e) => setFieldNote(e.target.value)}
                  disabled={updatingStatus}
                />
              </div>

              {/* Conclude Mission Button */}
              <div className="flex justify-end pt-2" style={{ borderTop: '1px solid #e2e8f0' }}>
                <button
                  type="button"
                  className="btn btn-success btn-sm"
                  disabled={updatingStatus}
                  onClick={() => {
                    if (window.confirm('Confirm all rescue operations are completed and return unit to Available standby?')) {
                      handleStatusUpdate('Resolved');
                    }
                  }}
                  title="Conclude mission and return unit to Available standby status"
                >
                  <CheckCircle size={14} />
                  <span>Complete Mission &amp; Return to Standby</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="panel p-5 text-center" style={{ backgroundColor: '#ffffff', border: '1px solid var(--border-subtle)' }}>
              <div className="flex items-center justify-center mx-auto mb-2" style={{
                width: '42px', 
                height: '42px', 
                backgroundColor: '#f0f9ff', 
                border: '1px solid #bae6fd', 
                borderRadius: '50%'
              }}>
                <CheckCircle size={22} className="text-cyan" />
              </div>
              <h4 className="text-xs font-bold text-main mb-1">
                Unit Standby: {selectedTeam?.name} ({selectedTeam?.contact_callsign})
              </h4>
              <p className="text-xs text-secondary mb-2 font-medium" style={{ fontSize: '0.72rem' }}>
                This rescue unit is currently Available at <strong>{selectedTeam?.simulated_location_name}</strong>. No emergency assignment has been dispatched to this unit yet.
              </p>
              {pendingIncidents.length > 0 && onSwitchToDispatcher && (
                <button
                  type="button"
                  className="btn btn-cyan btn-sm"
                  style={{ fontSize: '0.72rem', padding: '0.25rem 0.65rem' }}
                  onClick={() => onSwitchToDispatcher(pendingIncidents[0])}
                >
                  <span>Review {pendingIncidents.length} Pending Signal(s) in Dispatcher Console &rarr;</span>
                </button>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Tactical Destination Map & Mission Audit Logs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          
          {/* Tactical Geospatial Map */}
          <div className="panel" style={{ height: '380px', display: 'flex', flexDirection: 'column', position: 'relative' }}>
            <div className="flex items-center justify-between" style={{ padding: '0.5rem 0.85rem', backgroundColor: '#ffffff', borderBottom: '1px solid var(--border-subtle)', zIndex: 10 }}>
              <span className="text-xs font-bold text-main flex items-center gap-1.5">
                <Compass size={14} className="text-cyan" />
                <span>Tactical Destination Grid</span>
              </span>
              <span className="badge badge-rule text-xs font-semibold">
                {activeIncident?.latitude && activeIncident?.longitude ? 'GPS Lock' : 'Address-Only'}
              </span>
            </div>

            <div style={{ flex: 1, position: 'relative' }}>
              <MapContainer
                center={
                  activeIncident?.latitude && activeIncident?.longitude 
                    ? [activeIncident.latitude, activeIncident.longitude] 
                    : [37.7749, -122.4194]
                }
                zoom={13}
                scrollWheelZoom={true}
                style={{ height: '100%', width: '100%' }}
              >
                <TileLayer
                  attribution='&copy; OpenStreetMap'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                {/* Inspected Incident Marker */}
                {activeIncident?.latitude !== null && activeIncident?.latitude !== undefined && 
                 activeIncident?.longitude !== null && activeIncident?.longitude !== undefined && (
                  <>
                    <MissionMapFocus lat={activeIncident.latitude} lng={activeIncident.longitude} />
                    <Marker
                      position={[activeIncident.latitude, activeIncident.longitude]}
                      icon={createIncidentPin(activeEffectiveUrgency)}
                    >
                      <Popup>
                        <div style={{ minWidth: '160px', padding: '2px' }}>
                          <strong className="text-sm font-bold text-main">{activeIncident.incident_type} Scene</strong>
                          <p className="text-xs text-secondary mt-1 font-medium">{activeIncident.location}</p>
                          <p className="text-xs mono text-cyan mt-1 font-semibold">[{activeIncident.latitude.toFixed(4)}, {activeIncident.longitude.toFixed(4)}]</p>
                          <p className="text-xs mt-1 font-medium">Status: <strong className="text-main">{activeIncident.status}</strong></p>
                        </div>
                      </Popup>
                    </Marker>
                  </>
                )}

                {/* Team Base / Vehicle Location */}
                {selectedTeam?.simulated_lat && selectedTeam?.simulated_lng && (
                  <Marker
                    position={[selectedTeam.simulated_lat, selectedTeam.simulated_lng]}
                    icon={createTeamPin(selectedTeam.availability !== 'Available')}
                  >
                    <Popup>
                      <div style={{ minWidth: '140px', padding: '2px' }}>
                        <strong className="text-main">{selectedTeam.name}</strong>
                        <p className="text-xs text-secondary mt-1 font-medium">📍 {selectedTeam.simulated_location_name}</p>
                        <p className="text-xs mt-1 font-medium">Callsign: <strong className="text-cyan">{selectedTeam.contact_callsign}</strong></p>
                      </div>
                    </Popup>
                  </Marker>
                )}
              </MapContainer>
            </div>
          </div>

          {/* Action Log / Mission Audit Trail */}
          <div className="card" style={{ flex: 1, minHeight: '200px', maxHeight: '320px', overflowY: 'auto' }}>
            <div className="text-xs text-muted uppercase font-bold mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-main font-bold">
                <Clock size={14} className="text-cyan" />
                <span>Mission Audit Log &amp; SitReps</span>
              </span>
              <span className="mono text-xs text-cyan font-bold">
                {activeIncident?.action_logs ? `${activeIncident.action_logs.length} entries` : 'Live'}
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
              {activeIncident?.action_logs && activeIncident.action_logs.length > 0 ? (
                activeIncident.action_logs.map((log) => (
                  <div
                    key={log.id}
                    style={{
                      padding: '0.5rem 0.75rem',
                      backgroundColor: '#ffffff',
                      borderRadius: '6px',
                      border: '1px solid #e2e8f0',
                      borderLeft: '3px solid #0284c7',
                      fontSize: '0.72rem',
                      boxShadow: 'var(--shadow-sm)'
                    }}
                  >
                    <div className="flex items-center justify-between text-muted mb-0.5">
                      <span className="font-bold text-main">{log.actor} &bull; {log.action_type}</span>
                      <span className="mono text-2xs text-secondary font-semibold">{new Date(log.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <div className="text-secondary font-medium">{log.details}</div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-muted font-medium">No transmission logs recorded yet.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
