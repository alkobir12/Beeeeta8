import React, { useEffect, useMemo, useRef, useState } from 'react';
import { BadgeCheck, CheckCircle2, Download, Eye, FileCode2, FileText, MessageCircle, Printer, RefreshCw, Star, Trash2, UploadCloud } from 'lucide-react';
import OutboundMessagesTab from '../components/OutboundMessagesTab';
import axios from 'axios';
import { useToast } from '../hooks/use-toast';
import { resolveBackendBase } from '../utils/backendBase';
import { assertTemplateComplete, renderDocumentTemplate } from '../utils/documentTemplate';

const API_URL = `${resolveBackendBase()}/api`;
const docTypes = { invoice: 'فاتورة', diagnosis: 'تقرير تشخيص', quote: 'عرض سعر', receipt: 'سند زيارة' };

const formatSize = (bytes = 0) => {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const TemplatesManager = () => {
  const { toast } = useToast();
  const fileRef = useRef(null);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedType, setSelectedType] = useState('invoice');
  const [templateName, setTemplateName] = useState('');
  const [description, setDescription] = useState('');
  const [preview, setPreview] = useState(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewReason, setPreviewReason] = useState('');
  const [previewError, setPreviewError] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('print');

  const grouped = useMemo(() => Object.keys(docTypes).reduce((acc, key) => {
    acc[key] = templates.filter((tpl) => (tpl.document_type || tpl.type || 'invoice') === key);
    return acc;
  }, {}), [templates]);

  const activeCount = useMemo(() => templates.filter((tpl) => tpl.is_default).length, [templates]);
  const tenantDefaultTypes = useMemo(() => new Set(templates.filter((tpl) => tpl.tenant_id !== 'system' && tpl.is_default).map((tpl) => tpl.document_type || tpl.type)), [templates]);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_URL}/document-templates`);
      setTemplates(Array.isArray(response.data?.templates) ? response.data.templates : []);
    } catch (error) {
      toast({ title: 'تعذر تحميل النماذج', description: 'تأكد من الاتصال وحاول مرة أخرى', variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTemplates(); }, []);

  const uploadTemplate = async (file) => {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['html', 'htm', 'pdf'].includes(ext)) {
      toast({ title: 'ملف غير مدعوم', description: 'ارفع HTML أو PDF فقط', variant: 'destructive' });
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('name', templateName || file.name.replace(/\.(html|htm|pdf)$/i, ''));
      formData.append('description', description || 'نموذج مرفوع من إدارة النماذج');
      formData.append('document_type', selectedType);
      const response = await axios.post(`${API_URL}/document-templates/upload`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast({ title: 'تم حفظ النموذج', description: ext === 'pdf' ? 'صُنّف للتحميل فقط' : 'تمت إضافته ويمكن تعيينه افتراضياً' });
      setTemplateName('');
      setDescription('');
      if (fileRef.current) fileRef.current.value = '';
      await loadTemplates();
      await openPreview(response.data?.template || null);
    } catch (error) {
      toast({ title: 'فشل رفع النموذج', description: error.response?.data?.detail || 'حاول مرة أخرى', variant: 'destructive' });
    } finally {
      setUploading(false);
    }
  };

  const makeDefault = async (template) => {
    try {
      await axios.post(`${API_URL}/document-templates/${template.id}/set-default`, {});
      toast({ title: 'تم التعيين', description: `صار «${template.name}» النموذج الافتراضي` });
      await loadTemplates();
    } catch (error) {
      toast({ title: 'تعذر التعيين', description: error.response?.data?.detail?.message || error.response?.data?.detail?.code || 'حاول مرة أخرى', variant: 'destructive' });
    }
  };

  const openPreview = async (template) => {
    setPreview(template); setPreviewHtml(''); setPreviewReason(''); setPreviewError(''); setPreviewLoading(true);
    try {
      const response = await axios.post(`${API_URL}/document-templates/${template.id}/use`, { document_type: template.document_type || template.type });
      const rendered = renderDocumentTemplate(response.data?.content || '', {
        settings: { document_number: 'PREVIEW-001', date: new Date().toISOString().slice(0, 10), status: 'مسودة', notes: 'معاينة داخل إدارة القوالب' },
        customer: { name: 'عميل تجريبي', phone: '0500000000' }, vehicle: { plateNumber: 'أ ب ج 1234', brand: 'Toyota', model: 'Camry', year: 2024 },
        items: [{ description: 'خدمة تجريبية', quantity: 1, unit_price: 100 }], payment: { paid: 100 },
      }, { name: 'ورشة تجريبية', phone: '0500000000', address: 'الرياض', tax_number: '300000000000003' });
      assertTemplateComplete(rendered);
      setPreviewHtml(rendered);
      setPreviewReason(response.data?.selection_reason || 'explicit_document_template');
    } catch (error) {
      const detail = error.response?.data?.detail;
      setPreviewError(error?.code === 'template_incomplete' ? error.message : (detail?.message || detail?.code || 'تعذر تحميل القالب للمعاينة.'));
    } finally { setPreviewLoading(false); }
  };

  const deleteTemplate = async (template) => {
    if (template.is_builtin) {
      toast({ title: 'نموذج أساسي', description: 'النموذج الرسمي لا يُحذف، اختر نموذجاً آخر كافتراضي بدلاً منه.' });
      return;
    }
    if (!window.confirm(`حذف النموذج «${template.name}»؟`)) return;
    try {
      await axios.delete(`${API_URL}/document-templates/${template.id}`);
      toast({ title: 'تمت الأرشفة', description: 'حُفظ القالب خارج خيارات الطباعة' });
      await loadTemplates();
    } catch (error) {
      toast({ title: 'فشل الحذف', description: 'حاول مرة أخرى', variant: 'destructive' });
    }
  };

  const downloadTemplate = async (template) => {
    try {
      const response = await axios.get(`${API_URL}/document-templates/${template.id}/download`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', template.original_filename || `${template.name}.html`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast({ title: 'فشل التحميل', description: 'حاول مرة أخرى', variant: 'destructive' });
    }
  };

  return (
    <div className="templates-page" dir="rtl" data-testid="templates-manager-page">
      <style>{styles}</style>
      <header className="templates-hero" data-testid="templates-manager-header">
        <div>
          <p data-testid="templates-manager-kicker">Dash Pro · مركز النماذج</p>
          <h1 data-testid="templates-manager-title">إدارة النماذج</h1>
          <span data-testid="templates-manager-description">عيّن قالب HTML صالحاً كافتراض للمستأجر؛ يبقى القالب النظامي احتياطياً فقط.</span>
        </div>
        <button type="button" className="tm-button ghost" onClick={loadTemplates} data-testid="templates-refresh-button"><RefreshCw size={18} /> تحديث</button>
      </header>

      <nav className="tm-tabs" data-testid="templates-tabs">
        <button type="button" className={`tm-tab ${activeTab === 'print' ? 'active' : ''}`} onClick={() => setActiveTab('print')} data-testid="templates-tab-print"><Printer size={17} /> نماذج الطباعة</button>
        <button type="button" className={`tm-tab ${activeTab === 'whatsapp' ? 'active' : ''}`} onClick={() => setActiveTab('whatsapp')} data-testid="templates-tab-whatsapp"><MessageCircle size={17} /> رسائل واتساب</button>
      </nav>

      {activeTab === 'whatsapp' && <OutboundMessagesTab />}

      {activeTab === 'print' && (<>
      <section className="templates-stats" data-testid="templates-stats">
        <Stat label="كل النماذج" value={templates.length} testId="templates-total-count" />
        <Stat label="النماذج الافتراضية" value={activeCount} testId="templates-default-count" />
        <Stat label="أنواع المستندات" value={Object.keys(docTypes).length} testId="templates-types-count" />
      </section>

      <main className="templates-layout">
        <section className="upload-panel" data-testid="template-upload-panel">
          <div className="panel-heading"><UploadCloud size={22} /><div><h2>رفع نموذج HTML</h2><p>ارفع ملفك واحفظه؛ سيتم إضافته تلقائياً لقائمة النماذج وخيارات الطباعة.</p></div></div>
          <div className="upload-grid">
            <label className="tm-field" data-testid="template-name-field"><span>اسم النموذج</span><input value={templateName} onChange={(e) => setTemplateName(e.target.value)} placeholder="مثال: فاتورة الورشة المختومة" data-testid="template-name-input" /></label>
            <label className="tm-field" data-testid="template-type-field"><span>نوع المستند</span><select value={selectedType} onChange={(e) => setSelectedType(e.target.value)} data-testid="template-type-select">{Object.entries(docTypes).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          </div>
          <label className="tm-field" data-testid="template-description-field"><span>الوصف</span><textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="وصف مختصر للنموذج" data-testid="template-description-input" /></label>
          <div className="drop-zone" onClick={() => fileRef.current?.click()} data-testid="template-file-dropzone">
            <FileCode2 size={34} />
            <strong>اختر ملف HTML أو PDF</strong>
            <span>HTML قابل للتعيين كافتراضي — PDF يبقى للتحميل والأرشفة</span>
            <input ref={fileRef} type="file" accept=".html,.htm,.pdf" onChange={(e) => uploadTemplate(e.target.files?.[0])} data-testid="template-file-input" />
          </div>
          <button type="button" className="tm-button primary full" disabled={uploading} onClick={() => fileRef.current?.click()} data-testid="template-upload-button"><UploadCloud size={18} />{uploading ? 'جارٍ الحفظ...' : 'إرفاق وحفظ كنموذج'}</button>
        </section>

        <section className="templates-list-panel" data-testid="templates-list-panel">
          <div className="panel-heading compact"><FileText size={22} /><div><h2>النماذج الافتراضية والمرفوعة</h2><p>اختر الافتراضي لكل نوع، وسيظهر في كل نوافذ الطباعة.</p></div></div>
          {loading ? <div className="empty" data-testid="templates-loading">جارٍ تحميل النماذج...</div> : Object.entries(docTypes).map(([type, label]) => (
            <div className="type-group" key={type} data-testid={`templates-group-${type}`}>
              <h3>{label}<span>{grouped[type]?.length || 0}</span></h3>
              <div className="template-cards">
                {(grouped[type] || []).map((template) => (
                  <article className={`template-card ${template.is_default ? 'active' : ''}`} key={template.id} data-testid={`template-card-${template.id}`}>
                    <div className="template-icon">{template.file_type === 'pdf' ? <FileText size={20} /> : <FileCode2 size={20} />}</div>
                    <div className="template-main">
                      <div className="template-title-row"><h4 data-testid={`template-name-${template.id}`}>{template.name}</h4>{template.is_default && (template.tenant_id !== 'system' || !tenantDefaultTypes.has(template.document_type || template.type)) && <span data-testid={`template-default-badge-${template.id}`}><BadgeCheck size={14} /> {template.tenant_id === 'system' ? 'افتراضي نظامي' : 'افتراضي'}</span>}</div>
                      <p data-testid={`template-description-${template.id}`}>{template.description || 'بدون وصف'}</p>
                      <small data-testid={`template-meta-${template.id}`}>{template.is_builtin ? 'نظامي' : 'مخصص'} · إصدار {template.version || 1} · {template.active ? 'نشط' : 'معطل'} · {template.status || 'غير مصنف'}</small>
                      <div className="template-actions">
                        <button type="button" onClick={() => openPreview(template)} data-testid={`template-preview-${template.id}`}><Eye size={15} /> معاينة</button>
                        <button type="button" onClick={() => downloadTemplate(template)} data-testid={`template-download-${template.id}`}><Download size={15} /> تحميل</button>
                        {template.file_type === 'html' && template.active && <button type="button" onClick={() => makeDefault(template)} data-testid={`template-make-default-${template.id}`}><Star size={15} /> تعيين كافتراضي</button>}
                        <button type="button" className="danger" onClick={() => deleteTemplate(template)} data-testid={`template-delete-${template.id}`}><Trash2 size={15} /> حذف</button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ))}
        </section>
      </main>
      </>)}

      {preview && <TemplatePreview template={preview} html={previewHtml} reason={previewReason} error={previewError} loading={previewLoading} onClose={() => setPreview(null)} />}
    </div>
  );
};

function Stat({ label, value, testId }) {
  return <div className="tm-stat" data-testid={testId}><span>{label}</span><strong>{value}</strong><CheckCircle2 size={18} /></div>;
}

function TemplatePreview({ template, html, reason, error, loading, onClose }) {
  return <div className="preview-modal" data-testid="template-preview-modal"><div className="preview-card"><div className="preview-head"><div><h3 data-testid="template-preview-title">{template.name}</h3><p data-testid="template-preview-subtitle">{docTypes[template.document_type || template.type]} · سبب الاختيار: {reason || 'جارٍ التحقق'}</p></div><button type="button" onClick={onClose} data-testid="template-preview-close">إغلاق</button></div><div className="preview-body"><p data-testid="template-preview-description">{template.description || 'قالب بلا وصف'}</p>{loading && <div className="preview-paper" data-testid="template-preview-loading">جارٍ تحميل القالب المعقّم...</div>}{error && <div className="preview-paper" data-testid="template-preview-error">فشلت المعاينة: {error}</div>}{!loading && !error && html && <iframe title={`preview-${template.id}`} srcDoc={html} sandbox="" style={{ width: '100%', height: 'min(65vh, 620px)', border: '1px solid #e2e8f0', borderRadius: 18, background: '#fff' }} data-testid="template-preview-frame" />}</div></div></div>;
}

const styles = `
.templates-page{min-height:100vh;padding:20px;background:linear-gradient(180deg,#f6f7fb,#eef3f8);color:#172033;direction:rtl}.templates-page *{box-sizing:border-box}.templates-hero{max-width:1320px;margin:0 auto 18px;padding:22px;border-radius:24px;background:linear-gradient(135deg,#172033,#1e3a5f);display:flex;align-items:center;justify-content:space-between;gap:16px;box-shadow:0 22px 50px rgba(23,32,51,.18)}.templates-hero p{margin:0 0 5px;color:#93c5fd!important;font-weight:900;font-size:13px}.templates-hero h1{margin:0;color:#fff!important;font-size:34px;font-weight:950}.templates-hero span{color:#dbeafe!important;font-size:14px}.tm-button{min-height:44px;display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:14px;border:1px solid #e2e8f0;background:#fff;color:#172033;font-weight:900;padding:9px 15px;cursor:pointer}.tm-button.primary{background:linear-gradient(135deg,#2563eb,#0ea5e9);border:0;color:#fff}.tm-button.ghost{background:rgba(255,255,255,.10);border-color:rgba(255,255,255,.18);color:#fff}.tm-button.full{width:100%;margin-top:12px}.templates-stats{max-width:1320px;margin:0 auto 18px;display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.tm-stat{padding:18px;border:1px solid #e2e8f0;border-radius:20px;background:#fff;box-shadow:0 10px 28px rgba(15,23,42,.06);display:flex;align-items:center;justify-content:space-between}.tm-stat span{color:#64748b!important;font-size:13px;font-weight:850}.tm-stat strong{font-size:28px;color:#172033!important}.tm-stat svg{color:#2563eb}.templates-layout{max-width:1320px;margin:0 auto;display:grid;grid-template-columns:420px minmax(0,1fr);gap:16px;align-items:start}.upload-panel,.templates-list-panel{border:1px solid #e2e8f0;background:#fff;border-radius:24px;padding:18px;box-shadow:0 12px 32px rgba(15,23,42,.07)}.upload-panel{position:sticky;top:18px}.panel-heading{display:flex;gap:12px;align-items:flex-start;margin-bottom:16px}.panel-heading svg{color:#2563eb;flex:none}.panel-heading h2{margin:0;color:#172033!important;font-size:18px;font-weight:950}.panel-heading p{margin:3px 0 0;color:#64748b!important;font-size:13px}.panel-heading.compact{border-bottom:1px solid #eef2f7;padding-bottom:14px}.upload-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.tm-field{display:block;margin-bottom:10px}.tm-field span{display:block;margin-bottom:6px;color:#64748b!important;font-size:12px;font-weight:900}.tm-field input,.tm-field select,.tm-field textarea{width:100%;border:1px solid #e2e8f0;background:#fff;border-radius:14px;min-height:44px;padding:10px 12px;color:#172033;font-weight:800;outline:none}.tm-field textarea{min-height:86px;resize:vertical}.drop-zone{min-height:180px;border:2px dashed #bfdbfe;border-radius:20px;background:#f8fbff;display:grid;place-items:center;text-align:center;padding:22px;cursor:pointer}.drop-zone svg{color:#2563eb}.drop-zone strong{color:#172033!important;font-size:17px}.drop-zone span{color:#64748b!important;font-size:12px}.drop-zone input{display:none}.type-group{margin-top:18px}.type-group h3{display:flex;align-items:center;justify-content:space-between;margin:0 0 10px;color:#172033!important;font-size:16px;font-weight:950}.type-group h3 span{background:#eff6ff;color:#2563eb!important;border-radius:999px;padding:3px 10px;font-size:12px}.template-cards{display:grid;gap:10px}.template-card{display:flex;gap:12px;padding:14px;border:1px solid #e2e8f0;border-radius:18px;background:#fff;transition:box-shadow .18s ease,border-color .18s ease}.template-card.active{border-color:#93c5fd;background:#f8fbff}.template-icon{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;background:#eff6ff;color:#2563eb;flex:none}.template-main{min-width:0;flex:1}.template-title-row{display:flex;gap:8px;align-items:center;justify-content:space-between}.template-title-row h4{margin:0;color:#172033!important;font-size:15px;font-weight:950}.template-title-row span{display:inline-flex;align-items:center;gap:4px;border-radius:999px;background:#d1fae5;color:#047857!important;padding:3px 9px;font-size:11px;font-weight:900}.template-main p{margin:5px 0;color:#64748b!important;font-size:12px}.template-main small{color:#94a3b8!important;font-size:11px}.template-actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}.template-actions button{border:1px solid #e2e8f0;background:#fff;border-radius:10px;min-height:34px;padding:6px 10px;display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:850;color:#172033;cursor:pointer}.template-actions button.danger{color:#be123c;background:#fff1f2;border-color:#fecdd3}.empty{padding:30px;text-align:center;color:#64748b}.preview-modal{position:fixed;inset:0;background:rgba(15,23,42,.68);display:grid;place-items:center;z-index:80;padding:18px}.preview-card{width:min(620px,100%);border-radius:24px;background:#fff;border:1px solid #e2e8f0;box-shadow:0 30px 80px rgba(0,0,0,.28);overflow:hidden}.preview-head{padding:18px;background:#172033;display:flex;align-items:center;justify-content:space-between;gap:12px}.preview-head h3{margin:0;color:#fff!important}.preview-head p{margin:3px 0 0;color:#bfdbfe!important;font-size:12px}.preview-head button{border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.10);color:#fff;border-radius:12px;padding:8px 12px}.preview-body{padding:18px}.preview-body p{color:#64748b!important}.preview-paper{height:260px;border-radius:18px;border:1px solid #e2e8f0;background:linear-gradient(180deg,#fff,#f8fbff);display:grid;place-items:center;text-align:center;color:#172033}.preview-paper svg{color:#2563eb}.preview-paper strong{color:#172033!important}.preview-paper span{color:#64748b!important}.tm-tabs{max-width:1320px;margin:0 auto 16px;display:flex;gap:10px;background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:8px;box-shadow:0 10px 26px rgba(15,23,42,.06)}.tm-tab{flex:1;min-height:48px;display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:12px;border:1px solid transparent;background:transparent;color:#64748b;font-weight:900;font-size:14px;cursor:pointer;transition:background .18s ease,color .18s ease}.tm-tab.active{background:linear-gradient(135deg,#172033,#1e3a5f);color:#fff}.tm-tab:hover:not(.active){background:#f1f5f9;color:#172033}@media(max-width:980px){.templates-layout{grid-template-columns:1fr}.upload-panel{position:static}.templates-stats{grid-template-columns:1fr}.templates-hero{align-items:flex-start;flex-direction:column}.upload-grid{grid-template-columns:1fr}}
`;

export default TemplatesManager;