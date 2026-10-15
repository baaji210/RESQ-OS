import React, { useState, useEffect } from 'react';
import { 
  ShieldAlert, 
  Radio, 
  RotateCcw, 
  PlusCircle, 
  Flame, 
  Truck, 
  CheckCircle2, 
  AlertTriangle,
  RefreshCw,
  Database,
  CheckCircle,
  WifiOff,
  Activity,
  Layers
} from 'lucide-react';

export default function Header({ 
  stats, 
  onOpenNewIncident, 
  onResetDemo, 
  onRefresh, 
  loading,
  health
}) {
  const [timeStr, setTimeStr] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toTimeString().split(' ')[0] + ' UTC' + (now.getTimezoneOffset() > 0 ? '-' : '+') + Math.abs(now.getTimezoneOffset() / 60));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const dbState = health?.database;

  return (
    <header className="tactical-header">
      {/* Top Bar */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        {/* Brand & Tagline */}
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center shrink-0" style={{
            width: '40px', 
            height: '40px', 
            backgroundColor: '#dc2626', 
            borderRadius: '8px', 
            boxShadow: '0 2px 8px rgba(220, 38, 38, 0.3)'
          }}>
            <ShieldAlert size={24} color="#ffffff" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-extrabold tracking-tight text-main">
                RESQ<span className="text-cyan">-OS</span>
              </h1>
              <span className="badge badge-sim">
                SIMULATION MODE
              </span>
              <span className="badge badge-rule text-xs">
                {health?.triage_engine?.active_provider?.includes('OpenAI') ? 'AI ENGINE ACTIVE' : 'RULE-BASED TRIAGE'}
              </span>

              {/* Database Connection State */}
              {dbState?.is_mongodb_connected ? (
                <span 
                  className="badge text-xs flex items-center gap-1.5" 
                  style={{ backgroundColor: '#f0fdf4', color: '#15803d', border: '1px solid #86efac' }}
                  title={`MongoDB Atlas Connected: ${dbState.database_name}.${dbState.collection || 'incidents'} | Latency: ${dbState.latency_ms || 0}ms`}
                >
                  <span className="pulse-indicator green" style={{ width: '6px', height: '6px' }}></span>
                  <span className="font-bold">ATLAS CONNECTED ({dbState.database_name})</span>
                  {dbState.latency_ms && <span className="opacity-75 font-mono text-2xs">({dbState.latency_ms}ms)</span>}
                </span>
              ) : dbState?.status === 'fallback_sqlite' ? (
                <span 
                  className="badge text-xs flex items-center gap-1.5" 
                  style={{ backgroundColor: '#fffbeb', color: '#b45309', border: '1px solid #fcd34d' }}
                  title={`MongoDB Atlas Unavailable: ${dbState.error || 'Connection Error'}. Using local SQLite fallback (resq_os.db).`}
                >
                  <WifiOff size={11} />
                  <span>ATLAS DISCONNECTED (SQLITE FALLBACK)</span>
                </span>
              ) : (
                <span 
                  className="badge text-xs flex items-center gap-1.5" 
                  style={{ backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1' }}
                  title="Local SQLite storage active (resq_os.db). Set MONGODB_URI in backend/.env to connect MongoDB Atlas."
                >
                  <Database size={11} />
                  <span>DATABASE: SQLITE (LOCAL)</span>
                </span>
              )}
            </div>
            <p className="text-xs text-secondary font-medium tracking-normal mt-0.5">
              Autonomous AI Disaster Response &amp; Rescue Coordination System &bull; <strong className="text-cyan">Every Signal Matters. Every Response Counts.</strong>
            </p>
          </div>
        </div>

        {/* Live Clock & Action Controls */}
        <div className="flex items-center gap-2.5 flex-wrap">
          <div className="flex items-center gap-2 px-3 py-1.5" style={{ 
            backgroundColor: '#f8fafc', 
            border: '1px solid #e2e8f0', 
            borderRadius: '6px',
            boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
          }}>
            <span className="pulse-indicator green"></span>
            <span className="text-xs mono text-cyan font-bold">{timeStr}</span>
            <span className="text-xs text-muted font-medium">| OPS LIVE</span>
          </div>

          <button 
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onRefresh}
            disabled={loading}
            title="Refresh dashboard telemetry"
          >
            <RefreshCw size={14} className={loading ? "animate-spin text-cyan" : "text-secondary"} />
            <span>Sync</span>
          </button>

          <button 
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onResetDemo}
            disabled={loading}
            title="Reload fictional demo data"
          >
            <RotateCcw size={14} className="text-secondary" />
            <span>Reset Demo</span>
          </button>

          <button 
            type="button"
            className="btn btn-primary btn-sm"
            onClick={onOpenNewIncident}
            style={{ padding: '0.4rem 0.85rem' }}
          >
            <PlusCircle size={15} />
            <span>Report Incident</span>
          </button>
        </div>
      </div>

      {/* Metrics Bar - 6 Compact, Scannable Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2.5" style={{ marginTop: '0.85rem' }}>
        {/* Metric 1: Total Incidents */}
        <div className="card flex items-center justify-between" style={{ padding: '0.6rem 0.85rem' }}>
          <div>
            <div className="text-2xs text-muted font-bold uppercase tracking-wider">Total Incidents</div>
            <div className="text-xl font-bold mono text-main leading-tight mt-0.5">
              {stats?.total_incidents ?? '—'}
            </div>
          </div>
          <div className="p-2 rounded-md" style={{ backgroundColor: '#f0f9ff' }}>
            <Radio size={18} className="text-cyan" />
          </div>
        </div>

        {/* Metric 2: Critical / High */}
        <div 
          className="card flex items-center justify-between" 
          style={{ 
            padding: '0.6rem 0.85rem',
            borderLeft: stats?.critical_high_count > 0 ? '3px solid #dc2626' : undefined,
            backgroundColor: stats?.critical_high_count > 0 ? '#fffcfc' : undefined
          }}
        >
          <div>
            <div className="text-2xs text-muted font-bold uppercase tracking-wider">Critical / High</div>
            <div className="text-xl font-bold mono text-critical leading-tight mt-0.5">
              {stats?.critical_high_count ?? '—'}
            </div>
          </div>
          <div className="p-2 rounded-md" style={{ backgroundColor: '#fef2f2' }}>
            <Flame size={18} className="text-critical" />
          </div>
        </div>

        {/* Metric 3: Active Missions */}
        <div className="card flex items-center justify-between" style={{ padding: '0.6rem 0.85rem' }}>
          <div>
            <div className="text-2xs text-muted font-bold uppercase tracking-wider">Active Missions</div>
            <div className="text-xl font-bold mono text-high leading-tight mt-0.5">
              {stats?.active_incidents ?? '—'}
            </div>
          </div>
          <div className="p-2 rounded-md" style={{ backgroundColor: '#fff7ed' }}>
            <AlertTriangle size={18} className="text-high" />
          </div>
        </div>

        {/* Metric 4: Resolved Incidents */}
        <div className="card flex items-center justify-between" style={{ padding: '0.6rem 0.85rem' }}>
          <div>
            <div className="text-2xs text-muted font-bold uppercase tracking-wider">Resolved</div>
            <div className="text-xl font-bold mono text-low leading-tight mt-0.5">
              {stats?.resolved_incidents ?? '—'}
            </div>
          </div>
          <div className="p-2 rounded-md" style={{ backgroundColor: '#f0fdf4' }}>
            <CheckCircle2 size={18} className="text-low" />
          </div>
        </div>

        {/* Metric 5: Total Resources */}
        <div className="card flex items-center justify-between" style={{ padding: '0.6rem 0.85rem' }}>
          <div>
            <div className="text-2xs text-muted font-bold uppercase tracking-wider">Total Fleet</div>
            <div className="text-xl font-bold mono text-main leading-tight mt-0.5">
              {stats?.total_resources ?? '—'}
            </div>
          </div>
          <div className="p-2 rounded-md" style={{ backgroundColor: '#f1f5f9' }}>
            <Layers size={18} className="text-secondary" />
          </div>
        </div>

        {/* Metric 6: Available Resources */}
        <div className="card flex items-center justify-between" style={{ padding: '0.6rem 0.85rem' }}>
          <div>
            <div className="text-2xs text-muted font-bold uppercase tracking-wider">Available Units</div>
            <div className="text-xl font-bold mono text-cyan leading-tight mt-0.5">
              {stats?.available_resources ?? '—'}
              <span className="text-xs text-muted font-normal ml-1">/ {stats?.total_resources ?? '—'}</span>
            </div>
          </div>
          <div className="p-2 rounded-md" style={{ backgroundColor: '#f0fdf4' }}>
            <Truck size={18} className="text-low" />
          </div>
        </div>
      </div>
    </header>
  );
}
