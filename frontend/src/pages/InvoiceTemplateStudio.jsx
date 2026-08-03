import React, { useEffect, useRef, useState, useMemo } from 'react';
import Layout from '../components/Layout';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Type, Image as ImageIcon, User, QrCode, Barcode, Hash } from 'lucide-react';
import axios from 'axios';
import '../styles/invoice-studio.css';
import { resolveBackendBase } from '../utils/backendBase';

const API_URL = `${resolveBackendBase() || ''}/api`.replace('//api','/api');

// A4 canvas size approx at 96dpi
const A4_WIDTH = 794; // px
const A4_HEIGHT = 1123; // px
const GRID_SIZE = 10; // snap grid

const defaultPage = { size: 'A4', orientation: 'portrait', bg: 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)' };

const makeId = () => Math.random().toString(36).slice(2, 9);

const defaultNewElement = (type) => {
  const id = makeId();
  if (type === 'text') return { id, type, name: `نص ${id}`, x: 40, y: 60, w: 300, h: 40, text: 'نص تجريبي', fontSize: 18, bold: false, align: 'right', color: '#111827', rtl: true };
  if (type === 'image') return { id, type, name: `صورة ${id}`, x: 40, y: 20, w: 140, h: 60, src: '', fit: 'contain' };
  if (type === 'itemsTable') return { id, type, name: `جدول البنود ${id}`, x: 30, y: 200, w: 730, h: 240, headerBg: '#f1f5f9', headerColor: '#0f172a', cols: [
    { key: 'description', label: 'المادة', w: 360, visible: true },
    { key: 'qty', label: 'الكمية', w: 80, visible: true },
    { key: 'unit', label: 'الوحدة', w: 80, visible: true },
    { key: 'price', label: 'الفردي', w: 120, visible: true },
    { key: 'total', label: 'الإجمالي', w: 120, visible: true },
    { key: 'additions', label: 'إضافات', w: 100, visible: false },
    { key: 'discount', label: 'خصومات', w: 100, visible: false },
    { key: 'profit', label: 'الربح التجاري', w: 120, visible: false },
    { key: 'tax_name', label: 'اسم الضريبة', w: 120, visible: false },
    { key: 'tax_value', label: 'قيمة الضريبة', w: 120, visible: false },
    { key: 'with_tax', label: 'السعر مع الضريبة', w: 140, visible: false },
    { key: 'warehouse', label: 'المستودع', w: 120, visible: false },
    { key: 'notes', label: 'الملاحظات', w: 160, visible: false },
  ], itemsBinding: 'ITEMS' };
  if (type === 'line') return { id, type, name: `خط ${id}`, x: 30, y: 160, w: 730, h: 2, color: '#e2e8f0' };
  if (type === 'note') return { id, type, name: `ملاحظة ${id}`, x: 30, y: 460, w: 730, h: 80, text: 'ملاحظات:', fontSize: 14, color: '#374151' };
  if (type === 'qr') return { id, type, name: `QR ${id}`, x: 620, y: 40, w: 120, h: 120, binding: 'INVOICE_LINK' };
  return { id, type, name: `${type} ${id}`, x: 40, y: 40, w: 200, h: 40 };
};

const InvoiceTemplateStudio = () => {
  const [templates, setTemplates] = useState([]);
  const [selected, setSelected] = useState(null);
  const [grid, setGrid] = useState([]);
  const [mapping, setMapping] = useState({ WORKSHOP_NAME: '', CUSTOMER_NAME: '', VEHICLE_PLATE: '', TOTAL: '' });
  const [itemsConfig, setItemsConfig] = useState({ anchor: '{{ITEMS}}', columns: { description: '', qty: '', price: '', total: '' } });
  const [importUrl, setImportUrl] = useState('');
  const fileRef = useRef();

  // Designer state
  const [tab, setTab] = useState('designer'); // studio | designer | preview
  const [elements, setElements] = useState([]); // absolute elements on canvas
  const [schema, setSchema] = useState([]); // DB fields: [{name,type}]
  const [page, setPage] = useState(defaultPage);
  const [selectedElId, setSelectedElId] = useState(null);
  const [dragging, setDragging] = useState(null);
  const [resizing, setResizing] = useState(null); // { id, corner, startX, startY, ox, oy, ow, oh }
  const canvasRef = useRef();
  const [zoom, setZoom] = useState(1);

  // Tool panel state (right)
  const [toolTab, setToolTab] = useState('elements'); // elements | columns | fields

  // Field management state
  const [showFieldDialog, setShowFieldDialog] = useState(false);
  const [editingField, setEditingField] = useState(null);

  useEffect(()=>{ loadTemplates(); },[]);

  useEffect(()=>{
    if (selected) {
      setElements(selected.elements || []);
      setSchema(selected.schema || []);
      setPage(selected.page || defaultPage);
      setGrid((selected.preview || []).map(r => r.map(c => (c === null || c === undefined) ? '' : String(c))));
    }
  }, [selected?.id]);

  const loadTemplates = async () => {
    try{
      const res = await axios.get(`${API_URL}/invoice-templates`);
      setTemplates(res.data || []);
    }catch(e){ console.error(e); }
  };

  const importFromUrl = async () => {
    if(!importUrl) return;
    try{
      const res = await axios.post(`${API_URL}/invoice-templates/import-url`, { url: importUrl });
      await loadTemplates();
      setSelected(res.data);
    }catch(e){ alert('فشل الاستيراد من الرابط'); }
  };

  const createBlank = async () => {
    const res = await axios.post(`${API_URL}/invoice-templates/create-blank`, { name: 'قالب فارغ' });
    await loadTemplates();
    setSelected(res.data);
  };

  const handleImport = async (e) => {
    const file = e.target.files[0];
    if(!file) return;
    const form = new FormData();
    form.append('file', file);
    const res = await axios.post(`${API_URL}/invoice-templates/import`, form, { headers:{'Content-Type':'multipart/form-data'} });
    await loadTemplates();
    setSelected(res.data);
  };

  const handleSelect = async (tpl) => { setSelected(tpl); };

  const addRow = () => setGrid([...grid, Array(grid[0]?.length || 10).fill('')]);
  const addCol = () => setGrid(grid.map(r => [...r, '']));

  const saveGrid = async () => {
    if(!selected) return;
    await axios.post(`${API_URL}/invoice-templates/${selected.id}/save-json`, { grid, mapping, items: itemsConfig });
    await axios.post(`${API_URL}/invoice-templates/${selected.id}/auto-save`, { grid, mapping, itemsConfig, elements, schema, page });
    alert('تم الحفظ وإنشاء/تحديث نموذج "فاتوره" تلقائياً');
  };

  const saveMapping = async () => {
    if(!selected) return;
    await axios.post(`${API_URL}/invoice-templates/${selected.id}/update-mapping`, { mapping, items: itemsConfig });
    alert('تم حفظ الربط والحقول');
  };

  const saveAsNamed = async () => {
    if(!selected) return;
    const name = window.prompt('أدخل اسم الفاتورة الجديدة', 'فاتوره');
    if(!name) return;
    const sample = {
      WORKSHOP_NAME: mapping.WORKSHOP_NAME || 'ورشة الخليج',
      CUSTOMER_NAME: mapping.CUSTOMER_NAME || 'عميل',
      VEHICLE_PLATE: mapping.VEHICLE_PLATE || 'س ع د 1234',
      TOTAL: mapping.TOTAL || '0.00',
      ITEMS: [ { description:'-', qty: 1, price: 0, total: 0 } ]
    };
    const res = await axios.post(`${API_URL}/invoice-templates/${selected.id}/save-named`, {
      name,
      grid,
      mapping,
      itemsConfig,
      elements,
      schema,
      page,
      data: sample
    });
    await loadTemplates();
    setSelected(res.data);
    alert('تم إنشاء وحفظ قالب جديد بالاسم المحدد');
  };

  const downloadFilled = async () => {
    if(!selected) return;
    const data = {
      WORKSHOP_NAME: 'ورشة الخليج',
      CUSTOMER_NAME: 'عميل تجريبي',
      VEHICLE_PLATE: 'س ع د 1234',
      TOTAL: '1500.00',
      ITEMS: [
        { description: 'زيت محرك', qty: 1, unit: 'حبة', price: 200, total: 200 },
        { description: 'فلتر زيت', qty: 1, unit: 'حبة', price: 50, total: 50 }
      ]
    };
    const resp = await fetch(`${API_URL}/print/invoice-xlsx`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ templateId: selected.id, data }) });
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'invoice.xlsx'; a.click();
    URL.revokeObjectURL(url);
  };

  // ---------- Designer: elements ops ----------
  const addElement = (type) => {
    const el = defaultNewElement(type);
    setElements(prev => [...prev, el]);
    setSelectedElId(el.id);
    autoSaveDebounced({ elements: [...elements, el] });
  };

  const addBoundText = (binding, label, fontSize=16) => {
    const el = defaultNewElement('text');
    el.text = label; el.binding = binding; el.fontSize = fontSize; el.name = label;
    setElements(prev => [...prev, el]);
    setSelectedElId(el.id);
    autoSaveDebounced({ elements: [...elements, el] });
  };

  const removeElement = (id) => {
    setElements(prev => prev.filter(e => e.id !== id));
    if (selectedElId === id) setSelectedElId(null);
    autoSaveDebounced({ elements: elements.filter(e => e.id !== id) });
  };

  const updateElement = (id, patch) => {
    setElements(prev => prev.map(e => e.id === id ? { ...e, ...patch } : e));
    autoSaveDebounced({ elements: elements.map(e => e.id === id ? { ...e, ...patch } : e) });
  };

  const moveLayer = (id, dir) => {
    setElements(prev => {
      const idx = prev.findIndex(e => e.id === id);
      if (idx === -1) return prev;
      const arr = [...prev];
      const swapWith = dir === 'up' ? Math.max(0, idx - 1) : Math.min(prev.length - 1, idx + 1);
      [arr[idx], arr[swapWith]] = [arr[swapWith], arr[idx]];
      autoSaveDebounced({ elements: arr });
      return arr;
    });
  };

  // ---------- Auto save (debounced) ----------
  const debounceRef = useRef();
  const autoSaveDebounced = (partial={}) => {
    if (!selected) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const payload = { elements, schema, page, ...partial };
    debounceRef.current = setTimeout(async ()=>{
      try{ await axios.post(`${API_URL}/invoice-templates/${selected.id}/auto-save`, payload); } catch(e){ /* silent */ }
    }, 600);
  };

  // ---------- Helper: snap to grid ----------
  const snapToGrid = (val) => Math.round(val / GRID_SIZE) * GRID_SIZE;

  // ---------- Properties panel helpers ----------
  const selEl = useMemo(()=> elements.find(e => e.id === selectedElId) || null, [selectedElId, elements]);

  // ---------- Keyboard: Arrow keys to move selected element ----------
  useEffect(() => {
    const handler = (e) => {
      if (!selectedElId || !selEl) return;
      const step = e.shiftKey ? GRID_SIZE : 1;
      if (e.key === 'ArrowLeft') { e.preventDefault(); updateElement(selectedElId, { x: Math.max(0, selEl.x - step) }); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); updateElement(selectedElId, { x: Math.min(A4_WIDTH - selEl.w, selEl.x + step) }); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); updateElement(selectedElId, { y: Math.max(0, selEl.y - step) }); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); updateElement(selectedElId, { y: Math.min(A4_HEIGHT - selEl.h, selEl.y + step) }); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [selectedElId, selEl]);

  // ---------- Canvas interactions ----------
  // ---------- Canvas interactions ----------
  const onCanvasMouseDown = (e) => {
    if (!canvasRef.current) return;
    const bounds = canvasRef.current.getBoundingClientRect();
    const cx = (e.clientX - bounds.left) / zoom;
    const cy = (e.clientY - bounds.top) / zoom;
    const rev = [...elements].reverse();
    // check for resize handle first (8px area on corners)
    if (selectedElId) {
      const el = elements.find(e => e.id === selectedElId);
      if (el) {
        const handleSize = 8 / zoom;
        const corners = [
          { name: 'se', x: el.x + el.w, y: el.y + el.h },
          { name: 'ne', x: el.x + el.w, y: el.y },
          { name: 'sw', x: el.x, y: el.y + el.h },
          { name: 'nw', x: el.x, y: el.y },
        ];
        for (const c of corners) {
          if (Math.abs(cx - c.x) <= handleSize && Math.abs(cy - c.y) <= handleSize) {
            setResizing({ id: el.id, corner: c.name, startX: cx, startY: cy, ox: el.x, oy: el.y, ow: el.w, oh: el.h });
            return;
          }
        }
      }
    }
    const found = rev.find(el => cx >= el.x && cx <= el.x + el.w && cy >= el.y && cy <= el.y + el.h);
    if (found) {
      setSelectedElId(found.id);
      setDragging({ id: found.id, startX: cx, startY: cy, ox: found.x, oy: found.y });
    } else {
      setSelectedElId(null);
    }
  };
  
  const onCanvasMouseMove = (e) => {
    if (!canvasRef.current) return;
    const bounds = canvasRef.current.getBoundingClientRect();
    const cx = (e.clientX - bounds.left) / zoom;
    const cy = (e.clientY - bounds.top) / zoom;
    
    if (resizing) {
      const dx = cx - resizing.startX;
      const dy = cy - resizing.startY;
      let newX = resizing.ox, newY = resizing.oy, newW = resizing.ow, newH = resizing.oh;
      if (resizing.corner.includes('e')) newW = Math.max(20, resizing.ow + dx);
      if (resizing.corner.includes('w')) { newW = Math.max(20, resizing.ow - dx); newX = resizing.ox + dx; }
      if (resizing.corner.includes('s')) newH = Math.max(20, resizing.oh + dy);
      if (resizing.corner.includes('n')) { newH = Math.max(20, resizing.oh - dy); newY = resizing.oy + dy; }
      // snap
      newX = snapToGrid(newX);
      newY = snapToGrid(newY);
      newW = snapToGrid(newW);
      newH = snapToGrid(newH);
      updateElement(resizing.id, { x: Math.max(0, Math.min(A4_WIDTH - 10, newX)), y: Math.max(0, Math.min(A4_HEIGHT - 10, newY)), w: newW, h: newH });
    } else if (dragging) {
      const dx = cx - dragging.startX;
      const dy = cy - dragging.startY;
      let newX = dragging.ox + dx;
      let newY = dragging.oy + dy;
      // snap to grid
      newX = snapToGrid(newX);
      newY = snapToGrid(newY);
      updateElement(dragging.id, { x: Math.max(0, Math.min(A4_WIDTH - 10, newX)), y: Math.max(0, Math.min(A4_HEIGHT - 10, newY)) });
    }
  };
  
  const onCanvasMouseUp = () => { setDragging(null); setResizing(null); };

  const imageFileInput = useRef();
  const importImageFromFile = () => { if (imageFileInput.current) imageFileInput.current.click(); };
  const onImageFile = (e) => {
    const file = e.target.files?.[0];
    if (!file || !selEl) return;
    const reader = new FileReader();
    reader.onload = () => { updateElement(selEl.id, { src: reader.result }); };
    reader.readAsDataURL(file);
  };

  // ---------- Apply design to grid (Enhanced Algorithm) ----------
  const applyDesignToGrid = async () => {
    if (!selected) return;
    // Better cell sizing based on A4 dimensions
    const cellW = Math.round(A4_WIDTH / 8);  // ~99px per col (8 columns for A4)
    const cellH = 28;  // Slightly smaller for better fit
    let g = grid && grid.length ? grid.map(r => [...r]) : [];
    const ensureSize = (rows, cols) => {
      const curRows = g.length;
      const curCols = g[0]?.length || 0;
      for (let r=curRows; r<rows; r++) g.push(Array(Math.max(cols, curCols||10)).fill(''));
      for (let r=0; r<g.length; r++) {
        for (let c=g[r].length; c<cols; c++) g[r].push('');
      }
    };
    
    // Auto-generate mapping from bound elements
    const newMapping = { ...mapping };
    
    // Sort elements by Y position (top to bottom)
    const sortedElements = [...elements].sort((a, b) => a.y - b.y);
    
    // Place all elements with intelligent positioning
    sortedElements.forEach(el => {
      if (el.type === 'text') {
        const r = Math.max(0, Math.round(el.y / cellH));
        const c = Math.max(0, Math.round(el.x / cellW));
        ensureSize(r+1, c+1);
        
        if (el.binding) {
          const placeholder = `{{${el.binding}}}`;
          g[r][c] = placeholder;
          // Auto-update mapping with cell reference
          const cellRef = String.fromCharCode(65 + c) + (r + 1);
          newMapping[el.binding] = cellRef;
        } else {
          g[r][c] = el.text || '';
        }
      }
      // Handle image elements (mark position)
      else if (el.type === 'image') {
        const r = Math.max(0, Math.round(el.y / cellH));
        const c = Math.max(0, Math.round(el.x / cellW));
        ensureSize(r+1, c+1);
        if (!g[r][c]) g[r][c] = '[صورة]';
      }
      // Handle QR codes
      else if (el.type === 'qr') {
        const r = Math.max(0, Math.round(el.y / cellH));
        const c = Math.max(0, Math.round(el.x / cellW));
        ensureSize(r+1, c+1);
        if (el.binding) {
          g[r][c] = `{{${el.binding}}}`;
        } else {
          g[r][c] = '[QR]';
        }
      }
    });
    
    // Handle items table with better column mapping
    const table = elements.find(e => e.type==='itemsTable');
    if (table) {
      const r = Math.max(0, Math.round(table.y / cellH));
      const c = Math.max(0, Math.round(table.x / cellW));
      const visibleCols = (table.cols||[]).filter(col=>col.visible!==false);
      const colsCount = Math.max(1, visibleCols.length);
      ensureSize(r+3, c+colsCount); // +3 for header + anchor + template row
      
      // Place header labels
      visibleCols.forEach((col, i) => {
        g[r][c+i] = col.label || col.key;
      });
      
      // Place anchor
      g[r+1][c] = '{{ITEMS}}';
      
      // Place template row
      const newItemsCols = {};
      visibleCols.forEach((col, i) => {
        const key = col.key || `col${i+1}`;
        g[r+2][c+i] = `{{ITEMS.${key}}}`;
        // Auto-update itemsConfig columns
        const cellCol = String.fromCharCode(65 + c + i);
        newItemsCols[key] = cellCol;
      });
      
      // Update itemsConfig
      const newItemsConfig = {
        anchor: `{{ITEMS}}`,
        columns: newItemsCols
      };
      setItemsConfig(newItemsConfig);
    }
    
    setGrid(g);
    setMapping(newMapping);
    
    try{
      await axios.post(`${API_URL}/invoice-templates/${selected.id}/save-json`, { grid: g, mapping: newMapping, items: itemsConfig });
      await axios.post(`${API_URL}/invoice-templates/${selected.id}/auto-save`, { grid: g, mapping: newMapping, itemsConfig, elements, schema, page });
      alert('✅ تم تطبيق التصميم على الشبكة وتحديث الربط تلقائياً');
    }catch(e){ alert('❌ تعذر تطبيق التصميم على الشبكة'); }
  };

  // ---------- Columns panel actions ----------
  const toggleColumn = (key) => {
    const table = elements.find(e=>e.type==='itemsTable');
    if (!table) return;
    const cols = (table.cols||[]).map(c => c.key===key? {...c, visible: !(c.visible!==false)}: c);
    updateElement(table.id, { cols });
  };

  // ---------- Field Management ----------
  const addField = () => {
    setEditingField({ name: '', type: 'text', label: '', validation: '' });
    setShowFieldDialog(true);
  };

  const editField = (field) => {
    setEditingField({ ...field });
    setShowFieldDialog(true);
  };

  const saveField = () => {
    if (!editingField || !editingField.name) {
      alert('يرجى إدخال اسم الحقل');
      return;
    }
    const existing = schema.find(f => f.name === editingField.name);
    let newSchema;
    if (existing) {
      // Update existing
      newSchema = schema.map(f => f.name === editingField.name ? editingField : f);
    } else {
      // Add new
      newSchema = [...schema, editingField];
    }
    setSchema(newSchema);
    autoSaveDebounced({ schema: newSchema });
    setShowFieldDialog(false);
    setEditingField(null);
  };

  const deleteField = (fieldName) => {
    if (!window.confirm(`هل تريد حذف الحقل "${fieldName}"؟`)) return;
    const newSchema = schema.filter(f => f.name !== fieldName);
    setSchema(newSchema);
    autoSaveDebounced({ schema: newSchema });
  };

  return (
    <Layout>
      <div className="container mx-auto p-3 md:p-6" dir="rtl">
        {/* Sticky header for mobile */}
        <div className="sticky top-0 z-50 bg-white shadow-md p-2 mb-2 md:static md:shadow-none md:p-0 md:mb-0 flex items-center justify-between md:hidden">
          <h2 className="text-sm font-bold">استوديو القوالب</h2>
          <div className="flex gap-1">
            <Button size="sm" onClick={saveGrid} className="bg-blue-600 hover:bg-blue-700 text-xs">حفظ</Button>
            <Button size="sm" onClick={downloadFilled} className="bg-emerald-600 hover:bg-emerald-700 text-xs">توليد</Button>
          </div>
        </div>
        
        <div className="flex items-center justify-between mb-4 md:mb-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold">استوديو قوالب الفواتير (Excel)</h1>
            {selected && (
              <div className="mt-1 text-sm">
                <span className={`px-2 py-1 rounded ${selected.isDefault ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'}`}>
                  {selected.isDefault ? 'القالب الافتراضي' : 'قالب عادي'}
                </span>
                <span className="mx-2 text-slate-400">•</span>
                <span className="text-slate-500">الصيغة: {selected.format?.toUpperCase()}</span>
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <label>
              <Button asChild className="bg-green-600 hover:bg-green-700 cursor-pointer"><span>استيراد قالب</span></Button>
              <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv,.html,.htm,.docx,.pdf" className="hidden" onChange={handleImport} />
            </label>
            <div className="hidden md:flex items-center gap-2">
              <Input value={importUrl} onChange={e=>setImportUrl(e.target.value)} placeholder="أدخل رابط نموذج للاستيراد" className="w-60" />
              <Button onClick={importFromUrl} variant="outline">استيراد من رابط</Button>
              <Button onClick={createBlank} variant="outline">قالب فارغ</Button>
            </div>
            <Button onClick={saveGrid} className="bg-blue-600 hover:bg-blue-700">حفظ كـ Excel</Button>
            <Button onClick={saveMapping} className="bg-purple-600 hover:bg-purple-700">حفظ الربط</Button>
            <Button onClick={saveAsNamed} className="bg-amber-600 hover:bg-amber-700">حفظ باسم فاتوره</Button>
            <Button onClick={downloadFilled} className="bg-emerald-600 hover:bg-emerald-700">توليد فاتورة</Button>
          </div>
        </div>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="mb-4">
            <TabsTrigger value="designer">مصمم A4</TabsTrigger>
            <TabsTrigger value="preview">معاينة الطباعة</TabsTrigger>
            <TabsTrigger value="studio">محرر الشبكة</TabsTrigger>
          </TabsList>

          {/* Designer A4 */}
          <TabsContent value="designer">
            {!selected && (
              <Card className="mb-6"><CardContent className="p-4 text-slate-600">اختر قالبًا أو أنشئ قالبًا فارغًا للبدء.</CardContent></Card>
            )}
            {selected && (
              <div className="grid grid-cols-12 gap-3 md:gap-4">
                {/* Right Tool Panel to match provided design */}
                <div className="order-2 md:order-3 col-span-12 md:col-span-3">
                  <Card className="bg-gradient-to-b from-slate-50 to-white sticky top-2 max-h-[88vh] overflow-auto">
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <CardTitle>
                          {toolTab==='elements'? 'العناصر المتاحة' : toolTab==='columns'? 'كل الأعمدة' : 'حقول القاعدة'}
                        </CardTitle>
                        <div className="flex gap-1">
                          <Button size="sm" variant={toolTab==='elements'? 'default':'outline'} onClick={()=>setToolTab('elements')}>العناصر</Button>
                          <Button size="sm" variant={toolTab==='columns'? 'default':'outline'} onClick={()=>setToolTab('columns')}>الأعمدة</Button>
                          <Button size="sm" variant={toolTab==='fields'? 'default':'outline'} onClick={()=>setToolTab('fields')}>الحقول</Button>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      {toolTab==='elements' && (
                        <div className="space-y-2">
                          <ToolItem icon={<Type/>} label="نص" onClick={()=>addElement('text')} />
                          <ToolItem icon={<ImageIcon/>} label="صورة" onClick={()=>addElement('image')} />
                          <ToolItem icon={<Type/>} label="العنوان الرئيسي" onClick={()=>addBoundText('TITLE','العنوان الرئيسي',22)} />
                          <ToolItem icon={<User/>} label="العميل" onClick={()=>addBoundText('CUSTOMER_NAME','العميل')} />
                          <ToolItem icon={<Hash/>} label="الرقم الضريبي/عميل" onClick={()=>addBoundText('CUSTOMER_TAX','الرقم الضريبي/عميل')} />
                          <ToolItem icon={<Barcode/>} label="سجل تجاري/عميل" onClick={()=>addBoundText('CUSTOMER_CR','سجل تجاري/عميل')} />
                          <ToolItem icon={<Type/>} label="إيميل/عميل" onClick={()=>addBoundText('CUSTOMER_EMAIL','إيميل/عميل')} />
                          <ToolItem icon={<Hash/>} label="الرقم الضريبي/شركة" onClick={()=>addBoundText('COMPANY_TAX','الرقم الضريبي/شركة')} />
                          <ToolItem icon={<Barcode/>} label="سجل تجاري/شركة" onClick={()=>addBoundText('COMPANY_CR','سجل تجاري/شركة')} />
                          <ToolItem icon={<QrCode/>} label="كود QR" onClick={()=>addElement('qr')} />
                          <ToolItem icon={<Type/>} label="رقم الفاتورة" onClick={()=>addBoundText('INVOICE_NO','رقم الفاتورة')} />
                          <div className="pt-2 border-t mt-2">
                            <ToolItem icon={<Type/>} label="جدول البنود" onClick={()=>addElement('itemsTable')} />
                          </div>
                        </div>
                      )}
                      {toolTab==='columns' && (
                        <div className="space-y-2">
                          {(elements.find(e=>e.type==='itemsTable')?.cols || []).map(col => (
                            <div key={col.key} className="flex items-center justify-between p-2 rounded bg-slate-50">
                              <div className="flex items-center gap-2">
                                <span className="w-6 h-1 bg-slate-400 rounded" />
                                <span>{col.label}</span>
                              </div>
                              <Button size="sm" variant={col.visible!==false? 'default':'outline'} onClick={()=>toggleColumn(col.key)}>
                                {col.visible!==false? 'إخفاء' : 'إظهار'}
                              </Button>
                            </div>
                          ))}
                          {!(elements.find(e=>e.type==='itemsTable')) && (
                            <div className="text-xs text-slate-500">أضف &quot;جدول البنود&quot; أولاً لعرض الأعمدة.</div>
                          )}
                        </div>
                      )}
                      {toolTab==='fields' && (
                        <div className="space-y-3">
                          <Button size="sm" className="w-full" onClick={addField}>+ إضافة حقل جديد</Button>
                          <div className="space-y-2">
                            {schema.map((field, idx) => (
                              <div key={idx} className="p-3 border rounded bg-white hover:bg-slate-50">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="font-semibold text-sm">{field.label || field.name}</span>
                                  <div className="flex gap-1">
                                    <Button size="sm" variant="ghost" onClick={()=>editField(field)}>✏️</Button>
                                    <Button size="sm" variant="ghost" onClick={()=>deleteField(field.name)}>🗑️</Button>
                                  </div>
                                </div>
                                <div className="text-xs text-slate-600">
                                  <div>الاسم: {field.name}</div>
                                  <div>النوع: {field.type}</div>
                                  {field.validation && <div>التحقق: {field.validation}</div>}
                                </div>
                              </div>
                            ))}
                            {schema.length === 0 && (
                              <div className="text-sm text-slate-500 text-center py-4">
                                لا توجد حقول بعد. اضغط &quot;إضافة حقل جديد&quot; للبدء.
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>

                {/* Canvas */}
                <div className="order-1 md:order-2 col-span-12 md:col-span-6">
                  <Card className="overflow-hidden">
                    <CardHeader>
                      <CardTitle className="flex items-center justify-between">
                        <span>لوح A4</span>
                        <div className="flex items-center gap-2">
                          <Label>تكبير</Label>
                          <input type="range" min="0.6" max="1.4" step="0.05" value={zoom} onChange={(e)=>setZoom(parseFloat(e.target.value))} />
                          <Button size="sm" onClick={applyDesignToGrid}>تطبيق التصميم على الشبكة</Button>
                        </div>
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="w-full flex justify-center">
                        <div
                          ref={canvasRef}
                          onMouseDown={onCanvasMouseDown}
                          onMouseMove={onCanvasMouseMove}
                          onMouseUp={onCanvasMouseUp}
                          className="relative shadow-2xl border bg-white"
                          style={{ width: A4_WIDTH*zoom, height: A4_HEIGHT*zoom, background: page.bg, transformOrigin:'top left' }}
                        >
                          <div className="absolute inset-0" style={{ backgroundImage:'linear-gradient(to right, rgba(0,0,0,0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(0,0,0,0.03) 1px, transparent 1px)', backgroundSize:`20px 20px` }} />
                          {elements.map(el => (
                            <div key={el.id}
                              className={`absolute ${selectedElId===el.id? 'ring-2 ring-blue-500': 'ring-1 ring-slate-200'}`}
                              style={{ left: el.x*zoom, top: el.y*zoom, width: el.w*zoom, height: el.h*zoom, background: el.type==='note'? '#fff' : 'transparent' }}
                              onMouseDown={(e)=>{ e.stopPropagation(); setSelectedElId(el.id); }}
                            >
                              {el.type==='text' && (
                                <div className="w-full h-full p-2" style={{ color: el.color, fontWeight: el.bold? '700':'400', fontSize: (el.fontSize||16)*zoom, textAlign: el.align||'right', direction: el.rtl? 'rtl':'ltr' }}>
                                  {el.text || 'نص'}{el.binding? ` — {{${el.binding}}}`: ''}
                                </div>
                              )}
                              {el.type==='image' && (
                                <div className="w-full h-full bg-white/40 flex items-center justify-center">
                                  {el.src? (<img alt="img" src={el.src} className="w-full h-full object-contain" />) : (<span className="text-xs text-slate-500">صورة</span>)}
                                </div>
                              )}
                              {el.type==='itemsTable' && (
                                <div className="w-full h-full bg-white">
                                  <div className="flex w-full" style={{ background: el.headerBg}}>
                                    {(el.cols||[]).filter(c=>c.visible!==false).map((c,idx)=> (
                                      <div key={idx} className="px-2 py-1 text-xs font-semibold" style={{ width: c.w*zoom, color: el.headerColor}}>{c.label}</div>
                                    ))}
                                  </div>
                                  <div className="p-2 text-xs text-slate-600">مصدر البنود: {el.itemsBinding}</div>
                                </div>
                              )}
                              {el.type==='line' && (<div className="w-full h-full" style={{ background: el.color }} />)}
                              {el.type==='note' && (<div className="w-full h-full p-2 text-sm" style={{ color: el.color }}>{el.text}</div>)}
                              {el.type==='qr' && (
                                <div className="w-full h-full bg-white flex items-center justify-center border">
                                  <span className="text-xs text-slate-700">QR • {`{${el.binding}}`}</span>
                                </div>
                              )}
                              {/* Resize handles for selected element */}
                              {selectedElId === el.id && (
                                <>
                                  <div className="absolute -top-1 -left-1 w-2 h-2 bg-blue-500 rounded-full cursor-nw-resize" />
                                  <div className="absolute -top-1 -right-1 w-2 h-2 bg-blue-500 rounded-full cursor-ne-resize" />
                                  <div className="absolute -bottom-1 -left-1 w-2 h-2 bg-blue-500 rounded-full cursor-sw-resize" />
                                  <div className="absolute -bottom-1 -right-1 w-2 h-2 bg-blue-500 rounded-full cursor-se-resize" />
                                </>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* Left properties / layers */}
                <div className="order-3 md:order-1 col-span-12 md:col-span-3 space-y-3">
                  <Card>
                    <CardHeader><CardTitle>خصائص العنصر</CardTitle></CardHeader>
                    <CardContent>
                      {!selEl && <div className="text-slate-500 text-sm">حدّد عنصراً من اللوح</div>}
                      {selEl && (
                        <div className="space-y-2">
                          <Input value={selEl.name||''} onChange={(e)=>updateElement(selEl.id, { name: e.target.value })} placeholder="اسم العنصر" />
                          <div className="grid grid-cols-4 gap-2">
                            <div><Label>X</Label><Input type="number" value={selEl.x} onChange={(e)=>updateElement(selEl.id, { x: parseInt(e.target.value||0) })} /></div>
                            <div><Label>Y</Label><Input type="number" value={selEl.y} onChange={(e)=>updateElement(selEl.id, { y: parseInt(e.target.value||0) })} /></div>
                            <div><Label>W</Label><Input type="number" value={selEl.w} onChange={(e)=>updateElement(selEl.id, { w: parseInt(e.target.value||0) })} /></div>
                            <div><Label>H</Label><Input type="number" value={selEl.h} onChange={(e)=>updateElement(selEl.id, { h: parseInt(e.target.value||0) })} /></div>
                          </div>
                          {selEl.type==='text' && (
                            <>
                              <Textarea value={selEl.text||''} onChange={(e)=>updateElement(selEl.id,{text:e.target.value})} placeholder="النص" />
                              <div className="grid grid-cols-3 gap-2">
                                <div><Label>حجم</Label><Input type="number" value={selEl.fontSize||16} onChange={(e)=>updateElement(selEl.id,{fontSize:parseInt(e.target.value||16)})} /></div>
                                <div><Label>محاذاة</Label>
                                  <select className="border rounded px-2 py-1 w-full" value={selEl.align||'right'} onChange={(e)=>updateElement(selEl.id,{align:e.target.value})}>
                                    <option value="right">يمين</option>
                                    <option value="center">وسط</option>
                                    <option value="left">يسار</option>
                                  </select>
                                </div>
                                <div><Label>لون</Label><Input type="color" value={selEl.color||'#111827'} onChange={(e)=>updateElement(selEl.id,{color:e.target.value})} /></div>
                              </div>
                              <div className="flex items-center gap-2">
                                <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={!!selEl.bold} onChange={(e)=>updateElement(selEl.id,{bold:e.target.checked})} />عريض</label>
                                <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={!!selEl.rtl} onChange={(e)=>updateElement(selEl.id,{rtl:e.target.checked})} />RTL</label>
                              </div>
                              <div>
                                <Label>ربط بحقل</Label>
                                <select className="border rounded px-2 py-1 w-full" value={selEl.binding||''} onChange={(e)=>updateElement(selEl.id,{binding:e.target.value})}>
                                  <option value="">— غير مربوط —</option>
                                  {schema.map((f,i)=>(<option key={i} value={f.name}>{`{{${f.name}}}`}</option>))}
                                  {['CUSTOMER_NAME','VEHICLE_PLATE','INVOICE_NO','DATE','TOTAL','TITLE','CUSTOMER_TAX','CUSTOMER_CR','CUSTOMER_EMAIL','COMPANY_TAX','COMPANY_CR','INVOICE_LINK'].map(k=>(
                                    <option key={k} value={k}>{`{{${k}}}`}</option>
                                  ))}
                                </select>
                              </div>
                            </>
                          )}
                          {selEl.type==='image' && (
                            <>
                              <Label>رابط الصورة/الشعار</Label>
                              <Input value={selEl.src||''} onChange={(e)=>updateElement(selEl.id,{src:e.target.value})} placeholder="https://..." />
                              <div className="flex items-center gap-2">
                                <Button size="sm" variant="outline" onClick={importImageFromFile}>رفع صورة</Button>
                                <input ref={imageFileInput} type="file" accept="image/*" className="hidden" onChange={onImageFile} />
                              </div>
                            </>
                          )}
                          {selEl.type==='itemsTable' && (
                            <>
                              <div className="grid grid-cols-2 gap-2">
                                <div><Label>لون الهيدر</Label><Input type="color" value={selEl.headerBg||'#f1f5f9'} onChange={(e)=>updateElement(selEl.id,{headerBg:e.target.value})} /></div>
                                <div><Label>لون النص</Label><Input type="color" value={selEl.headerColor||'#0f172a'} onChange={(e)=>updateElement(selEl.id,{headerColor:e.target.value})} /></div>
                              </div>
                              <div className="mt-2 text-xs text-slate-500">تحكم بالأعمدة من لوحة &quot;الأعمدة&quot; على اليمين.</div>
                            </>
                          )}
                          <div className="pt-2 border-t mt-2 flex items-center gap-2">
                            <Button size="sm" variant="outline" onClick={()=>moveLayer(selEl.id,'up')}>↑ رفع</Button>
                            <Button size="sm" variant="outline" onClick={()=>moveLayer(selEl.id,'down')}>↓ خفض</Button>
                            <Button size="sm" variant="destructive" onClick={()=>removeElement(selEl.id)}>حذف</Button>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader><CardTitle>القوالب</CardTitle></CardHeader>
                    <CardContent>
                      <div className="space-y-2 max-h-[40vh] overflow-auto">
                        {templates.map(t => (
                          <div key={t.id} className={`p-3 border rounded cursor-pointer ${selected?.id===t.id?'bg-blue-50 border-blue-300':'hover:bg-slate-50'}`} onClick={()=>handleSelect(t)}>
                            <div className="font-semibold">{t.name}</div>
                            <div className="text-xs text-slate-500">{t.format?.toUpperCase()} • {t.fields?.length||0} حقول</div>
                          </div>
                        ))}
                        {templates.length===0 && (<div className="text-sm text-slate-500">لا توجد قوالب بعد، قم بالاستيراد أولاً.</div>)}
                        {templates.length>0 && (
                          <div className="mt-2 text-right">
                            <Button variant="destructive" onClick={async ()=>{ if(!selected){ alert('اختر قالباً أولاً'); return; } const mode = window.prompt('اكتب soft للأرشفة أو hard للحذف النهائي', 'soft'); if(!mode) return; try{ if(mode==='hard'){ await axios.delete(`${API_URL}/invoice-templates/${selected.id}/hard`);} else { await axios.delete(`${API_URL}/invoice-templates/${selected.id}`);} setSelected(null); await loadTemplates(); } catch(e){ alert(e?.response?.data?.detail || 'تعذر تنفيذ الحذف'); } }}>حذف القالب المحدد</Button>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            )}
          </TabsContent>

          {/* Print Preview */}
          <TabsContent value="preview">
            {!selected && (
              <Card><CardContent className="p-4 text-slate-600">اختر قالبًا لمعاينة الطباعة.</CardContent></Card>
            )}
            {selected && (
              <Card>
                <CardHeader>
                  <CardTitle>معاينة الطباعة</CardTitle>
                  <p className="text-sm text-slate-600">معاينة A4 للعناصر المصممة (بدون بيانات)</p>
                </CardHeader>
                <CardContent>
                  <div className="flex justify-center bg-slate-100 p-6 rounded-lg">
                    <div 
                      className="shadow-2xl bg-white relative overflow-hidden"
                      style={{ 
                        width: `${A4_WIDTH}px`, 
                        height: `${A4_HEIGHT}px`,
                        background: page.bg || '#ffffff',
                        transform: 'scale(0.7)',
                        transformOrigin: 'top center'
                      }}
                    >
                      {elements.map(el => (
                        <div 
                          key={el.id}
                          className="absolute border border-dashed border-slate-300"
                          style={{ 
                            left: el.x, 
                            top: el.y, 
                            width: el.w, 
                            height: el.h,
                          }}
                        >
                          {el.type==='text' && (
                            <div 
                              className="w-full h-full flex items-center px-2"
                              style={{ 
                                fontSize: el.fontSize || 16,
                                fontWeight: el.bold ? 'bold' : 'normal',
                                textAlign: el.align || 'right',
                                color: el.color || '#111827',
                                direction: el.rtl ? 'rtl' : 'ltr'
                              }}
                            >
                              {el.text || ''}
                              {el.binding && <span className="text-xs text-blue-600 mr-1">[{el.binding}]</span>}
                            </div>
                          )}
                          {el.type==='image' && (
                            <div className="w-full h-full flex items-center justify-center bg-slate-50">
                              {el.src ? (
                                <img src={el.src} alt="preview" className="max-w-full max-h-full object-contain" />
                              ) : (
                                <ImageIcon className="w-8 h-8 text-slate-400" />
                              )}
                            </div>
                          )}
                          {el.type==='itemsTable' && (
                            <div className="w-full h-full overflow-hidden text-xs">
                              <div className="flex" style={{ background: el.headerBg, color: el.headerColor }}>
                                {(el.cols||[]).filter(c=>c.visible!==false).map((col,i)=>(
                                  <div key={i} className="px-1 py-1 border-l border-white" style={{ width: `${col.w||80}px` }}>
                                    {col.label}
                                  </div>
                                ))}
                              </div>
                              <div className="text-slate-500 p-2 text-center">جدول البنود (معاينة)</div>
                            </div>
                          )}
                          {el.type==='qr' && (
                            <div className="w-full h-full bg-slate-100 flex items-center justify-center border">
                              <QrCode className="w-12 h-12 text-slate-400" />
                            </div>
                          )}
                          {el.type==='line' && (
                            <div className="w-full h-full" style={{ background: el.color }} />
                          )}
                          {el.type==='note' && (
                            <div className="w-full h-full p-2 text-sm overflow-auto" style={{ color: el.color }}>
                              {el.text}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="mt-4 text-center text-sm text-slate-600">
                    للطباعة الفعلية، استخدم زر &quot;توليد فاتورة&quot; من الأعلى
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Grid editor */}
          <TabsContent value="studio">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card className="lg:col-span-1">
                <CardHeader><CardTitle>القوالب</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-2 max-h-[60vh] overflow-auto">
                    {templates.map(t => (
                      <div key={t.id} className={`p-3 border rounded cursor-pointer ${selected?.id===t.id?'bg-blue-50 border-blue-300':'hover:bg-slate-50'}`} onClick={()=>handleSelect(t)}>
                        <div className="font-semibold">{t.name}</div>
                        <div className="text-xs text-slate-500">{t.format?.toUpperCase()} • {t.fields?.length||0} حقول</div>
                      </div>
                    ))}
                    {templates.length===0 && (
                      <div className="text-sm text-slate-500">لا توجد قوالب بعد، قم بالاستيراد أولاً.</div>
                    )}
                    {templates.length>0 && (
                      <div className="mt-4 text-right">
                        <Button variant="destructive" onClick={async ()=>{ if(!selected){ alert('اختر قالباً أولاً'); return; } const mode = window.prompt('اكتب soft للأرشفة أو hard للحذف النهائي', 'soft'); if(!mode) return; try{ if(mode==='hard'){ await axios.delete(`${API_URL}/invoice-templates/${selected.id}/hard`);} else { await axios.delete(`${API_URL}/invoice-templates/${selected.id}`);} setSelected(null); await loadTemplates(); } catch(e){ alert(e?.response?.data?.detail || 'تعذر تنفيذ الحذف'); } }}>حذف القالب المحدد</Button>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card className="lg:col-span-2">
                <CardHeader><CardTitle>إعدادات الحقول وربط البنود</CardTitle></CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label>WORKSHOP_NAME</Label>
                      <Input value={mapping.WORKSHOP_NAME} onChange={e=>setMapping({...mapping, WORKSHOP_NAME: e.target.value})} placeholder="A1 أو {{WORKSHOP_NAME}}" />
                    </div>
                    <div>
                      <Label>CUSTOMER_NAME</Label>
                      <Input value={mapping.CUSTOMER_NAME} onChange={e=>setMapping({...mapping, CUSTOMER_NAME: e.target.value})} placeholder="B3 أو {{CUSTOMER_NAME}}" />
                    </div>
                    <div>
                      <Label>VEHICLE_PLATE</Label>
                      <Input value={mapping.VEHICLE_PLATE} onChange={e=>setMapping({...mapping, VEHICLE_PLATE: e.target.value})} placeholder="C5 أو {{VEHICLE_PLATE}}" />
                    </div>
                    <div>
                      <Label>TOTAL</Label>
                      <Input value={mapping.TOTAL} onChange={e=>setMapping({...mapping, TOTAL: e.target.value})} placeholder="E10 أو {{TOTAL}}" />
                    </div>
                  </div>

                  <div className="mt-4">
                    <Label>مرساة البنود (صف يحتوي {'{{ITEMS}}'})</Label>
                    <Input value={itemsConfig.anchor} onChange={e=>setItemsConfig({...itemsConfig, anchor: e.target.value})} />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-3">
                    <div>
                      <Label>عمود الوصف</Label>
                      <Input value={itemsConfig.columns.description} onChange={e=>setItemsConfig({...itemsConfig, columns:{...itemsConfig.columns, description: e.target.value}})} placeholder="مثل D" />
                    </div>
                    <div>
                      <Label>عمود الكمية</Label>
                      <Input value={itemsConfig.columns.qty} onChange={e=>setItemsConfig({...itemsConfig, columns:{...itemsConfig.columns, qty: e.target.value}})} placeholder="مثل E" />
                    </div>
                    <div>
                      <Label>عمود السعر</Label>
                      <Input value={itemsConfig.columns.price} onChange={e=>setItemsConfig({...itemsConfig, columns:{...itemsConfig.columns, price: e.target.value}})} placeholder="مثل F" />
                    </div>
                    <div>
                      <Label>عمود الإجمالي</Label>
                      <Input value={itemsConfig.columns.total} onChange={e=>setItemsConfig({...itemsConfig, columns:{...itemsConfig.columns, total: e.target.value}})} placeholder="مثل G" />
                    </div>
                  </div>
                  <div className="mt-4">
                    <Button onClick={async ()=>{ await axios.post(`${API_URL}/invoice-templates/${selected.id}/update-mapping`, { mapping, items: itemsConfig }); alert('تم حفظ الربط'); }} className="bg-purple-600 hover:bg-purple-700">حفظ الربط</Button>
                  </div>
                </CardContent>
              </Card>

              <Card className="lg:col-span-2">
                <CardHeader><CardTitle>المحرّر الشبكي (مبسّط)</CardTitle></CardHeader>
                <CardContent>
                  <div className="overflow-auto border rounded">
                    <table className="min-w-full text-sm">
                      <tbody>
                        {grid.map((row, rIdx) => (
                          <tr key={rIdx}>
                            {row.map((cell, cIdx) => (
                              <td key={cIdx} className="border p-1">
                                <input className="w-40 px-1 text-sm" value={cell} onChange={(e)=>{ const g = [...grid]; g[rIdx][cIdx] = e.target.value; setGrid(g); }} />
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex gap-2 mt-3">
                    <Button variant="outline" onClick={addRow}>+ صف</Button>
                    <Button variant="outline" onClick={addCol}>+ عمود</Button>
                  </div>
                  <div className="mt-4">
                    <Label>ملاحظات القالب</Label>
                    <Textarea placeholder="اكتب ملاحظات للفرق..."/>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>

        {/* Field Management Dialog */}
        {showFieldDialog && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={()=>setShowFieldDialog(false)}>
            <div className="bg-white p-6 rounded-lg w-full max-w-md" onClick={(e)=>e.stopPropagation()}>
              <h3 className="text-xl font-bold mb-4">{editingField?.name && schema.find(f=>f.name===editingField.name) ? 'تعديل حقل' : 'إضافة حقل جديد'}</h3>
              <div className="space-y-3">
                <div>
                  <Label>اسم الحقل (بالإنجليزية)</Label>
                  <Input 
                    value={editingField?.name || ''} 
                    onChange={e=>setEditingField({...editingField, name: e.target.value})}
                    placeholder="CUSTOMER_NAME"
                  />
                </div>
                <div>
                  <Label>التسمية (بالعربية)</Label>
                  <Input 
                    value={editingField?.label || ''} 
                    onChange={e=>setEditingField({...editingField, label: e.target.value})}
                    placeholder="اسم العميل"
                  />
                </div>
                <div>
                  <Label>نوع الحقل</Label>
                  <select 
                    className="w-full p-2 border rounded"
                    value={editingField?.type || 'text'}
                    onChange={e=>setEditingField({...editingField, type: e.target.value})}
                  >
                    <option value="text">نص</option>
                    <option value="number">رقم</option>
                    <option value="date">تاريخ</option>
                    <option value="email">إيميل</option>
                    <option value="phone">هاتف</option>
                    <option value="textarea">نص طويل</option>
                  </select>
                </div>
                <div>
                  <Label>قواعد التحقق (اختياري)</Label>
                  <Input 
                    value={editingField?.validation || ''} 
                    onChange={e=>setEditingField({...editingField, validation: e.target.value})}
                    placeholder="required, min:3, max:50"
                  />
                </div>
              </div>
              <div className="flex gap-2 mt-4">
                <Button onClick={saveField} className="flex-1">حفظ</Button>
                <Button onClick={()=>setShowFieldDialog(false)} variant="outline" className="flex-1">إلغاء</Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

const ToolItem = ({ icon, label, onClick }) => (
  <button onClick={onClick} className="w-full p-3 rounded-lg bg-slate-100 hover:bg-slate-200 flex items-center justify-between">
    <div className="flex items-center gap-2">
      <span className="text-slate-700">{label}</span>
    </div>
    <div className="text-slate-500">{icon}</div>
  </button>
);

export default InvoiceTemplateStudio;