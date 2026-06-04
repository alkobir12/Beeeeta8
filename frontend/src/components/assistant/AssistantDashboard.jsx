import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Activity, AlertTriangle, Car, Coins, Package, ShieldAlert, TrendingUp, Users } from 'lucide-react';

const API_URL = `${process.env.REACT_APP_BACKEND_URL}/api`;
const WORKSHOP_ID = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';

const PANEL_META = {
  active_visits: { Icon: Car, color: 'from-emerald-500 to-teal-500' },
  health_score: { Icon: ShieldAlert, color: 'from-indigo-500 to-blue-500' },
  total_ar: { Icon: Users, color: 'from-amber-500 to-orange-500' },
  total_ap: { Icon: Users, color: 'from-fuchsia-500 to-purple-500' },
  cash_flow_30d: { Icon: TrendingUp, color: 'from-cyan-500 to-sky-500' },
  critical_findings: { Icon: AlertTriangle, color: 'from-rose-500 to-red-500' },
  low_stock: { Icon: Package, color: 'from-orange-500 to-amber-500' },
  ops_with_warnings: { Icon: Activity, color: 'from-yellow-500 to-amber-500' },
};

function formatValue(value, kind) {
  if (value === null || value === undefined) return '—';
  if (kind === 'currency') {
    try {
      const v = Number(value);
      return `${v.toLocaleString('ar-SA', { maximumFractionDigits: 0 })} ر.س`;
    } catch (e) { return String(value); }
  }
  if (kind === 'score') return `${value}/100`;
  return String(value);
}

/**
 * 📊 AssistantDashboard — Phase 3B opening panel rendered when the drawer
 * opens with no prior messages. Shows 8 live KPIs at-a-glance.
 */
export const AssistantDashboard = ({ onAskMore }) => {
  const [panels, setPanels] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API_URL}/assistant/dashboard`, { params: { workshop_id: WORKSHOP_ID }, timeout: 25000 });
        if (!cancelled && res.data?.success) {
          setPanels(res.data.data?.panels || []);
        }
      } catch (e) { /* fail silent — panels stay empty */ }
      if (!cancelled) setLoading(false);
    })();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-2 my-3" data-testid="assistant-dashboard-loading">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="rounded-lg bg-slate-100 dark:bg-slate-800 p-3 animate-pulse h-16" />
        ))}
      </div>
    );
  }

  if (panels.length === 0) {
    return null;
  }

  return (
    <div className="my-3 space-y-2" data-testid="assistant-dashboard">
      <div className="text-[11px] font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
        <Coins size={12} className="text-amber-500" />
        <span>لوحة الورشة الآن</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {panels.map((p) => {
          const meta = PANEL_META[p.id] || { Icon: Activity, color: 'from-slate-500 to-slate-600' };
          const Icon = meta.Icon;
          return (
            <button
              key={p.id}
              data-testid={`dashboard-panel-${p.id}`}
              onClick={() => onAskMore?.(p)}
              className={`text-right rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-indigo-400 transition-colors overflow-hidden`}
            >
              <div className={`bg-gradient-to-l ${meta.color} h-1 w-full`} />
              <div className="p-2">
                <div className="flex items-center gap-1.5 text-[9px] text-slate-500 dark:text-slate-400 mb-0.5">
                  <Icon size={10} />
                  <span className="truncate">{p.label}</span>
                </div>
                <div className="text-[14px] font-extrabold text-slate-900 dark:text-slate-100">
                  {formatValue(p.value, p.kind)}
                </div>
                {p.secondary && <div className="text-[9px] text-slate-500 dark:text-slate-400 mt-0.5">{p.secondary}</div>}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default AssistantDashboard;
