import React from 'react';
import { 
  Search, 
  Filter, 
  Users, 
  MapPin, 
  Clock, 
  Flame, 
  Waves, 
  Building2, 
  AlertOctagon, 
  Activity, 
  Wind,
  ShieldAlert,
  Bot,
  Cpu
} from 'lucide-react';

function getIncidentIcon(type) {
  const t = (type || '').toLowerCase();
  if (t.includes('flood') || t.includes('water')) return <Waves size={16} className="text-cyan shrink-0" />;
  if (t.includes('fire')) return <Flame size={16} className="text-critical shrink-0" />;
  if (t.includes('collapse') || t.includes('earthquake')) return <Building2 size={16} className="text-high shrink-0" />;
  if (t.includes('chemical') || t.includes('hazmat')) return <AlertOctagon size={16} className="text-medium shrink-0" />;
  if (t.includes('medical')) return <Activity size={16} className="text-critical shrink-0" />;
  if (t.includes('storm')) return <Wind size={16} className="text-cyan shrink-0" />;
  return <ShieldAlert size={16} className="text-secondary shrink-0" />;
}

export default function IncidentQueue({
  incidents = [],
  selectedIncident,
  onSelectIncident,
  searchQuery,
  onSearchChange,
  urgencyFilter,
  onUrgencyFilterChange,
  statusFilter,
  onStatusFilterChange,
  loading,
}) {
  const urgencies = ['All', 'Critical', 'High', 'Medium', 'Low'];
  const statuses = ['All', 'Reported', 'Verified', 'Assigned', 'Accepted', 'En Route', 'Arrived', 'Resolved'];

  const formatTime = (isoString) => {
    if (!isoString) return '';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <div className="panel flex flex-col" style={{ height: '100%', maxHeight: 'calc(100vh - 165px)' }}>
      {/* Top Filter Bar */}
      <div style={{ padding: '0.85rem 1rem', borderBottom: '1px solid var(--border-subtle)', backgroundColor: '#ffffff' }}>
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <Filter size={15} className="text-cyan" />
            <span className="text-xs font-bold uppercase tracking-wider text-main">
              Signal Triage Queue
            </span>
          </div>
          <span className="text-xs text-muted mono font-semibold">
            {incidents.length} signals
          </span>
        </div>

        {/* Search input */}
        <div style={{ position: 'relative', marginBottom: '0.65rem' }}>
          <Search size={14} className="text-muted" style={{ position: 'absolute', left: '10px', top: '10px' }} />
          <input
            type="text"
            className="input text-xs"
            style={{ paddingLeft: '32px' }}
            placeholder="Search address, hazard, keywords..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>

        {/* Urgency Filter Tabs */}
        <div className="flex items-center gap-1 flex-wrap mb-2">
          {urgencies.map((urg) => (
            <button
              key={urg}
              type="button"
              className={`btn btn-sm ${urgencyFilter === urg ? 'btn-cyan' : 'btn-secondary'}`}
              style={{ fontSize: '0.68rem', padding: '0.15rem 0.5rem' }}
              onClick={() => onUrgencyFilterChange(urg)}
            >
              {urg}
            </button>
          ))}
        </div>

        {/* Status Filter Tabs */}
        <div className="flex items-center gap-1 flex-wrap">
          {statuses.map((st) => (
            <button
              key={st}
              type="button"
              className={`btn btn-sm ${statusFilter === st ? 'btn-cyan' : 'btn-secondary'}`}
              style={{ fontSize: '0.68rem', padding: '0.15rem 0.5rem' }}
              onClick={() => onStatusFilterChange(st)}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Incident List */}
      <div style={{ 
        flex: 1, 
        overflowY: 'auto', 
        padding: '0.75rem', 
        display: 'flex', 
        flexDirection: 'column', 
        gap: '0.65rem',
        backgroundColor: '#f8fafc'
      }}>
        {loading && (
          <div className="text-center py-8 text-xs text-muted">
            <div className="pulse-indicator mb-2"></div>
            <div>Syncing emergency dispatch signals...</div>
          </div>
        )}

        {!loading && incidents.length === 0 && (
          <div className="text-center py-10 text-xs text-muted">
            <ShieldAlert size={32} className="mx-auto text-secondary mb-2 opacity-40" />
            <div className="font-medium text-main">No matching incidents</div>
            <div className="text-muted mt-0.5">Try clearing or adjusting search and filters.</div>
          </div>
        )}

        {!loading && incidents.map((inc) => {
          const effectiveUrgency = inc.effective_urgency || inc.urgency;
          const isSelected = selectedIncident?.id === inc.id;
          const urgencyColor = effectiveUrgency === 'Critical' ? '#dc2626' : effectiveUrgency === 'High' ? '#ea580c' : effectiveUrgency === 'Medium' ? '#d97706' : '#16a34a';

          return (
            <div
              key={inc.id}
              className={`card ${isSelected ? 'selected' : ''}`}
              style={{ 
                cursor: 'pointer', 
                position: 'relative',
                borderLeft: isSelected ? `4px solid ${urgencyColor}` : '4px solid transparent',
              }}
              onClick={() => onSelectIncident(inc)}
            >
              {/* Card Header */}
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-1.5 min-w-0">
                  {getIncidentIcon(inc.incident_type)}
                  <span className="font-bold text-sm text-main truncate">
                    #{inc.id} &bull; {inc.incident_type}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className={`badge badge-${effectiveUrgency.toLowerCase()} text-xs`}>
                    {effectiveUrgency}
                  </span>
                  <span className={`badge-status ${inc.status} text-xs`}>
                    {inc.status}
                  </span>
                </div>
              </div>

              {/* Location */}
              <div className="flex items-center gap-1.5 text-xs text-secondary mb-1">
                <MapPin size={12} className={inc.latitude !== null && inc.longitude !== null ? "text-cyan shrink-0" : "text-amber-600 shrink-0"} />
                <span className="truncate font-medium">{inc.location}</span>
                {inc.latitude !== null && inc.longitude !== null ? (
                  <span className="mono text-2xs text-cyan shrink-0 ml-auto font-semibold">
                    [{inc.latitude.toFixed(2)}, {inc.longitude.toFixed(2)}]
                  </span>
                ) : (
                  <span className="badge text-2xs shrink-0 ml-auto" style={{ backgroundColor: '#fffbeb', color: '#b45309', border: '1px solid #fcd34d', padding: '0.05rem 0.35rem' }}>
                    No GPS
                  </span>
                )}
              </div>

              {/* Description Snippet */}
              <p className="text-xs text-secondary mb-2" style={{
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                lineHeight: 1.45,
              }}>
                {inc.description}
              </p>

              {/* Footer Meta */}
              <div className="flex items-center justify-between text-xs text-muted pt-2" style={{ borderTop: '1px solid #e2e8f0' }}>
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1 font-medium text-secondary">
                    <Users size={12} className="text-cyan" />
                    <span>{inc.people_affected} affected</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock size={12} />
                    <span>{formatTime(inc.reported_time)}</span>
                  </span>
                </div>

                <div className="flex items-center gap-1">
                  {inc.assessment_method === 'ai_generated' ? (
                    <span className="badge badge-ai" style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem' }}>
                      <Bot size={11} /> AI Core
                    </span>
                  ) : (
                    <span className="badge badge-rule" style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem' }}>
                      <Cpu size={11} /> Rule Fallback
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
