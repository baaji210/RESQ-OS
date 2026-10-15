import React, { useState } from 'react';
import { X, Send, Sparkles, MapPin, AlertCircle, CheckCircle, Info, Search, RefreshCw } from 'lucide-react';
import { api } from '../services/api';

const PRESET_SCENARIOS = [
  {
    title: '-- Select a Quick Demo Scenario --',
    type: 'Flood',
    location: '',
    description: '',
    people: 1,
    lat: '',
    lng: '',
  },
  {
    title: '🚨 Flash Flood at Downtown Underpass (Critical)',
    type: 'Flood',
    location: 'Mission & 8th Street Underpass',
    description: 'Rapid stormwater runoff flooding roadway. Two vehicles stalled with 5 occupants trapped on roof. Water depth rising over 4 feet.',
    people: 5,
    lat: 37.7765,
    lng: -122.4140,
  },
  {
    title: '🏢 Commercial Structure Partial Wall Failure (Critical)',
    type: 'Structural Collapse',
    location: '720 Market St Commercial Block',
    description: 'Cracking facade and mezzanine floor collapsed following seismic tremor. Heavy rubble pinning 3 workers. Shoring and search dogs required.',
    people: 3,
    lat: 37.7878,
    lng: -122.4045,
  },
  {
    title: '🧪 Chemical Gas Cloud at Distribution Hub (High)',
    type: 'Chemical Spill',
    location: 'Bayview Logistics Yard Berth 12',
    description: 'Forklift punctured chlorine cylinder. Yellowish vapor plume blowing north towards warehouse. 10 workers coughing and evacuating.',
    people: 10,
    lat: 37.7420,
    lng: -122.3880,
  },
  {
    title: '🔥 Electrical Substation Transformer Blaze (High)',
    type: 'Fire',
    location: '16th & Potrero Power Complex',
    description: 'High-voltage transformer exploded. Heavy oil fire emitting toxic fumes. Power outages affecting 2 neighborhood clinics.',
    people: 2,
    lat: 37.7650,
    lng: -122.4075,
  },
  {
    title: '🏥 Senior Community Center Heat Crisis (Medium)',
    type: 'Medical Emergency',
    location: '340 Sunset Blvd Senior Living',
    description: 'HVAC malfunction during severe temperature surge. 6 residents suffering heat exhaustion and dehydration; require triage and cooling.',
    people: 6,
    lat: 37.7510,
    lng: -122.4850,
  },
];

export default function IncidentModal({ isOpen, onClose, onSubmitSuccess }) {
  const [incidentType, setIncidentType] = useState('Flood');
  const [location, setLocation] = useState('');
  const [description, setDescription] = useState('');
  const [peopleAffected, setPeopleAffected] = useState(1);
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [isPresetCoords, setIsPresetCoords] = useState(false);

  // Geocoding state
  const [geocoding, setGeocoding] = useState(false);
  const [geocodeFeedback, setGeocodeFeedback] = useState(null); // { type: 'success' | 'warn' | 'info', text: string }

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successData, setSuccessData] = useState(null);

  if (!isOpen) return null;

  const handleSelectPreset = (e) => {
    const selected = PRESET_SCENARIOS[e.target.selectedIndex];
    if (!selected || !selected.location) return;
    setIncidentType(selected.type);
    setLocation(selected.location);
    setDescription(selected.description);
    setPeopleAffected(selected.people);
    setLatitude(selected.lat ? String(selected.lat) : '');
    setLongitude(selected.lng ? String(selected.lng) : '');
    setIsPresetCoords(true);
    setGeocodeFeedback({
      type: 'info',
      text: `Loaded preset demo coordinates [${selected.lat}, ${selected.lng}]`,
    });
    setError(null);
  };

  const handleLocationChange = (e) => {
    const val = e.target.value;
    setLocation(val);
    if (isPresetCoords) {
      setLatitude('');
      setLongitude('');
      setIsPresetCoords(false);
      setGeocodeFeedback(null);
    }
  };

  const handleGeocodeAddress = async () => {
    if (!location.trim() || location.trim().length < 3) {
      setGeocodeFeedback({
        type: 'warn',
        text: 'Please enter a valid address before locating GPS coordinates.',
      });
      return;
    }

    setGeocoding(true);
    setGeocodeFeedback(null);
    try {
      const data = await api.geocodeAddress(location.trim());
      if (data.found && data.latitude !== null && data.longitude !== null) {
        setLatitude(String(data.latitude));
        setLongitude(String(data.longitude));
        setIsPresetCoords(false);
        setGeocodeFeedback({
          type: 'success',
          text: `Located: [${data.latitude}, ${data.longitude}] — ${data.display_name}`,
        });
      } else {
        setGeocodeFeedback({
          type: 'warn',
          text: 'OpenStreetMap could not find exact coordinates for this address. You may enter coordinates manually, or proceed with address only.',
        });
      }
    } catch (err) {
      setGeocodeFeedback({
        type: 'warn',
        text: `Geocoding request failed: ${err.message}`,
      });
    } finally {
      setGeocoding(false);
    }
  };

  const handleClearCoords = () => {
    setLatitude('');
    setLongitude('');
    setIsPresetCoords(false);
    setGeocodeFeedback(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!location.trim()) {
      setError('Please provide an incident location address or landmark.');
      return;
    }
    if (!description.trim() || description.trim().length < 5) {
      setError('Please provide an informative emergency description (at least 5 characters).');
      return;
    }
    if (peopleAffected < 0) {
      setError('People affected headcount cannot be negative.');
      return;
    }

    const payload = {
      incident_type: incidentType,
      location: location.trim(),
      description: description.trim(),
      people_affected: Number(peopleAffected),
      latitude: latitude ? parseFloat(latitude) : null,
      longitude: longitude ? parseFloat(longitude) : null,
    };

    if (payload.latitude !== null && isNaN(payload.latitude)) {
      setError('Latitude must be a valid decimal number.');
      return;
    }
    if (payload.longitude !== null && isNaN(payload.longitude)) {
      setError('Longitude must be a valid decimal number.');
      return;
    }

    setLoading(true);
    try {
      const created = await api.createIncident(payload);
      setSuccessData(created);
      setTimeout(() => {
        onSubmitSuccess(created);
        onClose();
      }, 1400);
    } catch (err) {
      setError(err.message || 'Failed to submit incident intake');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-content">
        {/* Header */}
        <div className="flex items-center justify-between" style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-subtle)', backgroundColor: '#ffffff' }}>
          <div className="flex items-center gap-2">
            <span className="pulse-indicator"></span>
            <h2 className="text-base font-bold text-main uppercase tracking-wider">
              Emergency Incident Intake
            </h2>
          </div>
          <button 
            type="button" 
            className="btn btn-secondary btn-sm"
            onClick={onClose}
            disabled={loading}
          >
            <X size={16} />
          </button>
        </div>

        {/* Success Alert */}
        {successData && (
          <div style={{ margin: '1rem 1.25rem 0', padding: '0.85rem 1rem', backgroundColor: '#f0fdf4', border: '1px solid #86efac', borderRadius: '6px' }}>
            <div className="flex items-center gap-2 text-low font-bold text-sm">
              <CheckCircle size={18} />
              <span>Incident Registered &amp; Triage Assessed: [{successData.urgency.toUpperCase()}]</span>
            </div>
            <p className="text-xs text-secondary mt-1 font-medium">
              Method: {successData.assessment_method === 'ai_generated' ? 'AI LLM Core' : 'Deterministic Rule-Based Heuristic'} &bull; 
              Coordinates: {successData.latitude && successData.longitude ? `Plotted at [${successData.latitude}, ${successData.longitude}]` : 'Address-only (GPS unplotted)'}
            </p>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div style={{ margin: '1rem 1.25rem 0', padding: '0.75rem 1rem', backgroundColor: '#fef2f2', border: '1px solid #fca5a5', borderRadius: '6px' }}>
            <div className="flex items-center gap-2 text-critical font-semibold text-xs">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ padding: '1.25rem', backgroundColor: '#ffffff' }}>
          {/* Quick Scenario Picker */}
          <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', backgroundColor: '#f8fafc', borderRadius: '6px', border: '1px dashed #cbd5e1' }}>
            <div className="flex items-center gap-2 mb-1.5 text-cyan font-bold text-xs uppercase tracking-wide">
              <Sparkles size={14} />
              <span>Quick Demo Test Scenarios</span>
            </div>
            <select className="select text-xs" onChange={handleSelectPreset} disabled={loading} style={{ backgroundColor: '#ffffff' }}>
              {PRESET_SCENARIOS.map((s, idx) => (
                <option key={idx} value={s.title}>{s.title}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3" style={{ marginBottom: '1rem' }}>
            <div>
              <label className="label">Incident Category *</label>
              <select 
                className="select"
                value={incidentType}
                onChange={(e) => setIncidentType(e.target.value)}
                disabled={loading}
              >
                <option value="Flood">Flood / Flash Flood</option>
                <option value="Structural Collapse">Structural Collapse</option>
                <option value="Fire">Fire / Wildfire</option>
                <option value="Chemical Spill">Chemical Spill / HAZMAT</option>
                <option value="Medical Emergency">Medical Emergency</option>
                <option value="Earthquake">Earthquake Tremor</option>
                <option value="Landslide">Landslide / Mudflow</option>
                <option value="Severe Storm">Severe Storm / Hurricane</option>
                <option value="Other">Other Distress Signal</option>
              </select>
            </div>

            <div>
              <label className="label">Estimated People Affected *</label>
              <input 
                type="number" 
                min="0"
                className="input"
                value={peopleAffected}
                onChange={(e) => setPeopleAffected(e.target.value)}
                disabled={loading}
                required
              />
            </div>
          </div>

          {/* Location with Geocode Button */}
          <div style={{ marginBottom: '1rem' }}>
            <div className="flex items-center justify-between mb-1">
              <label className="label" style={{ margin: 0 }}>Location Description / Address *</label>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '0.7rem', padding: '0.15rem 0.55rem' }}
                onClick={handleGeocodeAddress}
                disabled={geocoding || !location.trim()}
                title="Geocode address to GPS coordinates using OpenStreetMap Nominatim"
              >
                {geocoding ? <RefreshCw size={12} className="animate-spin text-cyan" /> : <Search size={12} className="text-cyan" />}
                <span>{geocoding ? 'Locating...' : 'Locate on Map'}</span>
              </button>
            </div>
            <input 
              type="text" 
              className="input"
              placeholder="e.g. Pakala, Tirupati, Andhra Pradesh, India or Mission & 8th St"
              value={location}
              onChange={handleLocationChange}
              disabled={loading}
              required
            />

            {/* Geocode Feedback Status */}
            {geocodeFeedback && (
              <div style={{
                marginTop: '0.45rem',
                padding: '0.5rem 0.75rem',
                borderRadius: '6px',
                fontSize: '0.75rem',
                backgroundColor: geocodeFeedback.type === 'success' ? '#f0fdf4' : geocodeFeedback.type === 'warn' ? '#fffbeb' : '#f0f9ff',
                border: `1px solid ${geocodeFeedback.type === 'success' ? '#86efac' : geocodeFeedback.type === 'warn' ? '#fcd34d' : '#bae6fd'}`,
                color: geocodeFeedback.type === 'success' ? '#15803d' : geocodeFeedback.type === 'warn' ? '#b45309' : '#0369a1',
              }}>
                {geocodeFeedback.text}
              </div>
            )}
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label className="label">Emergency Narrative / Signal Transcript *</label>
            <textarea 
              className="textarea" 
              rows="4"
              placeholder="Describe situation, life threats (e.g., trapped individuals, rising water, fire spreading), physical hazards..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={loading}
              required
            ></textarea>
          </div>

          {/* Coordinates Inputs with Clear action */}
          <div style={{ marginBottom: '1.25rem', backgroundColor: '#f8fafc', padding: '0.85rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-secondary flex items-center gap-1.5 uppercase">
                <MapPin size={13} className="text-cyan" />
                <span>GPS Coordinates (Optional — Auto-Geocoded If Blank)</span>
              </span>
              {(latitude || longitude) && (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ fontSize: '0.68rem', padding: '0.15rem 0.45rem' }}
                  onClick={handleClearCoords}
                >
                  Clear GPS
                </button>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label text-xs">Latitude</label>
                <input 
                  type="text" 
                  className="input mono text-xs"
                  placeholder="e.g. 13.4490"
                  value={latitude}
                  onChange={(e) => {
                    setLatitude(e.target.value);
                    setIsPresetCoords(false);
                  }}
                  disabled={loading}
                />
              </div>
              <div>
                <label className="label text-xs">Longitude</label>
                <input 
                  type="text" 
                  className="input mono text-xs"
                  placeholder="e.g. 79.1149"
                  value={longitude}
                  onChange={(e) => {
                    setLongitude(e.target.value);
                    setIsPresetCoords(false);
                  }}
                  disabled={loading}
                />
              </div>
            </div>
            <p className="text-xs text-muted mt-1.5 font-medium" style={{ fontSize: '0.7rem' }}>
              💡 If left blank, RESQ-OS will automatically attempt to geocode the address above. If coordinates cannot be found, the incident will be saved with address-only and clearly marked on the dashboard.
            </p>
          </div>

          {/* Action Footer */}
          <div className="flex items-center justify-end gap-3 pt-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
            <button 
              type="button" 
              className="btn btn-secondary" 
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              className="btn btn-primary"
              disabled={loading}
              style={{ padding: '0.45rem 1rem' }}
            >
              <Send size={15} />
              <span>{loading ? 'Evaluating & Submitting...' : 'Dispatch Signal to Triage'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
