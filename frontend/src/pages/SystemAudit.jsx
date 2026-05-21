import React, { useState } from 'react';
import { Shield, RefreshCw, CheckCircle, AlertTriangle, XCircle, FileText, Download, Activity, Brain, Send, Loader2 } from 'lucide-react';
import FinancialCard from '../components/FinancialCard';
import { useTheme } from '../contexts/ThemeContext';
import { aiAPI } from '../services/api';
import { resolveBackendBase } from '../utils/backendBase';

const SystemAudit = () => {
  const { themeName } = useTheme();
  const [auditReport, setAuditReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [financeBotLoading, setFinanceBotLoading] = useState(false);
  const [financeBotResponse, setFinanceBotResponse] = useState('');
  const [financeBotError, setFinanceBotError] = useState('');

  const workshopId = process.env.REACT_APP_WORKSHOP_ID;

  const runAudit = async () => {
    try {
      setLoading(true);
      const API_URL = `${resolveBackendBase()}/api`;
      
      const response = await fetch(`${API_URL}/finance/audit-system?workshop_id=${workshopId}`, {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.success) {
        setAuditReport(data.data);
      } else {
        alert('❌ فشل التدقيق: ' + data.message);
      }
    } catch (error) {
      console.error('Error running audit:', error);
      alert('❌ حدث خطأ أثناء التدقيق');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeWithFinanceBot = async () => {
    if (!auditReport) return;

    setFinanceBotError('');
    setFinanceBotLoading(true);

    try {
      const summaryParts = [];

      if (auditReport.summary) {
        summaryParts.push(`ملخص التدقيق:\n${auditReport.summary}`);
      }

      if (auditReport.details?.balance_sheet_check) {
        summaryParts.push(
          `فحص معادلة المحاسبة: ${auditReport.details.balance_sheet_check.message}`
        );
      }

      if (auditReport.details?.consistency_analysis) {
        const issues = auditReport.details.consistency_analysis.issues || [];
        const warnings = auditReport.details.consistency_analysis.warnings || [];
        if (issues.length || warnings.length) {
          summaryParts.push(
            `قضايا الاتساق:\n- مشكلات: ${issues.join(' | ') || 'لا يوجد'}\n- تحذيرات: ${warnings.join(' | ') || 'لا يوجد'}`
          );
        }
      }

      if (auditReport.corrections_needed?.length) {
        summaryParts.push(
          'تصحيحات مطلوبة:\n' +
          auditReport.corrections_needed
            .map((c, idx) => `${idx + 1}- ${c.issue} | تصحيح مقترح: ${c.correction || '-'} | اقتراح: ${c.suggestion || '-'}`)
            .join('\n')
        );
      }

      const contextText = summaryParts.join('\n\n');
      const message =
        'أرغب في تفسير تقرير التدقيق أعلاه، وذكر الأخطاء المحاسبية المحتملة، مستوى خطورتها، والتوصيات العملية لتحسين دقة السجلات وتقليل المخاطر.';

      const payload = {
        message: `${contextText}\n\nسؤال المحاسب:\n${message}`,
        workshop_id: workshopId,
      };

      const res = await aiAPI.financeBotChat(payload);
      setFinanceBotResponse(res.data?.response || 'تعذر الحصول على تحليل من البوت المالي.');
    } catch (err) {
      console.error('Finance bot audit analysis error:', err);
      setFinanceBotError('تعذر الاتصال بالمحاسب المالي لتحليل تقرير التدقيق.');
    } finally {
      setFinanceBotLoading(false);
    }
  };

  const getHealthColor = (score) => {
    if (score >= 90) return 'success';
    if (score >= 70) return 'warning';
    return 'danger';
  };

  return (
    <div className="container mx-auto p-6 max-w-7xl" dir="rtl" style={{
      backgroundColor: 'var(--bg-primary)',
      minHeight: '100vh'
    }}>
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3" style={{ color: 'var(--text-primary)' }}>
            <Shield size={32} className="text-blue-500" />
            تدقيق النظام المحاسبي
          </h1>
          <p className="mt-2" style={{ color: 'var(--text-secondary)' }}>
            فحص شامل للنظام المحاسبي واكتشاف المشكلات والتوصيات
          </p>
        </div>

        <button
          onClick={runAudit}
          disabled={loading}
          className="flex items-center gap-2 px-6 py-3 rounded-xl font-medium text-white transition-all"
          style={{ 
            background: loading ? '#6b7280' : 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
            boxShadow: '0 4px 14px rgba(37, 99, 235, 0.25)',
            opacity: loading ? 0.7 : 1
          }}
        >
          {loading ? (
            <>
              <RefreshCw size={20} className="animate-spin" />
              <span>جاري التدقيق...</span>
            </>
          ) : (
            <>
              <Activity size={20} />
              <span>تشغيل التدقيق</span>
            </>
          )}
        </button>
      </div>

      {!auditReport && !loading && (
        <div className="space-y-8">
          {/* معلومات التدقيق */}
          <div className="text-center py-12">
            <Shield size={64} className="mx-auto mb-4 text-slate-400" />
            <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
              ابدأ التدقيق الشامل للنظام المحاسبي
            </h2>
            <p className="mb-6 max-w-2xl mx-auto" style={{ color: 'var(--text-secondary)' }}>
              سيتم فحص معادلة المحاسبة، اتساق القوائم المالية، واكتشاف المشكلات المحتملة تلقائياً
            </p>
            <button
              onClick={runAudit}
              className="px-8 py-3 rounded-xl font-semibold text-white"
              style={{ 
                background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                boxShadow: '0 4px 14px rgba(37, 99, 235, 0.25)'
              }}
            >
              🔍 تشغيل التدقيق الآن
            </button>
          </div>

          {/* شرح ما سيتم فحصه */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-2xl p-6"
              style={{
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-color)'
              }}
            >
              <h3 className="text-xl font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <CheckCircle size={24} className="text-emerald-500" />
                ماذا سيتم فحصه؟
              </h3>
              <ul className="space-y-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
                <li className="flex items-start gap-2">
                  <span className="text-blue-400 font-bold">✓</span>
                  <span><strong>معادلة المحاسبة:</strong> التأكد من أن الأصول = الالتزامات + حقوق الملكية</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-400 font-bold">✓</span>
                  <span><strong>اتساق القوائم:</strong> التحقق من تطابق البيانات بين القوائم المالية</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-400 font-bold">✓</span>
                  <span><strong>الأنماط غير العادية:</strong> اكتشاف هامش ربح غير واقعي، مصروفات ناقصة</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-400 font-bold">✓</span>
                  <span><strong>توازن القيود:</strong> التأكد من أن كل قيد محاسبي متوازن</span>
                </li>
              </ul>
            </div>

            <div className="rounded-2xl p-6"
              style={{
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-color)'
              }}
            >
              <h3 className="text-xl font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <FileText size={24} className="text-blue-500" />
                مثال على البيانات المطلوبة
              </h3>
              <div className="text-xs font-mono p-4 rounded-lg overflow-auto max-h-64"
                style={{
                  backgroundColor: 'rgba(15,23,42,0.5)',
                  border: '1px solid rgba(100,116,139,0.2)'
                }}
              >
                <pre className="text-slate-300">{`{
  "balance_sheet": {
    "assets": 350000,
    "liabilities": 120000,
    "equity": 230000
  },
  "income_statement": {
    "revenue": 67800,
    "expenses": 18000,
    "net_profit": 49800
  },
  "cash_flow": {
    "operating": 45000,
    "investing": -10000,
    "financing": 5000
  }
}`}</pre>
              </div>
            </div>
          </div>
        </div>
      )}

      {auditReport && (
        <div className="space-y-6">
          {/* Health Score Card */}
          <FinancialCard
            title={`${auditReport.health_score}/100`}
            subtitle="درجة صحة النظام"
            icon={Shield}
            variant={getHealthColor(auditReport.health_score)}
            expandable={false}
            details={[
              { label: 'الحكم النهائي', value: auditReport.summary?.final_verdict || '-' },
              { label: 'عدد المشكلات', value: auditReport.summary?.total_issues || 0, valueColor: 'text-red-400' },
              { label: 'التصحيحات المطلوبة', value: auditReport.summary?.corrections_needed || 0, valueColor: 'text-yellow-400' }
            ]}
          />

          {/* Balance Sheet Check */}
          {auditReport.details?.balance_sheet_check && (
            <div className="rounded-2xl p-6"
              style={{
                backgroundColor: 'var(--bg-card)',
                border: `2px solid ${auditReport.details.balance_sheet_check.result ? '#10b981' : '#ef4444'}`
              }}
            >
              <div className="flex items-center gap-3 mb-4">
                {auditReport.details.balance_sheet_check.result ? (
                  <CheckCircle size={32} className="text-emerald-400" />
                ) : (
                  <XCircle size={32} className="text-red-400" />
                )}
                <div>
                  <h3 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                    فحص معادلة المحاسبة
                  </h3>
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    {auditReport.details.balance_sheet_check.message}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Consistency Analysis */}
          {auditReport.details?.consistency_analysis && (
            <div>
              <h2 className="text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
                تحليل اتساق القوائم المالية
              </h2>
              
              {auditReport.details.consistency_analysis.issues?.length > 0 && (
                <div className="space-y-3 mb-4">
                  {auditReport.details.consistency_analysis.issues.map((issue, idx) => (
                    <div
                      key={`issue-${idx}-${String(issue).slice(0, 24)}`}
                      className="flex items-start gap-3 p-4 rounded-xl"
                      style={{
                        backgroundColor: 'rgba(239,68,68,0.1)',
                        border: '1px solid rgba(239,68,68,0.3)'
                      }}
                    >
                      <XCircle size={20} className="text-red-400 flex-shrink-0 mt-0.5" />
                      <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{issue}</span>
                    </div>
                  ))}
                </div>
              )}

              {auditReport.details.consistency_analysis.warnings?.length > 0 && (
                <div className="space-y-3">
                  {auditReport.details.consistency_analysis.warnings.map((warning, idx) => (
                    <div
                      key={`warning-${idx}-${String(warning).slice(0, 24)}`}
                      className="flex items-start gap-3 p-4 rounded-xl"
                      style={{
                        backgroundColor: 'rgba(251,146,60,0.1)',
                        border: '1px solid rgba(251,146,60,0.3)'
                      }}
                    >
                      <AlertTriangle size={20} className="text-orange-400 flex-shrink-0 mt-0.5" />
                      <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{warning}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Corrections Needed */}
          {auditReport.corrections_needed?.length > 0 && (
            <div>
              <h2 className="text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
                التصحيحات المطلوبة
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {auditReport.corrections_needed.map((correction, idx) => (
                  <div
                    key={correction?.id ?? `corr-${idx}`}
                    className="rounded-xl p-4"
                    style={{
                      backgroundColor: 'var(--bg-card)',
                      border: '1px solid var(--border-color)'
                    }}
                  >
                    <h3 className="font-bold text-lg mb-2 text-red-400">{correction.issue}</h3>
                    {correction.correction && (
                      <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>
                        {correction.correction}
                      </p>
                    )}
                    {correction.suggestion && (
                      <p className="text-sm font-semibold text-blue-400">
                        💡 {correction.suggestion}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Audit Log */}
          {auditReport.audit_log?.length > 0 && (
            <div>
              <h2 className="text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
                سجل التدقيق
              </h2>
              <div className="rounded-xl p-4 max-h-96 overflow-y-auto"
                style={{
                  backgroundColor: 'var(--bg-card)',
                  border: '1px solid var(--border-color)'
                }}
              >
                {auditReport.audit_log.map((log, idx) => (
                  <div
                    key={`log-${idx}-${String(log).slice(0, 24)}`}
                    className="text-sm py-1 font-mono"
                    style={{ 
                      color: log.includes('ERROR') ? '#ef4444' : 
                             log.includes('WARNING') ? '#f59e0b' :
                             log.includes('SUCCESS') ? '#10b981' : 'var(--text-secondary)'
                    }}
                  >
                    {log}
                  </div>
                ))}
              </div>
            </div>
          )}
          {/* تحليل تقرير التدقيق بواسطة البوت المالي */}
          <div className="mt-8 max-w-3xl mx-auto" dir="rtl">
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-lg">
              <h3 className="text-sm font-semibold mb-2 text-slate-100 flex items-center gap-2">
                <Brain className="h-4 w-4 text-blue-400" />
                تحليل تقرير التدقيق باستخدام المحاسب المالي الذكي
              </h3>
              <p className="text-xs text-slate-400 mb-3">
                اضغط على الزر أدناه لإرسال ملخص تقرير التدقيق إلى البوت المالي والحصول على شرح وتوصيات.
              </p>
              <button
                type="button"
                onClick={handleAnalyzeWithFinanceBot}
                disabled={financeBotLoading}
                className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm disabled:opacity-50 flex items-center gap-2"
              >
                {financeBotLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                {financeBotLoading ? 'جاري تحليل تقرير التدقيق...' : 'حلّل تقرير التدقيق الآن'}
              </button>

              {financeBotError && (
                <p className="mt-3 text-xs text-red-400">{financeBotError}</p>
              )}

              {financeBotResponse && (
                <div className="mt-3 p-3 rounded-lg bg-slate-900/70 border border-slate-800 text-xs text-slate-100 whitespace-pre-wrap">
                  {financeBotResponse}
                </div>
              )}
            </div>
          </div>

        </div>
      )}
    </div>
  );
};

export default SystemAudit;