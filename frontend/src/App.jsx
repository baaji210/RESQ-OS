import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import IncidentModal from './components/IncidentModal';
import CommandMap from './components/CommandMap';
import IncidentQueue from './components/IncidentQueue';
import IncidentDetail from './components/IncidentDetail';
import ResourceFleet from './components/ResourceFleet';
import RescueTeamView from './components/RescueTeamView';
import { api } from './services/api';
import { Map, List, Truck, ShieldAlert, AlertCircle, Radio } from 'lucide-react';

export default function App() {
  const [allIncidents, setAllIncidents] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [resources, setResources] = useState([]);
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);

  const [selectedIncident, setSelectedIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [urgencyFilter, setUrgencyFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('All');

  // Modals & View Modes
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isFleetOpen, setIsFleetOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('split'); // 'split', 'map', 'detail'
  const [viewMode, setViewMode] = useState('dispatcher'); // 'dispatcher' | 'rescue-team'
  const [selectedTeamId, setSelectedTeamId] = useState(null);

  // Fetch all dashboard data
  const fetchData = useCallback(async (keepSelectedId = null) => {
    setLoading(true);
    setError(null);
    try {
      const [healthData, statsData, allIncData, resourcesData] = await Promise.all([
        api.getHealth().catch((err) => ({ status: 'offline', error: err.message })),
        api.getDashboardStats().catch(() => null),
        api.getIncidents(), // Always retrieve all incidents as single source of truth
        api.getResources(),
      ]);

      setHealth(healthData);
      setStats(statsData);
      setAllIncidents(allIncData);
      setResources(resourcesData);

      // Filtered incidents for Dispatcher Queue view
      let filtered = allIncData;
      if (statusFilter && statusFilter !== 'All') {
        filtered = filtered.filter((i) => i.status === statusFilter);
      }
      if (urgencyFilter && urgencyFilter !== 'All') {
        filtered = filtered.filter((i) => (i.dispatcher_urgency_override || i.urgency) === urgencyFilter);
      }
      if (searchQuery && searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        filtered = filtered.filter(
          (i) =>
            (i.location && i.location.toLowerCase().includes(q)) ||
            (i.description && i.description.toLowerCase().includes(q)) ||
            (i.incident_type && i.incident_type.toLowerCase().includes(q))
        );
      }
      setIncidents(filtered);

      // Keep selected incident or auto-select the highest priority active one
      if (keepSelectedId) {
        const found = allIncData.find((i) => i.id === keepSelectedId);
        if (found) setSelectedIncident(found);
      } else if (!selectedIncident && allIncData.length > 0) {
        // Find first Critical or High
        const topUrgent = allIncData.find((i) => ['Critical', 'High'].includes(i.effective_urgency || i.urgency)) || allIncData[0];
        setSelectedIncident(topUrgent);
      } else if (selectedIncident) {
        // Refresh currently selected incident object
        const refreshed = allIncData.find((i) => i.id === selectedIncident.id);
        if (refreshed) setSelectedIncident(refreshed);
      }
    } catch (err) {
      console.error('Data fetch error:', err);
      setError(err.message || 'Unable to connect to RESQ-OS backend services');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, urgencyFilter, searchQuery, selectedIncident]);

  useEffect(() => {
    fetchData();
  }, [statusFilter, urgencyFilter, searchQuery]);

  // Periodic telemetry poll every 7 seconds for live sync
  useEffect(() => {
    const timer = setInterval(() => {
      fetchData(selectedIncident?.id);
    }, 7000);
    return () => clearInterval(timer);
  }, [fetchData, selectedIncident?.id]);

  // Synchronize telemetry whenever switching between Dispatcher Console and Rescue Team MDT
  useEffect(() => {
    fetchData(selectedIncident?.id);
  }, [viewMode]);

  const handleSelectIncident = (inc) => {
    setSelectedIncident(inc);
  };

  const handleSelectIncidentById = (id) => {
    const inc = incidents.find((i) => i.id === id);
    if (inc) {
      setSelectedIncident(inc);
    } else {
      api.getIncidentById(id).then((data) => setSelectedIncident(data)).catch(() => {});
    }
  };

  const handleIncidentCreated = (newIncident) => {
    fetchData(newIncident.id);
  };

  const handleIncidentUpdated = (updatedIncident) => {
    setSelectedIncident(updatedIncident);
    setAllIncidents((prev) =>
      prev.map((i) => (i.id === updatedIncident.id ? updatedIncident : i))
    );
    setIncidents((prev) =>
      prev.map((i) => (i.id === updatedIncident.id ? updatedIncident : i))
    );
    if (updatedIncident.assigned_resource_id) {
      setSelectedTeamId(updatedIncident.assigned_resource_id);
    }
    // Refresh stats and resources immediately
    api.getDashboardStats().then(setStats).catch(() => {});
    api.getResources().then(setResources).catch(() => {});
  };

  const handleResetDemo = async () => {
    if (!window.confirm('Reset emergency coordination scenario to default fictional demo data?')) return;
    try {
      setLoading(true);
      await api.resetDemoData();
      await fetchData();
    } catch (err) {
      alert(`Reset error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Top Header & Metrics */}
      <Header
        stats={stats}
        health={health}
        loading={loading}
        onOpenNewIncident={() => setIsModalOpen(true)}
        onResetDemo={handleResetDemo}
        onRefresh={() => fetchData(selectedIncident?.id)}
      />

      {/* Primary Sub-Command Banner with View Mode Switcher */}
      <div className="command-banner">
        {/* Left: View Mode Toggle */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1 p-0.5 rounded-md" style={{ backgroundColor: '#ffffff', border: '1px solid #cbd5e1', boxShadow: '0 1px 2px rgba(0,0,0,0.03)' }}>
            <button
              type="button"
              className={`btn btn-sm ${viewMode === 'dispatcher' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ 
                fontSize: '0.75rem', 
                padding: '0.25rem 0.75rem',
                border: viewMode === 'dispatcher' ? '1px solid #dc2626' : '1px solid transparent'
              }}
              onClick={() => setViewMode('dispatcher')}
            >
              <ShieldAlert size={14} />
              <span>Dispatcher Console</span>
            </button>
            <button
              type="button"
              className={`btn btn-sm ${viewMode === 'rescue-team' ? 'btn-cyan' : 'btn-secondary'}`}
              style={{ 
                fontSize: '0.75rem', 
                padding: '0.25rem 0.75rem',
                border: viewMode === 'rescue-team' ? '1px solid #0284c7' : '1px solid transparent'
              }}
              onClick={() => {
                if (selectedIncident?.assigned_resource_id) {
                  setSelectedTeamId(selectedIncident.assigned_resource_id);
                }
                setViewMode('rescue-team');
              }}
            >
              <Truck size={14} />
              <span>Rescue Team View (MDT)</span>
              {resources.some((r) => r.current_incident_id) && (
                <span className="pulse-indicator" style={{ width: '6px', height: '6px', marginLeft: '2px' }}></span>
              )}
            </button>
          </div>

          <span className="text-muted hidden md:inline">|</span>
          <span className="text-secondary text-xs font-medium hidden md:inline">
            {viewMode === 'dispatcher' 
              ? 'PROTOCOL: AI-ASSISTED TRIAGE & DISPATCH' 
              : 'PROTOCOL: FIELD RESPONDER MOBILE DATA TERMINAL'}
          </span>
        </div>

        {/* Right: Contextual Controls */}
        <div className="flex items-center gap-2">
          {viewMode === 'dispatcher' ? (
            <>
              {/* View Toggles for Dispatcher */}
              <div className="flex items-center gap-1 p-0.5 rounded-md" style={{ backgroundColor: '#ffffff', border: '1px solid #cbd5e1', boxShadow: '0 1px 2px rgba(0,0,0,0.03)' }}>
                <button
                  type="button"
                  className={`btn btn-sm ${activeTab === 'split' ? 'btn-cyan' : 'btn-secondary'}`}
                  style={{ 
                    fontSize: '0.7rem', 
                    padding: '0.2rem 0.55rem',
                    border: activeTab === 'split' ? '1px solid #0284c7' : '1px solid transparent'
                  }}
                  onClick={() => setActiveTab('split')}
                  title="Split View: Map & Dispatcher"
                >
                  Split View
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${activeTab === 'map' ? 'btn-cyan' : 'btn-secondary'}`}
                  style={{ 
                    fontSize: '0.7rem', 
                    padding: '0.2rem 0.55rem',
                    border: activeTab === 'map' ? '1px solid #0284c7' : '1px solid transparent'
                  }}
                  onClick={() => setActiveTab('map')}
                  title="Full Map View"
                >
                  <Map size={12} /> Map Only
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${activeTab === 'detail' ? 'btn-cyan' : 'btn-secondary'}`}
                  style={{ 
                    fontSize: '0.7rem', 
                    padding: '0.2rem 0.55rem',
                    border: activeTab === 'detail' ? '1px solid #0284c7' : '1px solid transparent'
                  }}
                  onClick={() => setActiveTab('detail')}
                  title="Full Dispatcher Detail"
                >
                  <List size={12} /> Dispatcher Only
                </button>
              </div>

              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.72rem', padding: '0.25rem 0.65rem' }}
                onClick={() => setIsFleetOpen(true)}
              >
                <Truck size={14} className="text-cyan" />
                <span>Fleet Assets ({resources.length})</span>
              </button>
            </>
          ) : (
            <div className="flex items-center gap-2 text-xs text-secondary font-medium">
              <span className="badge badge-rule">
                Simulated Teams: {resources.length}
              </span>
              <span className="badge badge-sim">
                Real-world Dispatch Unconnected
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div style={{ backgroundColor: '#fef2f2', borderBottom: '1px solid #fca5a5', padding: '0.6rem 1.5rem' }}>
          <div className="flex items-center gap-2 text-critical text-xs font-semibold">
            <AlertCircle size={16} />
            <span>Connection Error: {error}. Check backend server on port 8000.</span>
          </div>
        </div>
      )}

      {/* Main Workspace Layout */}
      {viewMode === 'dispatcher' ? (
        <main style={{
          flex: 1,
          padding: '0.85rem',
          display: 'grid',
          gridTemplateColumns: '360px minmax(0, 1fr)',
          gap: '0.85rem',
          overflow: 'hidden',
          height: 'calc(100vh - 150px)',
        }}>
          {/* Left: Signal Intake & Triage Queue */}
          <section style={{ height: '100%', overflow: 'hidden' }}>
            <IncidentQueue
              incidents={incidents}
              selectedIncident={selectedIncident}
              onSelectIncident={handleSelectIncident}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              urgencyFilter={urgencyFilter}
              onUrgencyFilterChange={setUrgencyFilter}
              statusFilter={statusFilter}
              onStatusFilterChange={setStatusFilter}
              loading={loading}
            />
          </section>

          {/* Right: Geospatial Grid & Dispatcher Workbench */}
          <section style={{
            height: '100%',
            overflow: 'hidden',
            display: 'grid',
            gridTemplateRows: activeTab === 'split' ? '44% 56%' : '1fr',
            gap: '0.85rem',
          }}>
            {/* Geospatial Map */}
            {(activeTab === 'split' || activeTab === 'map') && (
              <div style={{ height: '100%', minHeight: '0' }}>
                <CommandMap
                  incidents={allIncidents.length > 0 ? allIncidents : incidents}
                  resources={resources}
                  selectedIncident={selectedIncident}
                  onSelectIncident={handleSelectIncident}
                />
              </div>
            )}

            {/* Dispatcher Incident Detail Workbench */}
            {(activeTab === 'split' || activeTab === 'detail') && (
              <div style={{ height: '100%', minHeight: '0', overflow: 'hidden' }}>
                <IncidentDetail
                  incident={selectedIncident}
                  onIncidentUpdated={handleIncidentUpdated}
                  onOpenRescueTeamView={(resId) => {
                    setSelectedTeamId(resId);
                    setViewMode('rescue-team');
                  }}
                />
              </div>
            )}
          </section>
        </main>
      ) : (
        /* RESCUE TEAM TERMINAL VIEW (MDT) */
        <RescueTeamView
          health={health}
          incidents={allIncidents.length > 0 ? allIncidents : incidents}
          resources={resources}
          selectedTeamId={selectedTeamId}
          onSelectTeamId={setSelectedTeamId}
          onSwitchToDispatcher={(inc) => {
            if (inc) setSelectedIncident(inc);
            setViewMode('dispatcher');
          }}
          onMissionUpdated={() => fetchData(selectedIncident?.id)}
        />
      )}

      {/* Incident Intake Modal */}
      <IncidentModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmitSuccess={handleIncidentCreated}
      />

      {/* Fleet Browser Modal */}
      <ResourceFleet
        isOpen={isFleetOpen}
        onClose={() => setIsFleetOpen(false)}
        resources={resources}
        onSelectIncidentById={handleSelectIncidentById}
      />
    </div>
  );
}
