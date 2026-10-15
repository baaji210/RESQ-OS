import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { MapPin, Navigation, AlertTriangle, ShieldCheck, Layers, Maximize2, Crosshair, AlertCircle } from 'lucide-react';

// Controller to auto-focus map when selected incident changes or fit bounds
function MapFocusController({ selectedIncident, allIncidentsWithCoords }) {
  const map = useMap();

  useEffect(() => {
    if (selectedIncident && selectedIncident.latitude !== null && selectedIncident.longitude !== null) {
      map.flyTo(
        [selectedIncident.latitude, selectedIncident.longitude],
        13,
        { duration: 1.2 }
      );
    }
  }, [selectedIncident?.id, selectedIncident?.latitude, selectedIncident?.longitude, map]);

  return null;
}

// Map Controls component inside MapContainer to provide Fit All and Focus buttons
function MapActionsToolbar({ selectedIncident, incidentsWithCoords }) {
  const map = useMap();

  const handleFitAll = () => {
    if (!incidentsWithCoords || incidentsWithCoords.length === 0) return;
    const bounds = L.latLngBounds(
      incidentsWithCoords.map((i) => [i.latitude, i.longitude])
    );
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
  };

  const handleFocusSelected = () => {
    if (selectedIncident && selectedIncident.latitude !== null && selectedIncident.longitude !== null) {
      map.flyTo([selectedIncident.latitude, selectedIncident.longitude], 14, { duration: 1.0 });
    }
  };

  return (
    <div style={{
      position: 'absolute',
      bottom: '15px',
      right: '15px',
      zIndex: 1000,
      display: 'flex',
      gap: '6px',
    }}>
      {selectedIncident && selectedIncident.latitude !== null && selectedIncident.longitude !== null && (
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          style={{ 
            backgroundColor: '#ffffff', 
            border: '1px solid #0284c7', 
            color: '#0284c7', 
            fontSize: '0.72rem',
            boxShadow: '0 2px 5px rgba(0,0,0,0.1)'
          }}
          onClick={handleFocusSelected}
          title="Jump directly to selected incident coordinates"
        >
          <Crosshair size={13} className="text-cyan" />
          <span className="font-semibold">Focus Incident</span>
        </button>
      )}

      {incidentsWithCoords.length > 1 && (
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          style={{ 
            backgroundColor: '#ffffff', 
            border: '1px solid #cbd5e1', 
            fontSize: '0.72rem',
            boxShadow: '0 2px 5px rgba(0,0,0,0.1)'
          }}
          onClick={handleFitAll}
          title="Zoom out to encompass all plotted emergency signals across all regions"
        >
          <Maximize2 size={13} className="text-secondary" />
          <span>Fit All Signals</span>
        </button>
      )}
    </div>
  );
}

// Custom DivIcons for Incidents
function createIncidentIcon(urgency, isSelected) {
  const colorMap = {
    Critical: '#dc2626',
    High: '#ea580c',
    Medium: '#d97706',
    Low: '#16a34a',
  };
  const color = colorMap[urgency] || '#dc2626';
  const size = isSelected ? 34 : 26;
  const pulseClass = (urgency === 'Critical' || urgency === 'High') ? 'pulse-indicator' : '';

  const html = `
    <div style="position: relative; width: ${size}px; height: ${size}px; display: flex; align-items: center; justify-content: center;">
      <div style="position: absolute; inset: -4px; border-radius: 50%; background-color: ${color}; opacity: 0.35;" class="${pulseClass}"></div>
      <div style="
        width: ${size}px; 
        height: ${size}px; 
        border-radius: 50%; 
        background-color: ${color}; 
        border: 2px solid #ffffff; 
        box-shadow: 0 2px 8px rgba(0,0,0,0.3); 
        display: flex; 
        align-items: center; 
        justify-content: center; 
        color: #ffffff; 
        font-weight: 800; 
        font-size: ${isSelected ? '14px' : '11px'};
      ">
        !
      </div>
    </div>
  `;

  return L.divIcon({
    html,
    className: 'custom-leaflet-marker',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  });
}

// Custom DivIcons for Rescue Units
function createResourceIcon(availability) {
  const isAvail = availability === 'Available';
  const bgColor = isAvail ? '#0284c7' : '#ea580c';

  const html = `
    <div style="
      width: 26px; 
      height: 26px; 
      border-radius: 6px; 
      background-color: ${bgColor}; 
      border: 2px solid #ffffff; 
      box-shadow: 0 2px 6px rgba(0,0,0,0.25); 
      display: flex; 
      align-items: center; 
      justify-content: center; 
      color: #ffffff; 
      font-weight: 700; 
      font-size: 11px;
    ">
      ⛑
    </div>
  `;

  return L.divIcon({
    html,
    className: 'custom-resource-marker',
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -13],
  });
}

export default function CommandMap({ 
  incidents = [], 
  resources = [], 
  selectedIncident, 
  onSelectIncident 
}) {
  // Determine initial center: if selected incident has coordinates, center on it; otherwise default to demo SF coordinates
  const initialCenter = (selectedIncident && selectedIncident.latitude !== null && selectedIncident.longitude !== null)
    ? [selectedIncident.latitude, selectedIncident.longitude]
    : [37.7749, -122.4194];

  // Filter items with valid coordinates
  const incidentsWithCoords = incidents.filter(
    (inc) => inc.latitude !== null && inc.longitude !== null && !isNaN(inc.latitude) && !isNaN(inc.longitude)
  );

  const unmappedIncidents = incidents.filter(
    (inc) => inc.latitude === null || inc.longitude === null || isNaN(inc.latitude) || isNaN(inc.longitude)
  );

  const resourcesWithCoords = resources.filter(
    (res) => res.simulated_lat !== null && res.simulated_lng !== null && !isNaN(res.simulated_lat) && !isNaN(res.simulated_lng)
  );

  const isSelectedUnmapped = selectedIncident && (selectedIncident.latitude === null || selectedIncident.longitude === null);

  return (
    <div className="panel" style={{ height: '100%', minHeight: '380px', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      {/* Map Header Overlay */}
      <div className="flex items-center justify-between" style={{
        padding: '0.65rem 1rem', 
        backgroundColor: '#ffffff', 
        borderBottom: '1px solid var(--border-subtle)',
        zIndex: 20
      }}>
        <div className="flex items-center gap-2">
          <Layers size={16} className="text-cyan" />
          <span className="text-xs font-bold uppercase tracking-wider text-main">
            Geospatial Emergency Grid
          </span>
          <span className="badge badge-sim text-xs">OpenStreetMap Live</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-secondary flex-wrap">
          <div className="flex items-center gap-1.5 font-medium">
            <span style={{ width: '9px', height: '9px', borderRadius: '50%', backgroundColor: '#dc2626' }}></span>
            <span>Plotted Incidents ({incidentsWithCoords.length})</span>
          </div>
          {unmappedIncidents.length > 0 && (
            <div className="flex items-center gap-1 text-xs text-amber-700 font-medium">
              <AlertTriangle size={13} className="text-amber-600" />
              <span>Unmapped ({unmappedIncidents.length})</span>
            </div>
          )}
          <div className="flex items-center gap-1.5 font-medium">
            <span style={{ width: '9px', height: '9px', borderRadius: '3px', backgroundColor: '#0284c7' }}></span>
            <span>Fleet Units ({resourcesWithCoords.length})</span>
          </div>
        </div>
      </div>

      {/* Unmapped Selected Incident Banner Alert */}
      {isSelectedUnmapped && (
        <div style={{
          backgroundColor: '#fffbeb',
          borderBottom: '1px solid #fcd34d',
          padding: '0.5rem 1rem',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '0.75rem',
          color: '#92400e',
          zIndex: 25,
        }}>
          <AlertCircle size={15} className="shrink-0 text-amber-600" />
          <span>
            <strong>Location Unmapped:</strong> Selected Signal #{selectedIncident.id} ("{selectedIncident.location}") has no GPS coordinates and cannot be displayed on the map.
          </span>
        </div>
      )}

      {/* Leaflet Container */}
      <div style={{ flex: 1, position: 'relative', minHeight: '320px' }}>
        <MapContainer
          center={initialCenter}
          zoom={12}
          scrollWheelZoom={true}
          style={{ height: '100%', width: '100%' }}
        >
          {/* OpenStreetMap Standard Clean Bright Tile Layer */}
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <MapFocusController 
            selectedIncident={selectedIncident} 
            allIncidentsWithCoords={incidentsWithCoords} 
          />

          <MapActionsToolbar 
            selectedIncident={selectedIncident} 
            incidentsWithCoords={incidentsWithCoords} 
          />

          {/* Incident Markers */}
          {incidentsWithCoords.map((inc) => {
            const urgency = inc.effective_urgency || inc.urgency;
            const isSelected = selectedIncident?.id === inc.id;
            return (
              <Marker
                key={`inc-${inc.id}`}
                position={[inc.latitude, inc.longitude]}
                icon={createIncidentIcon(urgency, isSelected)}
                eventHandlers={{
                  click: () => onSelectIncident(inc),
                }}
              >
                <Popup>
                  <div style={{ minWidth: '200px', padding: '2px' }}>
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <span className={`badge badge-${urgency.toLowerCase()} text-xs`}>
                        {urgency}
                      </span>
                      <span className={`badge-status ${inc.status} text-xs`}>
                        {inc.status}
                      </span>
                    </div>
                    <div className="font-bold text-sm text-main mb-1">
                      #{inc.id} &bull; {inc.incident_type}
                    </div>
                    <p className="text-xs text-secondary mb-1">
                      {inc.location}
                    </p>
                    <p className="text-xs mono text-cyan mb-1.5 font-semibold">
                      📍 [{inc.latitude.toFixed(4)}, {inc.longitude.toFixed(4)}]
                    </p>
                    <p className="text-xs text-muted mb-2 font-medium">
                      👥 {inc.people_affected} affected
                    </p>
                    <button
                      type="button"
                      className="btn btn-cyan btn-sm"
                      style={{ width: '100%', padding: '0.3rem 0.5rem' }}
                      onClick={() => onSelectIncident(inc)}
                    >
                      Inspect in Dispatcher
                    </button>
                  </div>
                </Popup>
              </Marker>
            );
          })}

          {/* Rescue Resource Markers */}
          {resourcesWithCoords.map((res) => (
            <Marker
              key={`res-${res.id}`}
              position={[res.simulated_lat, res.simulated_lng]}
              icon={createResourceIcon(res.availability)}
            >
              <Popup>
                <div style={{ minWidth: '180px', padding: '2px' }}>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="badge badge-rule text-xs">
                      {res.contact_callsign}
                    </span>
                    <span className={`badge-status ${res.availability === 'Available' ? 'Resolved' : 'Assigned'} text-xs`}>
                      {res.availability}
                    </span>
                  </div>
                  <div className="font-bold text-sm text-main mb-1">
                    {res.name}
                  </div>
                  <p className="text-xs text-secondary mb-1">
                    📍 {res.simulated_location_name}
                  </p>
                  <p className="text-xs text-muted font-medium">
                    Type: {res.resource_type} | Cap: {res.capacity}
                  </p>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
