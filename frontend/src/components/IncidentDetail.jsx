import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  Bot,
  Cpu,
  AlertTriangle,
  CheckCircle,
  Truck,
  Clock,
  MapPin,
  Users,
  Compass,
  ArrowRight,
  UserCheck,
  Check,
  X,
  History,
  FileText,
  AlertCircle
} from 'lucide-react';
import { api } from '../services/api';

export default function IncidentDetail({
  incident,
  onIncidentUpdated,
  onOpenRescueTeamView,
}) {
  const [recommendations, setRecommendations] = useState(null);
  const [recLoading, setRecLoading] = useState(false);
  const [recError, setRecError] = useState(null);

  // Status update state
  const [selectedStatus, setSelectedStatus] = useState('');
  const [statusNote, setStatusNote] = useState('');
  const [statusUpdating, setStatusUpdating] = useState(false);

  // Urgency override state
  const [overrideUrgency, setOverrideUrgency] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [showOverrideForm, setShowOverrideForm] = useState(false);
  const [overrideUpdating, setOverrideUpdating] = useState(false);

  // Assign resource state
  const [assigningId, setAssigningId] = useState(null);

  // Load recommendations whenever incident changes
  useEffect(() => {
    if (!incident) return;
    setSelectedStatus(incident.status);
    setOverrideUrgency(incident.dispatcher_urgency_override || incident.urgency);
    setShowOverrideForm(false);

    let isMounted = true;
    async function loadRecommendations() {
      setRecLoading(true);
      setRecError(null);
      try {
        const data = await api.getRecommendations(incident.id);
        if (isMounted) setRecommendations(data);
      } catch (err) {
        if (isMounted) setRecError(err.message || 'Failed to calculate recommendations');
      } finally {
        if (isMounted) setRecLoading(false);
      }
    }

    loadRecommendations();
    return () => { isMounted = false; };
  }, [incident?.id, incident?.status, incident?.assigned_resource_id]);

  if (!incident) {
    return (
      <div className="panel flex items-center justify-center text-center p-8" style={{ height: '100%', minHeight: '380px', backgroundColor: '#ffffff' }}>
        <div>
          <ShieldAlert size={44} className="text-secondary opacity-30 mx-auto mb-3" />
          <h3 className="text-base font-bold text-main mb-1">No Incident Selected</h3>
          <p className="text-xs text-muted max-w-sm">
            Select an active signal from the queue or click on a map marker to review AI triage, dispatch units, and manage incident workflow.
          </p>
        </div>
      </div>
    );
  }

  const effectiveUrgency = incident.dispatcher_urgency_override || incident.urgency;
  const isOverridden = Boolean(incident.dispatcher_urgency_override);
  const urgencyColor = effectiveUrgency === 'Critical' ? '#dc2626' : effectiveUrgency === 'High' ? '#ea580c' : effectiveUrgency === 'Medium' ? '#d97706' : '#16a34a';

  // Status progression workflow
  const workflowStatuses = ['Reported', 'Verified', 'Assigned', 'Accepted', 'En Route', 'Arrived', 'Resolved'];

  const handleAdvanceStatus = async (newStatus) => {
    setStatusUpdating(true);
    try {
      const updated = await api.updateIncidentStatus(
        incident.id,
        newStatus,
        statusNote || `Advanced status to ${newStatus}`,
        'Dispatcher Lead'
      );
      setStatusNote('');
      onIncidentUpdated(updated);
    } catch (err) {
      alert(`Error updating status: ${err.message}`);
    } finally {
      setStatusUpdating(false);
    }
  };

  const handleSaveOverride = async (e) => {
    e.preventDefault();
    if (!overrideUrgency) return;
    setOverrideUpdating(true);
    try {
      const updated = await api.overrideUrgency(
        incident.id,
        overrideUrgency,
        overrideReason || 'Dispatcher field assessment override',
        'Dispatcher Lead'
      );
      setShowOverrideForm(false);
      onIncidentUpdated(updated);
    } catch (err) {
      alert(`Error applying override: ${err.message}`);
    } finally {
      setOverrideUpdating(false);
    }
  };

  const handleAssignResource = async (resourceId, reassign = false) => {
    setAssigningId(resourceId);
    try {
      const updated = await api.assignResource(
        incident.id,
        resourceId,
        reassign
          ? 'Reassigned and diverted unit from previous incident by Dispatcher Lead'
          : 'Authorized by human dispatcher based on recommendation match',
        'Dispatcher Lead',
        reassign
      );
      onIncidentUpdated(updated);
    } catch (err) {
      alert(`Assignment failed: ${err.message}`);
    } finally {
      setAssigningId(null);
    }
  };

  const handleUnassignResource = async () => {
    if (!window.confirm('Release assigned resource and return to standby?')) return;
    try {
      const updated = await api.unassignResource(incident.id);
      onIncidentUpdated(updated);
    } catch (err) {
      alert(`Release failed: ${err.message}`);
    }
  };

  return (
    <div className="panel flex flex-col" style={{ height: '100%', overflowY: 'auto', backgroundColor: '#ffffff' }}>
      {/* Top Header */}
      <div style={{ padding: '0.9rem 1.25rem', borderBottom: '1px solid var(--border-subtle)', backgroundColor: '#ffffff' }}>
        <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
          <div className="flex items-center gap-2">
            <span className="mono text-xs text-cyan font-bold">SIGNAL #{incident.id}</span>
            <h2 className="text-base font-extrabold text-main">
              {incident.incident_type}
            </h2>
            <span className={`badge badge-${effectiveUrgency.toLowerCase()}`}>
              {effectiveUrgency}
            </span>
            {isOverridden && (
              <span className="badge badge-sim text-xs" title={`Original AI: ${incident.urgency}`}>
                Overridden
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span className={`badge-status ${incident.status}`}>
              {incident.status}
            </span>
          </div>
        </div>

        {/* Location & Time Subtitle */}
        <div className="flex items-center gap-3 text-xs text-secondary flex-wrap font-medium">
          <span className="flex items-center gap-1">
            <MapPin size={13} className={incident.latitude !== null && incident.longitude !== null ? "text-cyan" : "text-amber-600"} />
            <span>{incident.location}</span>
          </span>
          {incident.latitude !== null && incident.longitude !== null ? (
            <span className="badge badge-rule mono text-xs font-semibold" style={{ fontSize: '0.68rem' }}>
              📍 GPS: [{incident.latitude.toFixed(4)}, {incident.longitude.toFixed(4)}]
            </span>
          ) : (
            <span className="badge text-xs" style={{ backgroundColor: '#fffbeb', color: '#b45309', border: '1px solid #fcd34d', fontSize: '0.68rem' }}>
              ⚠️ Map Location Unavailable
            </span>
          )}
          <span className="flex items-center gap-1">
            <Users size={13} className="text-cyan" />
            <span>{incident.people_affected} affected individuals</span>
          </span>
          <span className="flex items-center gap-1 text-muted">
            <Clock size={13} />
            <span>{new Date(incident.reported_time).toLocaleString()}</span>
          </span>
        </div>
      </div>

      <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', backgroundColor: '#f8fafc' }}>
        {/* Narrative Description */}
        <div className="card">
          <div className="text-xs text-muted uppercase font-bold mb-1.5 flex items-center gap-1.5">
            <FileText size={14} className="text-cyan" />
            <span>Signal Narrative &amp; Telemetry</span>
          </div>
          <p className="text-sm text-main" style={{ lineHeight: 1.6 }}>
            {incident.description}
          </p>
        </div>

        {/* AI & Heuristic Triage Card */}
        <div className="card" style={{ borderLeft: `4px solid ${urgencyColor}` }}>
          <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
            <div className="flex items-center gap-2">
              {incident.assessment_method === 'ai_generated' ? (
                <div className="flex items-center gap-1.5 text-xs font-bold text-cyan">
                  <Bot size={16} />
                  <span>AI-ASSISTED TRIAGE ASSESSMENT</span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 text-xs font-bold text-cyan">
                  <Cpu size={16} />
                  <span>DETERMINISTIC HEURISTIC TRIAGE (RULE-BASED FALLBACK)</span>
                </div>
              )}
            </div>

            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setShowOverrideForm(!showOverrideForm)}
            >
              <UserCheck size={13} className="text-secondary" />
              <span>{showOverrideForm ? 'Close Override' : 'Dispatcher Override'}</span>
            </button>
          </div>

          {/* Explanation Text */}
          <p className="text-xs text-secondary mb-3 font-medium" style={{ lineHeight: 1.55 }}>
            {incident.urgency_explanation || 'Assessment completed based on situational indicators and affected casualty headcount.'}
          </p>

          {/* Uncertainty Meter */}
          <div style={{ marginBottom: '0.85rem', backgroundColor: '#ffffff', padding: '0.65rem 0.85rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-secondary font-semibold">Uncertainty Index</span>
              <span className="mono font-bold text-cyan">
                {Math.round((incident.uncertainty_score || 0.15) * 100)}% Uncertainty &bull; {100 - Math.round((incident.uncertainty_score || 0.15) * 100)}% Confidence
              </span>
            </div>
            <div style={{ width: '100%', height: '6px', backgroundColor: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{
                width: `${Math.round((incident.uncertainty_score || 0.15) * 100)}%`,
                height: '100%',
                backgroundColor: incident.uncertainty_score > 0.4 ? '#ea580c' : '#0284c7'
              }}></div>
            </div>
            {incident.uncertainty_note && (
              <p className="text-xs text-muted mt-1.5 italic font-medium">
                Note: {incident.uncertainty_note}
              </p>
            )}
          </div>

          {/* Key Risks & Required Capabilities */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs text-muted uppercase font-bold mb-1.5">
                Extracted Risk Factors
              </div>
              <div className="flex flex-wrap gap-1">
                {incident.key_risks && incident.key_risks.length > 0 ? (
                  incident.key_risks.map((risk, i) => (
                    <span key={i} className="badge badge-high" style={{ textTransform: 'none', fontSize: '0.7rem' }}>
                      {risk}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-muted font-medium">No specific secondary risks flagged</span>
                )}
              </div>
            </div>

            <div>
              <div className="text-xs text-muted uppercase font-bold mb-1.5">
                Required Capabilities
              </div>
              <div className="flex flex-wrap gap-1">
                {incident.recommended_capabilities && incident.recommended_capabilities.length > 0 ? (
                  incident.recommended_capabilities.map((cap, i) => (
                    <span key={i} className="badge badge-rule" style={{ textTransform: 'none', fontSize: '0.7rem' }}>
                      {cap}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-muted font-medium">Standard incident response</span>
                )}
              </div>
            </div>
          </div>

          {/* Dispatcher Override Form Inline */}
          {showOverrideForm && (
            <form onSubmit={handleSaveOverride} style={{ marginTop: '1rem', paddingTop: '0.85rem', borderTop: '1px solid var(--border-subtle)' }}>
              <div className="text-xs font-bold text-main uppercase mb-2">
                Human Dispatcher Urgency Override
              </div>
              <div className="grid grid-cols-2 gap-2 mb-2">
                <div>
                  <label className="label">Manual Urgency</label>
                  <select
                    className="select text-xs"
                    value={overrideUrgency}
                    onChange={(e) => setOverrideUrgency(e.target.value)}
                  >
                    <option value="Critical">Critical</option>
                    <option value="High">High</option>
                    <option value="Medium">Medium</option>
                    <option value="Low">Low</option>
                  </select>
                </div>
                <div>
                  <label className="label">Rationale / Field Log</label>
                  <input
                    type="text"
                    className="input text-xs"
                    placeholder="e.g. Eyewitness video confirms active water rise"
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setShowOverrideForm(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-cyan btn-sm"
                  disabled={overrideUpdating}
                >
                  {overrideUpdating ? 'Saving...' : 'Apply Urgency Override'}
                </button>
              </div>
            </form>
          )}

          {/* Regulatory & Safety Disclaimer */}
          <div className="flex items-center gap-2 mt-3 pt-2 text-xs text-muted" style={{ borderTop: '1px solid #e2e8f0', fontSize: '0.68rem' }}>
            <AlertCircle size={13} className="text-secondary shrink-0" />
            <span>
              DECISION SUPPORT PROTOCOL — Rule-based triage system. Human dispatcher authorization required before physical deployment.
            </span>
          </div>
        </div>

        {/* Workflow Status Progression */}
        <div className="card">
          <div className="text-xs text-muted uppercase font-bold mb-2.5 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Compass size={14} className="text-cyan" />
              <span>Incident Response Lifecycle</span>
            </span>
            <span className="mono text-xs text-cyan font-bold">Current: {incident.status}</span>
          </div>

          <div className="flex items-center justify-between gap-1.5 flex-wrap">
            {workflowStatuses.map((st, index) => {
              const isCurrent = incident.status === st;
              const isPassed = workflowStatuses.indexOf(incident.status) > index;
              return (
                <button
                  key={st}
                  type="button"
                  className={`btn btn-sm ${isCurrent ? 'btn-primary' : isPassed ? 'btn-secondary' : 'btn-secondary'}`}
                  style={{
                    flex: '1 1 0%',
                    minWidth: '92px',
                    fontSize: '0.72rem',
                    borderColor: isCurrent ? '#dc2626' : isPassed ? '#16a34a' : '#cbd5e1',
                    backgroundColor: isCurrent ? '#dc2626' : isPassed ? '#f0fdf4' : '#ffffff',
                    color: isCurrent ? '#ffffff' : isPassed ? '#15803d' : '#334155',
                    opacity: isCurrent || isPassed ? 1 : 0.7,
                  }}
                  disabled={statusUpdating || isCurrent}
                  onClick={() => handleAdvanceStatus(st)}
                >
                  {isPassed && <Check size={12} className="text-low" />}
                  <span>{st}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Rescue Resource Recommendations & Assignment */}
        <div className="card">
          <div className="flex items-center justify-between gap-2 mb-2.5">
            <div className="flex items-center gap-1.5">
              <Truck size={15} className="text-cyan" />
              <span className="text-xs font-bold uppercase tracking-wider text-main">
                Rescue Resource Matching &amp; Deployment
              </span>
            </div>
            {incident.assigned_resource && (
              <span className="badge badge-low text-xs">
                Unit Assigned: {incident.assigned_resource.contact_callsign}
              </span>
            )}
          </div>

          {/* Currently Assigned Asset Banner */}
          {incident.assigned_resource && (
            <div style={{
              backgroundColor: '#f0f9ff',
              border: '1px solid #bae6fd',
              borderRadius: '8px',
              padding: '0.85rem 1rem',
              marginBottom: '1rem',
              boxShadow: '0 1px 2px rgba(2, 132, 199, 0.05)'
            }}>
              <div className="flex items-center justify-between flex-wrap gap-2 mb-1.5">
                <div>
                  <span className="badge badge-rule text-xs mr-2 font-bold">{incident.assigned_resource.contact_callsign}</span>
                  <strong className="text-sm text-main">{incident.assigned_resource.name}</strong>
                  <span className="text-xs text-secondary ml-2 font-medium">({incident.assigned_resource.resource_type})</span>
                </div>
                <div className="flex items-center gap-2">
                  {onOpenRescueTeamView && (
                    <button
                      type="button"
                      className="btn btn-cyan btn-sm"
                      style={{ fontSize: '0.72rem', padding: '0.25rem 0.65rem' }}
                      onClick={() => onOpenRescueTeamView(incident.assigned_resource.id)}
                      title="Open dedicated Rescue Team Mobile Data Terminal for this assigned unit"
                    >
                      <Truck size={12} />
                      <span>View in Team MDT &rarr;</span>
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn-danger btn-sm"
                    style={{ fontSize: '0.72rem', padding: '0.25rem 0.65rem' }}
                    onClick={handleUnassignResource}
                  >
                    <X size={12} />
                    <span>Release Unit</span>
                  </button>
                </div>
              </div>
              <p className="text-xs text-secondary font-medium">
                📍 Station: {incident.assigned_resource.simulated_location_name} &bull; Capacity: {incident.assigned_resource.capacity} specialists
              </p>
            </div>
          )}

          {/* Awaiting Dispatcher Approval Alert when unassigned */}
          {!incident.assigned_resource && (
            <div style={{
              backgroundColor: '#f0f9ff',
              border: '1px solid #bae6fd',
              borderRadius: '6px',
              padding: '0.65rem 0.85rem',
              marginBottom: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '0.75rem',
              color: '#0369a1'
            }}>
              <AlertCircle size={16} className="text-cyan shrink-0" />
              <span>
                <strong>HUMAN DISPATCHER APPROVAL REQUIRED:</strong> Review the matching fleet units below and click <strong>"Approve &amp; Dispatch Unit"</strong> to authorize deployment.
              </span>
            </div>
          )}

          {/* Recommendation List */}
          <div className="text-xs text-secondary mb-2 font-medium">
            {recommendations?.explanation || 'Calculating operational suitability based on capability match and availability...'}
          </div>

          {recLoading && (
            <div className="text-center py-4 text-xs text-muted">
              <div className="pulse-indicator mb-1"></div>
              <div>Computing distance and capability matches...</div>
            </div>
          )}

          {recError && (
            <div className="text-xs text-critical py-2 font-medium">
              Could not load recommendations: {recError}
            </div>
          )}

          {!recLoading && recommendations?.recommendations && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {recommendations.recommendations.slice(0, 4).map((rec) => {
                const res = rec.resource;
                const isCurrentlyAssigned = incident.assigned_resource_id === res.id;

                return (
                  <div
                    key={res.id}
                    className="card"
                    style={{
                      padding: '0.75rem',
                      backgroundColor: isCurrentlyAssigned ? '#f0fdf4' : '#ffffff',
                      borderColor: isCurrentlyAssigned ? '#86efac' : 'var(--border-subtle)',
                      boxShadow: 'var(--shadow-sm)'
                    }}
                  >
                    <div className="flex items-center justify-between flex-wrap gap-2 mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="mono text-xs font-bold text-cyan">
                          {res.contact_callsign}
                        </span>
                        <strong className="text-sm text-main">{res.name}</strong>
                        <span className={`badge ${rec.priority_level === 'Primary Recommendation' ? 'badge-low' : 'badge-secondary'} text-xs font-semibold`}>
                          {rec.priority_level}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="mono text-xs font-bold text-cyan">
                          Match: {rec.match_score}%
                        </span>
                        <span className={`badge-status ${res.availability === 'Available' ? 'Resolved' : 'Assigned'} text-xs`}>
                          {res.availability}
                        </span>
                      </div>
                    </div>

                    {/* Proximity & Station */}
                    <div className="flex items-center gap-3 text-xs text-secondary mb-1 font-medium">
                      <span>📍 {res.simulated_location_name}</span>
                      {rec.distance_km !== null ? (
                        <span className="mono text-cyan font-bold">
                          📏 {rec.distance_km} km away
                        </span>
                      ) : (
                        <span className="text-muted italic">
                          (Distance N/A — no GPS coords)
                        </span>
                      )}
                    </div>

                    {/* Recommendation Reason */}
                    <p className="text-xs text-muted mb-2 font-medium">
                      {rec.recommendation_reason}
                    </p>

                    {/* Action button */}
                    <div className="flex items-center justify-between pt-2" style={{ borderTop: '1px solid #e2e8f0' }}>
                      <div className="flex flex-wrap gap-1">
                        {rec.matched_capabilities.map((c, idx) => (
                          <span key={idx} className="badge badge-rule" style={{ fontSize: '0.65rem' }}>
                            ✓ {c}
                          </span>
                        ))}
                      </div>

                      {isCurrentlyAssigned ? (
                        <span className="text-xs text-low font-bold flex items-center gap-1">
                          <CheckCircle size={14} /> Assigned to Mission
                        </span>
                      ) : !rec.is_available ? (
                        <div className="flex items-center gap-1.5">
                          <span className="badge text-xs" style={{ backgroundColor: '#fffbeb', color: '#b45309', border: '1px solid #fcd34d' }}>
                            {res.availability === 'Maintenance' ? 'In Maintenance' : `Deployed (#${res.current_incident_id})`}
                          </span>
                          {res.availability !== 'Maintenance' && res.current_incident_id && (
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              style={{ fontSize: '0.68rem', padding: '0.15rem 0.5rem', borderColor: '#ea580c', color: '#ea580c' }}
                              disabled={assigningId === res.id}
                              onClick={() => {
                                if (window.confirm(`Unit '${res.name}' is currently deployed to Incident #${res.current_incident_id}. Divert and reassign to Incident #${incident.id}?`)) {
                                  handleAssignResource(res.id, true);
                                }
                              }}
                              title={`Divert unit from Signal #${res.current_incident_id} to this mission`}
                            >
                              <ArrowRight size={11} />
                              <span>{assigningId === res.id ? 'Reassigning...' : 'Divert / Reassign'}</span>
                            </button>
                          )}
                        </div>
                      ) : !rec.is_suitable ? (
                        <span className="badge text-xs" style={{ backgroundColor: '#fef2f2', color: '#b91c1c', border: '1px solid #fca5a5' }}>
                          Capability Mismatch
                        </span>
                      ) : (
                        <button
                          type="button"
                          className="btn btn-cyan btn-sm"
                          disabled={assigningId === res.id}
                          onClick={() => handleAssignResource(res.id, false)}
                          style={{ padding: '0.3rem 0.75rem' }}
                        >
                          <ArrowRight size={13} />
                          <span>{assigningId === res.id ? 'Deploying...' : 'Approve & Dispatch Unit'}</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Action Logs & Timeline */}
        <div className="card">
          <div className="text-xs text-muted uppercase font-bold mb-2 flex items-center gap-1.5">
            <History size={14} className="text-cyan" />
            <span>Dispatcher Audit Log &amp; Timeline</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {incident.action_logs && incident.action_logs.length > 0 ? (
              incident.action_logs.map((log) => (
                <div
                  key={log.id}
                  style={{
                    padding: '0.6rem 0.85rem',
                    backgroundColor: '#ffffff',
                    borderRadius: '6px',
                    border: '1px solid #e2e8f0',
                    borderLeft: '3px solid #0284c7',
                    fontSize: '0.75rem',
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
              <div className="text-xs text-muted font-medium">No logged actions recorded yet.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
