import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, History, MessageCircle, Pencil, RefreshCw, RotateCcw, Power, X } from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import {
  listOutboundTemplates,
  listOutboundVariables,
  restoreOutboundTemplate,
  updateOutboundTemplate,
} from '../services/outboundShare';

const docTypes = { invoice: 'فاتورة', diagnosis: 'تقرير تشخيص', quote: 'عرض سعر', receipt: 'سند زيارة' };
const statusLabels = { '*': 'كل الحالات', paid: 'مدفوعة', partial: 'جزئية', unpaid: 'غير مدفوعة', deferred: 'آجلة', draft: 'مسودة', cancelled: 'ملغي' };

const errorText = (error) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  return 'حدث خطأ — حاول مرة أخرى';
};

const OutboundMessagesTab = () => {
  const { toast } = useToast();
  const [templates, setTemplates] = useState([]);
  const [variables, setVariables] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [tplRes, varRes] = await Promise.all([listOutboundTemplates(), listOutboundVariables()]);
      setTemplates(tplRes.templates || []);
      setVariables(varRes.variables || []);
    } catch (error) {
      toast({ title: 'تعذر تحميل قوالب الرسائل', description: errorText(error), variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const grouped = useMemo(() => Object.keys(docTypes).reduce((acc, key) => {
    acc[key] = templates.filter((tpl) => tpl.doc_type === key);
    return acc;
  }, {}), [templates]);

  const toggleEnabled = async (tpl) => {
    try {
      await updateOutboundTemplate(tpl.id, { enabled: !tpl.enabled });
      toast({ title: tpl.enabled ? 'تم تعطيل القالب' : 'تم تفعيل القالب' });
      await load();
    } catch (error) {
      toast({ title: 'تعذر التغيير', description: errorText(error), variant: 'destructive' });
    }
  };

  const restore = async (tpl) => {
    if (!window.confirm(`استرجاع النص الافتراضي للقالب «${tpl.name}»؟`)) return;
    try {
      await restoreOutboundTemplate(tpl.id);
      toast({ title: 'تم استرجاع النص الافتراضي' });
      await load();
    } catch (error) {
      toast({ title: 'تعذر الاسترجاع', description: errorText(error), variant: 'destructive' });
    }
  };

  return (
    <section className="wa-templates" data-testid="outbound-messages-tab">
      <style>{styles}</style>
      <div className="wa-head">
        <div className="wa-head-text">
          <span className="wa-head-icon"><MessageCircle size={22} /></span>
          <div>
            <h2 data-testid="outbound-messages-title">قوالب رسائل واتساب الصادرة</h2>
            <p data-testid="outbound-messages-description">نص ثابت لكل نوع مستند وحالة — يُحل تلقائياً بالمتغيرات عند ضغط «PDF وواتساب». التسجيل في سجل التدقيق لا يدّعي التسليم أبداً.</p>
          </div>
        </div>
        <button type="button" className="wa-btn ghost" onClick={load} data-testid="outbound-messages-refresh"><RefreshCw size={16} /> تحديث</button>
      </div>

      {loading && <div className="wa-empty" data-testid="outbound-messages-loading">جارٍ تحميل قوالب الرسائل...</div>}

      {!loading && Object.entries(docTypes).map(([type, label]) => (
        <div className="wa-group" key={type} data-testid={`outbound-group-${type}`}>
          <h3>{label}<span>{grouped[type]?.length || 0}</span></h3>
          <div className="wa-cards">
            {(grouped[type] || []).map((tpl) => (
              <article className={`wa-card ${tpl.enabled ? '' : 'disabled'}`} key={tpl.id} data-testid={`outbound-template-card-${tpl.action_key}`}>
                <div className="wa-card-top">
                  <div>
                    <h4 data-testid={`outbound-template-name-${tpl.action_key}`}>{tpl.name}</h4>
                    <small>{tpl.action_key} · النسخة v{tpl.version}</small>
                  </div>
                  <span className={`wa-badge ${tpl.enabled ? 'on' : 'off'}`} data-testid={`outbound-template-status-${tpl.action_key}`}>
                    {tpl.enabled ? 'نشط' : 'معطل'}
                  </span>
                </div>
                <div className="wa-statuses">
                  {(tpl.allowed_statuses || []).map((st) => <span key={st}>{statusLabels[st] || st}</span>)}
                  {(tpl.default_attachments || []).includes('pdf') && <span className="att">📎 PDF</span>}
                  {(tpl.default_attachments || []).includes('image') && <span className="att">🖼️ صورة</span>}
                  {tpl.allow_edit_before_share === false && <span className="lock">🔒 بلا تعديل قبل الإرسال</span>}
                </div>
                <pre className="wa-body" data-testid={`outbound-template-body-${tpl.action_key}`}>{tpl.body}</pre>
                <div className="wa-actions">
                  <button type="button" onClick={() => setEditing({ ...tpl })} data-testid={`outbound-template-edit-${tpl.action_key}`}><Pencil size={14} /> تحرير</button>
                  <button type="button" onClick={() => restore(tpl)} data-testid={`outbound-template-restore-${tpl.action_key}`}><RotateCcw size={14} /> النص الافتراضي</button>
                  <button type="button" className={tpl.enabled ? 'danger' : 'ok'} onClick={() => toggleEnabled(tpl)} data-testid={`outbound-template-toggle-${tpl.action_key}`}><Power size={14} /> {tpl.enabled ? 'تعطيل' : 'تفعيل'}</button>
                  {(tpl.versions || []).length > 0 && <span className="wa-history"><History size={13} /> {tpl.versions.length} نسخة سابقة</span>}
                </div>
              </article>
            ))}
            {!loading && !(grouped[type] || []).length && <div className="wa-empty">لا توجد قوالب لهذا النوع.</div>}
          </div>
        </div>
      ))}

      {editing && (
        <EditModal
          template={editing}
          variables={variables}
          onClose={() => setEditing(null)}
          onSaved={async () => { setEditing(null); await load(); }}
        />
      )}
    </section>
  );
};

function EditModal({ template, variables, onClose, onSaved }) {
  const { toast } = useToast();
  const [name, setName] = useState(template.name || '');
  const [body, setBody] = useState(template.body || '');
  const [statuses, setStatuses] = useState(template.allowed_statuses || []);
  const [attachments, setAttachments] = useState(template.default_attachments || []);
  const [allowEdit, setAllowEdit] = useState(template.allow_edit_before_share !== false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const toggleList = (list, setList, value) => {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  };

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      await updateOutboundTemplate(template.id, {
        name,
        body,
        allowed_statuses: statuses,
        default_attachments: attachments,
        allow_edit_before_share: allowEdit,
      });
      toast({ title: 'تم حفظ القالب', description: `النسخة الجديدة v${(template.version || 1) + 1}` });
      onSaved();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="wa-modal" data-testid="outbound-edit-modal">
      <div className="wa-modal-card">
        <div className="wa-modal-head">
          <div>
            <h3 data-testid="outbound-edit-title">تحرير قالب «{template.name}»</h3>
            <p>{template.action_key} · {docTypes[template.doc_type]} · النسخة الحالية v{template.version}</p>
          </div>
          <button type="button" onClick={onClose} data-testid="outbound-edit-close"><X size={17} /></button>
        </div>
        <div className="wa-modal-body">
          <label className="wa-field"><span>اسم القالب</span><input value={name} onChange={(e) => setName(e.target.value)} data-testid="outbound-edit-name-input" /></label>
          <label className="wa-field">
            <span>نص الرسالة (المتغيرات بصيغة {'{{VAR}}'} الموحدة)</span>
            <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={9} data-testid="outbound-edit-body-input" />
          </label>
          <div className="wa-vars" data-testid="outbound-edit-variables">
            {variables.map((v) => (
              <button type="button" key={v.key} title={v.label} onClick={() => setBody((prev) => `${prev}{{${v.key}}}`)} data-testid={`outbound-variable-${v.key}`}>
                {`{{${v.key}}}`} <em>{v.label}</em>
              </button>
            ))}
          </div>
          <div className="wa-field">
            <span>الحالات المسموح بها</span>
            <div className="wa-checks" data-testid="outbound-edit-statuses">
              {Object.entries(statusLabels).map(([key, label]) => (
                <label key={key}><input type="checkbox" checked={statuses.includes(key)} onChange={() => toggleList(statuses, setStatuses, key)} data-testid={`outbound-status-check-${key}`} /> {label}</label>
              ))}
            </div>
          </div>
          <div className="wa-field">
            <span>المرفقات الافتراضية</span>
            <div className="wa-checks">
              <label><input type="checkbox" checked={attachments.includes('pdf')} onChange={() => toggleList(attachments, setAttachments, 'pdf')} data-testid="outbound-attachment-pdf" /> ملف PDF</label>
              <label><input type="checkbox" checked={attachments.includes('image')} onChange={() => toggleList(attachments, setAttachments, 'image')} data-testid="outbound-attachment-image" /> صورة معاينة</label>
              <label><input type="checkbox" checked={allowEdit} onChange={() => setAllowEdit(!allowEdit)} data-testid="outbound-allow-edit-check" /> السماح بتعديل النص قبل المشاركة</label>
            </div>
          </div>
          {error && <div className="wa-error" data-testid="outbound-edit-error">{error}</div>}
        </div>
        <div className="wa-modal-foot">
          <button type="button" className="wa-btn ghost" onClick={onClose} data-testid="outbound-edit-cancel">إلغاء</button>
          <button type="button" className="wa-btn primary" disabled={saving} onClick={save} data-testid="outbound-edit-save"><CheckCircle2 size={16} /> {saving ? 'جارٍ الحفظ...' : 'حفظ نسخة جديدة'}</button>
        </div>
      </div>
    </div>
  );
}

const styles = `
.wa-templates{max-width:1320px;margin:0 auto}
.wa-head{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:18px;border-radius:22px;border:1px solid #d1fae5;background:linear-gradient(135deg,#ecfdf5,#f0fdfa);margin-bottom:16px}
.wa-head-text{display:flex;gap:12px;align-items:flex-start;min-width:0}
.wa-head-icon{width:46px;height:46px;border-radius:14px;background:#059669;color:#fff;display:grid;place-items:center;flex:none}
.wa-head h2{margin:0;font-size:18px;font-weight:950;color:#064e3b!important}
.wa-head p{margin:4px 0 0;font-size:12.5px;color:#047857!important;line-height:1.7}
.wa-btn{min-height:42px;display:inline-flex;align-items:center;gap:7px;border-radius:12px;border:1px solid #d1fae5;background:#fff;color:#065f46;font-weight:900;padding:8px 14px;cursor:pointer;font-size:13px}
.wa-btn.primary{background:linear-gradient(135deg,#059669,#10b981);color:#fff;border:0}
.wa-btn.ghost{background:#fff}
.wa-group{margin-bottom:18px}
.wa-group h3{display:flex;align-items:center;justify-content:space-between;margin:0 0 10px;font-size:15px;font-weight:950;color:#172033!important}
.wa-group h3 span{background:#ecfdf5;color:#059669!important;border-radius:999px;padding:3px 10px;font-size:12px}
.wa-cards{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(340px,1fr))}
.wa-card{border:1px solid #e2e8f0;border-radius:18px;background:#fff;padding:14px;box-shadow:0 8px 22px rgba(15,23,42,.05)}
.wa-card.disabled{opacity:.62}
.wa-card-top{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
.wa-card-top h4{margin:0;font-size:14.5px;font-weight:950;color:#172033!important}
.wa-card-top small{color:#94a3b8!important;font-size:11px;direction:ltr;display:inline-block}
.wa-badge{border-radius:999px;padding:3px 10px;font-size:11px;font-weight:900;flex:none}
.wa-badge.on{background:#d1fae5;color:#047857!important}
.wa-badge.off{background:#f1f5f9;color:#64748b!important}
.wa-statuses{display:flex;flex-wrap:wrap;gap:5px;margin:9px 0}
.wa-statuses span{background:#eff6ff;color:#1d4ed8!important;border-radius:999px;padding:2px 9px;font-size:10.5px;font-weight:900}
.wa-statuses span.att{background:#f0fdf4;color:#15803d!important}
.wa-statuses span.lock{background:#fef2f2;color:#b91c1c!important}
.wa-body{margin:0;max-height:150px;overflow:auto;background:#f8fafc;border:1px solid #edf2f7;border-radius:12px;padding:10px;font-size:11.5px;line-height:1.9;color:#334155!important;white-space:pre-wrap;font-family:inherit;direction:rtl}
.wa-actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px;align-items:center}
.wa-actions button{border:1px solid #e2e8f0;background:#fff;border-radius:10px;min-height:34px;padding:6px 10px;display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:850;color:#172033;cursor:pointer}
.wa-actions button.danger{color:#be123c;background:#fff1f2;border-color:#fecdd3}
.wa-actions button.ok{color:#047857;background:#ecfdf5;border-color:#bbf7d0}
.wa-history{display:inline-flex;align-items:center;gap:4px;color:#94a3b8!important;font-size:11px;font-weight:800}
.wa-empty{padding:26px;text-align:center;color:#64748b;background:#fff;border:1px dashed #e2e8f0;border-radius:16px}
.wa-modal{position:fixed;inset:0;background:rgba(15,23,42,.7);display:grid;place-items:center;z-index:90;padding:16px}
.wa-modal-card{width:min(720px,100%);max-height:92vh;display:flex;flex-direction:column;border-radius:22px;background:#fff;overflow:hidden;box-shadow:0 30px 80px rgba(0,0,0,.3)}
.wa-modal-head{padding:16px 18px;background:#064e3b;display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.wa-modal-head h3{margin:0;color:#fff!important;font-size:16px;font-weight:950}
.wa-modal-head p{margin:4px 0 0;color:#a7f3d0!important;font-size:11.5px;direction:ltr;text-align:right}
.wa-modal-head button{border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.1);color:#fff;border-radius:10px;width:36px;height:36px;display:grid;place-items:center;cursor:pointer;flex:none}
.wa-modal-body{padding:16px 18px;overflow-y:auto}
.wa-field{display:block;margin-bottom:12px}
.wa-field>span{display:block;margin-bottom:6px;color:#64748b!important;font-size:12px;font-weight:900}
.wa-field input[type=text],.wa-field input:not([type]),.wa-field textarea{width:100%;border:1px solid #e2e8f0;border-radius:12px;min-height:44px;padding:10px 12px;color:#172033;font-weight:700;outline:none;font-family:inherit;font-size:13px;box-sizing:border-box}
.wa-field textarea{line-height:1.9;resize:vertical}
.wa-vars{display:flex;flex-wrap:wrap;gap:6px;margin:-4px 0 12px}
.wa-vars button{border:1px solid #dbeafe;background:#eff6ff;color:#1d4ed8;border-radius:999px;padding:4px 10px;font-size:10.5px;font-weight:900;cursor:pointer;direction:ltr}
.wa-vars button em{color:#64748b;font-style:normal;font-size:10px}
.wa-checks{display:flex;flex-wrap:wrap;gap:12px}
.wa-checks label{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:800;color:#334155;cursor:pointer}
.wa-error{background:#fef2f2;border:1px solid #fecaca;color:#b91c1c!important;border-radius:12px;padding:10px 12px;font-size:12.5px;font-weight:800}
.wa-modal-foot{padding:14px 18px;border-top:1px solid #eef2f7;display:flex;justify-content:flex-end;gap:8px}
@media(max-width:720px){.wa-cards{grid-template-columns:1fr}.wa-head{flex-direction:column;align-items:flex-start}}
`;

export default OutboundMessagesTab;
