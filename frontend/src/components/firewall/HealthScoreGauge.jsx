import React from 'react';

/**
 * 🛡️ Health Score Gauge
 * مؤشر دائري للصحة المالية 0-100 بألوان متدرجة.
 */
export const HealthScoreGauge = ({ score = 0, status = '', color = 'amber', breakdown = {} }) => {
  const percentage = Math.max(0, Math.min(100, score));
  const radius = 90;
  const stroke = 14;
  const circumference = 2 * Math.PI * radius;
  const dash = (percentage / 100) * circumference;

  const colorMap = {
    emerald: { stroke: '#10b981', glow: 'shadow-emerald-500/40', text: 'text-emerald-400' },
    lime: { stroke: '#84cc16', glow: 'shadow-lime-500/40', text: 'text-lime-400' },
    amber: { stroke: '#f59e0b', glow: 'shadow-amber-500/40', text: 'text-amber-400' },
    orange: { stroke: '#f97316', glow: 'shadow-orange-500/40', text: 'text-orange-400' },
    rose: { stroke: '#f43f5e', glow: 'shadow-rose-500/40', text: 'text-rose-400' },
  };
  const c = colorMap[color] || colorMap.amber;

  return (
    <div
      data-testid="firewall-health-score"
      className={`relative flex flex-col items-center justify-center bg-gradient-to-br from-slate-900/95 to-slate-800/95 dark:from-slate-900 dark:to-slate-800 rounded-2xl border-2 border-slate-700 dark:border-slate-600 p-6 shadow-2xl ${c.glow}`}
    >
      <svg width={220} height={220} className="-rotate-90">
        <circle
          cx={110}
          cy={110}
          r={radius}
          fill="none"
          stroke="rgba(100, 116, 139, 0.2)"
          strokeWidth={stroke}
        />
        <circle
          cx={110}
          cy={110}
          r={radius}
          fill="none"
          stroke={c.stroke}
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${circumference}`}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 1.2s ease-out' }}
        />
      </svg>
      <div className="absolute flex flex-col items-center pointer-events-none">
        <div className={`text-6xl font-black ${c.text}`} data-testid="firewall-health-score-value">{percentage}</div>
        <div className="text-slate-400 text-xs font-medium mt-1">من 100</div>
        <div className={`mt-2 px-4 py-1 rounded-full text-sm font-bold ${c.text} bg-slate-800/80 border border-slate-700`} data-testid="firewall-health-score-status">
          {status}
        </div>
      </div>
      {/* breakdown chips */}
      {Object.keys(breakdown).length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-1.5 w-full text-[10px]" data-testid="firewall-health-breakdown">
          {Object.entries(breakdown).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between bg-slate-800/60 px-2 py-1 rounded border border-slate-700/60">
              <span className="text-slate-400 truncate">{labelize(k)}</span>
              <span className={`font-bold ${v >= 8 ? 'text-emerald-400' : v >= 4 ? 'text-amber-400' : 'text-rose-400'}`}>{v}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const labelize = (key) => {
  const map = {
    balance_integrity: 'توازن القيود',
    no_duplicates: 'لا تكرار',
    consistency: 'اتساق البيانات',
    no_anomalies: 'لا شذوذ',
    data_integrity: 'نزاهة البيانات',
    positive_cash_flow: 'تدفق إيجابي',
    audit_coverage: 'تغطية التدقيق',
    overdue_control: 'متابعة المتأخرات',
  };
  return map[key] || key;
};

export default HealthScoreGauge;
