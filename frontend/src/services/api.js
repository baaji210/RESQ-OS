/**
 * Dynamic resolution of Backend API Base URL.
 * - In local dev (or reverse proxy): defaults to relative '/api', proxied by Vite to http://localhost:8000.
 * - In production: reads import.meta.env.VITE_API_BASE_URL.
 *   Gracefully handles variations with or without '/api' and with or without trailing slash.
 */
function resolveApiBase() {
  const envUrl = (import.meta.env.VITE_API_BASE_URL || '').trim();
  if (!envUrl) {
    return '/api';
  }
  const clean = envUrl.replace(/\/+$/, '');
  return clean.endsWith('/api') ? clean : `${clean}/api`;
}

export const API_BASE = resolveApiBase();

/**
 * Handle API responses with proper error extraction
 */
async function handleResponse(response) {
  if (!response.ok) {
    let errorMsg = `Server error (${response.status})`;
    try {
      const errData = await response.json();
      errorMsg = errData.detail || errData.message || errorMsg;
    } catch {
      // ignore json parse error
    }
    throw new Error(errorMsg);
  }
  return response.json();
}

export const api = {
  // System & Health
  async getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    return handleResponse(res);
  },

  async getDatabaseStatus(force = false) {
    const res = await fetch(`${API_BASE}/database/status${force ? '?force=true' : ''}`);
    return handleResponse(res);
  },

  async migrateToAtlas(confirm = false) {
    const res = await fetch(`${API_BASE}/database/migrate-to-atlas?confirm=${confirm ? 'true' : 'false'}`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  async getDashboardStats() {
    const res = await fetch(`${API_BASE}/dashboard/stats`);
    return handleResponse(res);
  },

  // Incidents
  async getIncidents({ status = 'All', urgency = 'All', search = '' } = {}) {
    const params = new URLSearchParams();
    if (status && status !== 'All') params.append('status', status);
    if (urgency && urgency !== 'All') params.append('urgency', urgency);
    if (search && search.trim()) params.append('search', search.trim());

    const url = `${API_BASE}/incidents${params.toString() ? '?' + params.toString() : ''}`;
    const res = await fetch(url);
    return handleResponse(res);
  },

  async getIncidentById(id) {
    const res = await fetch(`${API_BASE}/incidents/${id}`);
    return handleResponse(res);
  },

  async getPrioritizedIncidents() {
    const res = await fetch(`${API_BASE}/incidents/prioritize`);
    return handleResponse(res);
  },

  async geocodeAddress(query) {
    const res = await fetch(`${API_BASE}/incidents/geocode?q=${encodeURIComponent(query)}`);
    return handleResponse(res);
  },

  async createIncident(incidentData) {
    const res = await fetch(`${API_BASE}/incidents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(incidentData),
    });
    return handleResponse(res);
  },

  async updateIncidentStatus(incidentId, status, dispatcherNotes = '', dispatcherActor = 'Dispatcher Ops') {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status,
        dispatcher_notes: dispatcherNotes,
        dispatcher_actor: dispatcherActor,
      }),
    });
    return handleResponse(res);
  },

  async overrideUrgency(incidentId, urgencyOverride, reason = '', dispatcherActor = 'Dispatcher Ops') {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/urgency`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        urgency_override: urgencyOverride,
        reason,
        dispatcher_actor: dispatcherActor,
      }),
    });
    return handleResponse(res);
  },

  async resetDemoData() {
    const res = await fetch(`${API_BASE}/incidents/reset-demo`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  // Resources & Recommendations
  async getResources({ availability = 'All', resource_type = 'All' } = {}) {
    const params = new URLSearchParams();
    if (availability && availability !== 'All') params.append('availability', availability);
    if (resource_type && resource_type !== 'All') params.append('resource_type', resource_type);

    const url = `${API_BASE}/resources${params.toString() ? '?' + params.toString() : ''}`;
    const res = await fetch(url);
    return handleResponse(res);
  },

  async getRecommendations(incidentId) {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/recommendations`);
    return handleResponse(res);
  },

  async assignResource(incidentId, resourceId, notes = '', actor = 'Dispatcher Lead', reassign = false) {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/assignments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resource_id: resourceId,
        dispatcher_notes: notes,
        dispatcher_actor: actor,
        reassign,
      }),
    });
    return handleResponse(res);
  },

  async unassignResource(incidentId) {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/unassign`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  // Rescue Team Terminal (MDT)
  async getTeamMission(resourceId) {
    const res = await fetch(`${API_BASE}/resources/${resourceId}/mission`);
    return handleResponse(res);
  },

  async updateTeamMissionStatus(resourceId, status, notes = '') {
    const res = await fetch(`${API_BASE}/resources/${resourceId}/mission-status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, notes }),
    });
    return handleResponse(res);
  },
};
