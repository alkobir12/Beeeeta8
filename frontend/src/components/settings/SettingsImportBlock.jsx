import React, { useState } from 'react';
import axios from 'axios';
import { Card } from '../ui/card';
import { Button } from '../ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs';
import { resolveBackendBase } from '../../utils/backendBase';
import { Upload, CheckCircle2, AlertCircle, FileDown } from 'lucide-react';

const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);

/**
 * 📦 SettingsImportBlock — compact import widget that lives INSIDE Settings page (not its own page).
 * Combines customers / services / parts CSV+XLSX imports in a single block.
 */
const SettingsImportBlock = () => {
  const [active, setActive] = useState('customers');

  const [files, setFiles] = useState({ customers: null, services: null, parts: null });
  const [modes, setModes] = useState({ customers: 'skip', services: 'skip', parts: 'skip' });
  const [results, setResults] = useState({ customers: null, services: null, parts: null });
  const [loading, setLoading] = useState({ customers: false, services: false, parts: false });

  const upload = async (kind, format) => {
    const file = files[kind];
    if (!file) return;
    setLoading((p) => ({ ...p, [kind]: true }));
    setResults((p) => ({ ...p, [kind]: null }));
    try {
      const fd = new FormData();
      fd.append('file', file);
      const endpoint = `/import/${kind}/${format}`;
      const { data } = await axios.post(`${API_URL}${endpoint}?mode=${modes[kind]}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResults((p) => ({ ...p, [kind]: { ok: true, data } }));
    } catch (e) {
      setResults((p) => ({ ...p, [kind]: { ok: false, error: e?.response?.data?.detail || 'فشل الرفع' } }));
    } finally {
      setLoading((p) => ({ ...p, [kind]: false }));
    }
  };

  const PANEL = (kind, title, headerHint) => (
    <Card className="p-4 border-slate-200 dark:border-white/10">
      <h3 className="text-sm font-bold mb-1 text-slate-800 dark:text-slate-200">{title}</h3>
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
        <FileDown size={12} className="inline mb-0.5 ml-1" />
        الترويسة المطلوبة: <code className="bg-slate-100 dark:bg-white/10 px-1.5 py-0.5 rounded">{headerHint}</code>
      </p>

      <div className="flex flex-wrap items-center gap-2 mb-3">
        <select
          className="border border-slate-300 dark:border-white/10 bg-white dark:bg-[#1a1a1a] rounded-lg px-2 py-1.5 text-xs"
          value={modes[kind]}
          onChange={(e) => setModes((p) => ({ ...p, [kind]: e.target.value }))}
          data-testid={`settings-import-mode-${kind}`}
        >
          <option value="skip">تخطي المكرر</option>
          <option value="update">تحديث الموجود</option>
        </select>
        <input
          type="file"
          accept=".csv,.xlsx"
          onChange={(e) => setFiles((p) => ({ ...p, [kind]: e.target.files?.[0] || null }))}
          data-testid={`settings-import-file-${kind}`}
          className="text-xs flex-1 min-w-[180px]"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          onClick={() => upload(kind, 'csv')}
          disabled={!files[kind] || loading[kind]}
          data-testid={`settings-import-csv-${kind}`}
          className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs h-8"
        >
          <Upload size={12} className="ml-1" /> رفع CSV
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => upload(kind, 'xlsx')}
          disabled={!files[kind] || loading[kind]}
          data-testid={`settings-import-xlsx-${kind}`}
          className="text-xs h-8"
        >
          <Upload size={12} className="ml-1" /> رفع XLSX
        </Button>
        {loading[kind] && <span className="text-xs text-slate-500">جاري الرفع...</span>}
      </div>

      {results[kind] ? (
        <div
          className={`mt-3 rounded-lg border p-2.5 text-xs flex items-start gap-2 ${
            results[kind].ok
              ? 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-900 text-emerald-900 dark:text-emerald-200'
              : 'bg-rose-50 dark:bg-rose-950/30 border-rose-200 dark:border-rose-900 text-rose-900 dark:text-rose-200'
          }`}
          data-testid={`settings-import-result-${kind}`}
        >
          {results[kind].ok ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
          <pre className="text-[10px] whitespace-pre-wrap break-all flex-1 m-0">
            {results[kind].ok ? JSON.stringify(results[kind].data, null, 2) : results[kind].error}
          </pre>
        </div>
      ) : null}
    </Card>
  );

  return (
    <Tabs value={active} onValueChange={setActive} className="w-full" data-testid="settings-import-tabs">
      <TabsList className="grid grid-cols-3 mb-3 bg-slate-100 dark:bg-white/5">
        <TabsTrigger value="customers" data-testid="settings-import-tab-customers">العملاء</TabsTrigger>
        <TabsTrigger value="services" data-testid="settings-import-tab-services">الخدمات</TabsTrigger>
        <TabsTrigger value="parts" data-testid="settings-import-tab-parts">قطع الغيار</TabsTrigger>
      </TabsList>
      <TabsContent value="customers">{PANEL('customers', 'استيراد العملاء', 'name,phone,email,address')}</TabsContent>
      <TabsContent value="services">{PANEL('services', 'استيراد الخدمات', 'name,category,price,duration')}</TabsContent>
      <TabsContent value="parts">{PANEL('parts', 'استيراد قطع الغيار', 'name,code,category,price,quantity,unit')}</TabsContent>
    </Tabs>
  );
};

export default SettingsImportBlock;
