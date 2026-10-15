import React, { useState } from 'react';
import { Truck, CheckCircle, Clock, MapPin, Users, Shield, Wrench, X } from 'lucide-react';

export default function ResourceFleet({
  isOpen,
  onClose,
  resources = [],
  onSelectIncidentById,
}) {
  const [filterType, setFilterType] = useState('All');
  const [filterAvail, setFilterAvail] = useState('All');

  if (!isOpen) return null;

  const filtered = resources.filter((r) => {
    if (filterType !== 'All' && r.resource_type !== filterType) return false;
    if (filterAvail !== 'All' && r.availability !== filterAvail) return false;
    return true;
  });

  const resourceTypes = ['All', ...new Set(resources.map((r) => r.resource_type))];
  const availabilities = ['All', 'Available', 'Assigned', 'Maintenance'];

  return (
    <div className="modal-backdrop">
      <div className="modal-content" style={{ maxWidth: '820px' }}>
        {/* Modal Header */}
        <div className="flex items-center justify-between" style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-subtle)', backgroundColor: '#ffffff' }}>
          <div className="flex items-center gap-2">
            <Truck size={18} className="text-cyan" />
            <h2 className="text-base font-bold text-main uppercase tracking-wider">
              Emergency Resource Fleet ({resources.length} Units)
            </h2>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onClose}
          >
            <X size={16} />
          </button>
        </div>

        {/* Filters */}
        <div style={{ padding: '0.85rem 1.25rem', borderBottom: '1px solid var(--border-subtle)', backgroundColor: '#f8fafc' }}>
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="text-xs text-secondary uppercase font-bold tracking-wide">Availability:</span>
              <div className="flex items-center gap-1">
                {availabilities.map((a) => (
                  <button
                    key={a}
                    type="button"
                    className={`btn btn-sm ${filterAvail === a ? 'btn-cyan' : 'btn-secondary'}`}
                    style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem' }}
                    onClick={() => setFilterAvail(a)}
                  >
                    {a}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-secondary uppercase font-bold tracking-wide">Type:</span>
              <select
                className="select text-xs"
                style={{ width: 'auto', padding: '0.2rem 0.6rem', backgroundColor: '#ffffff' }}
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
              >
                {resourceTypes.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Grid of Resources */}
        <div style={{ padding: '1.25rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '0.85rem', maxHeight: '65vh', overflowY: 'auto', backgroundColor: '#f8fafc' }}>
          {filtered.map((res) => {
            const isAvail = res.availability === 'Available';
            return (
              <div
                key={res.id}
                className="card"
                style={{
                  borderLeft: `3px solid ${isAvail ? '#16a34a' : '#ea580c'}`,
                  backgroundColor: '#ffffff'
                }}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div>
                    <span className="mono text-xs font-bold text-cyan mr-1.5">
                      {res.contact_callsign}
                    </span>
                    <strong className="text-sm text-main">{res.name}</strong>
                  </div>
                  <span className={`badge-status ${isAvail ? 'Resolved' : 'Assigned'} text-xs`}>
                    {res.availability}
                  </span>
                </div>

                <div className="text-xs text-secondary mb-1 font-medium">
                  Type: <strong className="text-main">{res.resource_type}</strong>
                </div>

                <div className="flex items-center gap-1.5 text-xs text-muted mb-2 font-medium">
                  <MapPin size={12} className="text-cyan shrink-0" />
                  <span>{res.simulated_location_name}</span>
                  {res.simulated_lat && (
                    <span className="mono text-xs text-secondary font-semibold">
                      [{res.simulated_lat.toFixed(3)}, {res.simulated_lng.toFixed(3)}]
                    </span>
                  )}
                </div>

                {/* Capabilities */}
                <div className="flex flex-wrap gap-1 mb-2">
                  {res.capabilities && res.capabilities.map((cap, i) => (
                    <span key={i} className="badge badge-rule" style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem' }}>
                      {cap}
                    </span>
                  ))}
                </div>

                {/* Footer Info */}
                <div className="flex items-center justify-between text-xs text-muted pt-2 font-medium" style={{ borderTop: '1px solid #e2e8f0' }}>
                  <span>Capacity: {res.capacity} operatives</span>
                  {res.current_incident_id && (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      style={{ fontSize: '0.68rem', padding: '0.15rem 0.45rem', color: '#0284c7' }}
                      onClick={() => {
                        onSelectIncidentById(res.current_incident_id);
                        onClose();
                      }}
                    >
                      Assigned to Signal #{res.current_incident_id} &rarr;
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between" style={{ padding: '0.85rem 1.25rem', borderTop: '1px solid var(--border-subtle)', backgroundColor: '#ffffff' }}>
          <span className="text-xs text-muted font-medium">
            All units are simulated entities for emergency coordination exercises.
          </span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
