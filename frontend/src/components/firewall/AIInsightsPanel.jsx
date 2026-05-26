import React from 'react';
import { Brain, Sparkles, Lightbulb, ArrowLeftCircle } from 'lucide-react';

/**
 * 🤖 AI Insights Panel
 * يعرض توصيات الذكاء الاصطناعي (rules + AI provider).
 */

const SEV_COLORS = {
  critical: 'border-rose-500 bg-rose-50 dark:bg-rose-950/40',
  high: 'border-orange-500 bg-orange-50 dark:bg-orange-950/40',
  medium: 'border-amber-500 bg-amber-50 dark:bg-amber-950/40',
  info: 'border-sky-500 bg-sky-50 dark:bg-sky-950/40',
};

export const AIInsightsPanel = ({ insights = [], aiEnabled = false, loading = false }) => {
  return (
    <div data-testid="firewall-ai-insights-panel" className="bg-gradient-to-br from-indigo-900/95 to-purple-900/95 dark:from-indigo-950 dark:to-purple-950 rounded-2xl border-2 border-indigo-600 shadow-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-indigo-600/30">
            <Brain className="text-indigo-200" size={22} />
          </div>
          <div>
            <h3 className="text-base font-extrabold text-white">تحليلات المساعد المالي</h3>
            <p className="text-[11px] text-indigo-200/80">{aiEnabled ? 'مدعوم بـ AI + قواعد محلية' : 'قواعد محلية (AI غير متاح)'}</p>
          </div>
        </div>
        <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold ${aiEnabled ? 'bg-emerald-500/30 text-emerald-100 border border-emerald-400/40' : 'bg-amber-500/30 text-amber-100 border border-amber-400/40'}`}>
          {aiEnabled ? <><Sparkles size={10} className="inline ml-1" />AI نشط</> : 'محرك قواعد فقط'}
        </span>
      </div>

      {loading ? (
        <div className="text-indigo-200 text-sm py-6 text-center">جاري التحليل…</div>
      ) : insights.length === 0 ? (
        <div className="text-indigo-200 text-sm py-6 text-center">لا توجد توصيات حالياً.</div>
      ) : (
        <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1" data-testid="firewall-ai-insights-list">
          {insights.map((ins, i) => (
            <div
              key={i}
              data-testid={`firewall-ai-insight-${i}`}
              className={`border-r-4 ${SEV_COLORS[ins.severity] || SEV_COLORS.info} rounded-lg p-3 bg-white/95 dark:bg-slate-800/95 shadow-sm`}
            >
              <div className="flex items-start gap-2">
                <Lightbulb className="text-amber-500 flex-shrink-0 mt-0.5" size={16} />
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <h4 className="font-extrabold text-sm text-slate-900 dark:text-slate-50">{ins.title}</h4>
                    {ins.source === 'ai' && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-600 text-white font-bold">AI</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-700 dark:text-slate-200 leading-relaxed">{ins.body}</p>
                  {ins.action && (
                    <p className="text-[11px] mt-2 text-emerald-700 dark:text-emerald-300 flex items-start gap-1 font-semibold">
                      <ArrowLeftCircle size={13} className="flex-shrink-0 mt-0.5" />
                      <span>{ins.action}</span>
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AIInsightsPanel;
