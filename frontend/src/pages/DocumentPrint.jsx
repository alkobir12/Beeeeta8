import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { 
  Plus, Trash2, FileText, Download, Eye, Loader2, Printer,
  Receipt, ClipboardList, FileCheck, Car, Save, Check, Share2
} from 'lucide-react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import { downloadPDF } from '../utils/pdfGenerator'; // New utility
import { getWhatsAppLink } from '../utils/constants';
import { resolveBackendBase } from '../utils/backendBase';

const API_URL = process.env.NODE_ENV === 'production'
  ? '/api'
  : `${resolveBackendBase()}/api`.replace('//api', '/api');

const DocumentPrint = () => {
  const { i18n } = useTranslation();
  const isArabic = i18n.language === 'ar';
  const [searchParams] = useSearchParams();
  const previewRef = useRef(null);
  const pdfIframeRef = useRef(null);
  const autoRefreshRef = useRef(false);
  
  const [loading, setLoading] = useState(false);
  const [generatingPdf, setGeneratingPdf] = useState(false);
  const [previewHtml, setPreviewHtml] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [workshopSettings, setWorkshopSettings] = useState(null);
  const [workshopLoaded, setWorkshopLoaded] = useState(false);
  const [pdfSourceHtml, setPdfSourceHtml] = useState('');
  
  // نوع المستند من URL أو افتراضي
  const initialType = searchParams.get('type') || 'invoice';
  const vehicleId = searchParams.get('vehicleId');
  const visitId = searchParams.get('visitId');
  const operationId = searchParams.get('operationId');
  const invoiceId = searchParams.get('invoiceId');
  const autoPrint = searchParams.get('autoPrint') === '1';
  const autoWhatsApp = searchParams.get('autoWhatsApp') === '1';
  const autoClose = searchParams.get('autoClose') === '1';
  const autoActionRef = useRef(false);
  
  const [docType, setDocType] = useState(initialType);
  
  const [formData, setFormData] = useState({
    workshop: {
      name: '',
      name_en: '',
      address: '',
      phone: '',
      email: '',
      website: '',
      commercial_register: ''
    },
    customer: {
      name: '',
      company: '',
      address: '',
      phone: '',
      email: ''
    },
    vehicle: {
      brand: '',
      model: '',
      year: '',
      plateNumber: '',
      vin: '',
      color: '',
      mileage: '',
      notes: ''
    },
    items: [{ description: '', quantity: 1, unit_price: 0, discount: 0 }],
    settings: {
      theme: 'أزرق',
      style: 'حديث',
      tax_rate: 0,
      description: '',
      notes: '',
      approval_token: '',
      date: new Date().toISOString().split('T')[0],
      terms: []
    }
  });

  const isDataReady = Boolean(
    formData?.items?.length ||
    formData?.customer?.name ||
    formData?.customerName ||
    formData?.settings?.document_number
  );

  const themes = ['أزرق', 'أخضر', 'بنفسجي', 'برتقالي', 'أحمر', 'تركوازي', 'ذهبي', 'رمادي'];
  const styles = ['حديث', 'كلاسيكي', 'فاخر'];
  
  const docTypes = {
    invoice: { label: isArabic ? 'فاتورة مبيعات' : 'Sales Invoice', icon: Receipt },
    diagnosis: { label: isArabic ? 'تقرير تشخيص' : 'Diagnosis Report', icon: ClipboardList },
    quote: { label: isArabic ? 'عرض سعر' : 'Price Quote', icon: FileCheck },
    receipt: { label: isArabic ? 'إيصال استلام' : 'Receipt', icon: FileText }
  };

  useEffect(() => {
    loadWorkshopSettings();
    if (vehicleId) {
      loadVehicleData(vehicleId, { preserveItems: Boolean(visitId || operationId || invoiceId) });
      loadLatestApprovalToken(vehicleId);
    }
    if (visitId) {
      loadVisitItems(vehicleId || null, visitId);
    }
    if (operationId) {
      loadOperationData(operationId);
    }
    if (invoiceId) {
      loadInvoiceData(invoiceId);
    }
  }, [vehicleId, visitId, operationId, invoiceId]);

  useEffect(() => {
    const loadPrintDefaults = async () => {
      try {
        const res = await axios.get(`${API_URL}/settings`);
        const defaults = res.data?.printDefaults;
        if (defaults) {
          setFormData(prev => ({
            ...prev,
            settings: {
              ...prev.settings,
              theme: defaults.theme || prev.settings.theme,
              style: defaults.style || prev.settings.style,
              tax_rate: 0,
            }
          }));
        }
      } catch (e) {
        // ignore
      }
    };

    loadPrintDefaults();
  }, []);

  useEffect(() => {
    autoRefreshRef.current = false;
    autoActionRef.current = false;
  }, [vehicleId, visitId, operationId, invoiceId]);

  useEffect(() => {
    if (!autoPrint && !autoWhatsApp) return;
    if (!workshopLoaded || !isDataReady) return;
    if (autoActionRef.current) return;
    autoActionRef.current = true;

    if (autoPrint) {
      printDocument({ useCurrentWindow: true, closeAfter: autoClose });
    } else if (autoWhatsApp) {
      handleWhatsAppSend({ closeAfter: autoClose });
    }
  }, [autoPrint, autoWhatsApp, autoClose, workshopLoaded, isDataReady]);

  const loadWorkshopSettings = async () => {
    try {
      const [settingsRes, profileRes] = await Promise.all([
        axios.get(`${API_URL}/settings`),
        axios.get(`${API_URL}/profile`).catch(() => ({ data: null })),
      ]);

      const data = settingsRes.data || {};
      const profile = profileRes.data || {};

      setWorkshopSettings(data);
      setFormData(prev => ({
        ...prev,
        workshop: {
          name: profile.name || data.workshopName || '',
          name_en: profile.nameEnglish || data.workshopNameEn || '',
          address: profile.address || data.address || '',
          phone: profile.phone || data.phone || '',
          email: profile.email || data.email || '',
          website: data.website || '',
          commercial_register: profile.commercialRegister || data.commercialRegister || '',
          logo: profile.logo || '',
          slogan: profile.slogan || '',
          slogan_en: profile.sloganEnglish || ''
        }
      }));
    } catch (e) {
      console.error('Error loading settings/profile:', e);
    } finally {
      setWorkshopLoaded(true);
    }
  };

  const loadCustomerData = async (customerId) => {
    if (!customerId) return;
    try {
      const response = await axios.get(`${API_URL}/customers`);
      const rows = Array.isArray(response.data) ? response.data : (response.data?.customers || []);
      const match = rows.find((c) => c.id === customerId || c.customerId === customerId);
      if (!match) return;
      setFormData((prev) => ({
        ...prev,
        customer: {
          ...prev.customer,
          name: match.name || prev.customer.name,
          phone: match.phone || prev.customer.phone,
          email: match.email || prev.customer.email,
          address: match.address || match.company || prev.customer.address,
        }
      }));
    } catch (e) {
      console.error('Error loading customer:', e);
    }
  };

  const loadVehicleData = async (id, options = {}) => {
    const { preserveItems = false } = options;
    try {
      const { data } = await axios.get(`${API_URL}/vehicles/${id}`);
      if (data) {
        const vehicleParts = data.parts || [];
        const itemsFromParts = vehicleParts.map(part => ({
          description: part.name || part.description || '',
          quantity: part.quantity || 1,
          unit_price: part.price || 0,
          discount: 0
        }));

        const finalItems = itemsFromParts.length > 0 
          ? itemsFromParts 
          : (data.services || []).map(s => ({
              description: s,
              quantity: 1,
              unit_price: 0,
              discount: 0
            }));

        const customerName = data.customerName || data.customer_name || '';
        const customerPhone = data.customerPhone || data.customer_phone || '';
        const customerId = data.customerId || data.customer_id || '';

        setFormData(prev => ({
          ...prev,
          customer: {
            ...prev.customer,
            name: customerName || prev.customer.name,
            phone: customerPhone || prev.customer.phone
          },
          vehicle: {
            brand: data.brand || '',
            model: data.model || '',
            year: data.year || '',
            plateNumber: data.plateNumber || '',
            vin: data.vin || '',
            color: data.color || '',
            mileage: data.mileage || '',
            notes: data.notes || ''
          },
          items: preserveItems ? prev.items : (finalItems.length > 0 ? finalItems : [{ description: '', quantity: 1, unit_price: 0, discount: 0 }])
        }));

        if (customerId && !customerName) {
          loadCustomerData(customerId);
        }
      }
    } catch (e) {
      console.error('Error loading vehicle:', e);
    }
  };

  const loadVisitItems = async (vId, vVisitId) => {
    try {
      // 1) Prefer finance operations linked to the visit (most accurate for invoices/receipts).
      const opsRes = await axios.get(`${API_URL}/visits/${vVisitId}/operations`).catch(() => ({ data: [] }));
      const ops = Array.isArray(opsRes.data) ? opsRes.data : [];

      if (ops.length > 0) {
        const op = ops[0]; // latest
        // When printing from a specific visit, we derive doc type from the visit status.
        // This matches the “print حسب الحالة” requirement.
        if (docType === initialType && visitId) {
          const st = String(op.status || '').toLowerCase();
          const mapped = st === 'quotation' ? 'quote' : st === 'diagnosis' ? 'diagnosis' : st === 'receipt' ? 'receipt' : 'invoice';
          setDocType(mapped);
        }
        let opItems = op.items || [];
        if (typeof opItems === 'string') {
          try {
            opItems = JSON.parse(opItems);
          } catch (e) {
            opItems = [];
          }
        }
        const mappedItems = (opItems || []).map((it) => ({
          description: it.name || it.description || '',
          quantity: Number(it.quantity || 1),
          unit_price: Number(it.price || it.unit_price || 0),
          discount: 0,
        }));

        const opCustomerName = op.customerName || op.customer_name || op.partnerName || op.partner_name || '';
        const opCustomerPhone = op.customerPhone || op.customer_phone || op.phone || '';
        const opCustomerId = op.customerId || op.customer_id || '';

        setFormData((prev) => ({
          ...prev,
          items: mappedItems.length > 0 ? mappedItems : prev.items,
          customer: {
            ...prev.customer,
            name: opCustomerName || prev.customer.name,
            phone: opCustomerPhone || prev.customer.phone,
          },
          settings: {
            ...prev.settings,
            document_number: op.invoice_number || op.invoiceNumber || prev.settings.document_number,
            date: (op.op_date || op.date || '').toString().slice(0, 10) || prev.settings.date,
          },
        }));

        if (opCustomerId && !opCustomerName) {
          loadCustomerData(opCustomerId);
        }

        // Map doc type based on vehicle/visit status when not explicitly specified.
        if (!searchParams.get('type')) {
          // fallback logic: keep existing
        }

        return;
      }

      // 2) Fallback: load visit notes->items from vehicle visits endpoint.
      if (!vId) return;
      const visitsRes = await axios.get(`${API_URL}/vehicles/${vId}/visits`).catch(() => ({ data: [] }));
      const visits = Array.isArray(visitsRes.data) ? visitsRes.data : [];
      const match = visits.find((x) => (x.id || x.visitId) === vVisitId);

      if (match && match.notes && String(match.notes).trim().startsWith('{')) {
        try {
          const obj = JSON.parse(match.notes);
          const parsed = (obj.items || []).map((it) => ({
            description: it.name || it.description || '',
            quantity: Number(it.quantity || 1),
            unit_price: Number(it.price || it.unit_price || 0),
            discount: 0,
          }));
          if (parsed.length > 0) {
            setFormData((prev) => ({
              ...prev,
              items: parsed,
            }));
          }
        } catch (_) {
          // ignore
        }
      }
    } catch (e) {
      console.error('Error loading visit items:', e);
    }
  };

  const loadLatestApprovalToken = async (id) => {
    try {
      const { data } = await axios.get(`${API_URL}/approvals?vehicle_id=${id}`);
      if (!Array.isArray(data) || data.length === 0) return;

      const approved = data.filter(a => (a.status || '').toLowerCase() === 'approved');
      const candidates = approved.length > 0 ? approved : data;

      const sorted = [...candidates].sort((a, b) => {
        const aDate = a.respondedAt || a.responded_at || a.createdAt || a.created_at || a.requestedAt || a.requested_at;
        const bDate = b.respondedAt || b.responded_at || b.createdAt || b.created_at || b.requestedAt || b.requested_at;
        return new Date(bDate || 0) - new Date(aDate || 0);
      });

      const latest = sorted[0];
      if (latest && latest.token) {
        setFormData(prev => ({
          ...prev,
          settings: {
            ...prev.settings,
            approval_token: latest.token,
          },
        }));
      }
    } catch (e) {
      console.error('Error loading latest approval token:', e);
    }
  };

  const loadOperationData = async (opId) => {
    try {
      const { data: op } = await axios.get(`${API_URL}/operations/${opId}`);
      if (!op) return;

      let opItems = op.items || [];
      if (typeof opItems === 'string') {
        try {
          opItems = JSON.parse(opItems);
        } catch (e) {
          opItems = [];
        }
      }
      const mappedItems = (opItems || []).map((it) => ({
        description: it.name || it.description || '',
        quantity: Number(it.quantity || 1),
        unit_price: Number(it.price || it.unit_price || 0),
        discount: 0,
      }));

      const opVehicleId = op.vehicleId || op.vehicle_id;
      if (opVehicleId && !vehicleId) {
        loadVehicleData(opVehicleId, { preserveItems: true });
        loadLatestApprovalToken(opVehicleId);
      }

      const opType = op.type || op.operation_type || 'sale';
      const normalizedType = String(opType).toLowerCase();
      const isPurchase = ['purchase', 'expense', 'out'].includes(normalizedType);
      const accountLabel = op.accountName || op.account_name || op.accountLabel || '';
      const documentTitle = isPurchase ? (accountLabel || 'فاتورة شراء') : 'فاتورة مبيعات';

      setDocType('invoice');

      const opCustomerName = op.customerName || op.customer_name || op.partnerName || '';
      const opCustomerPhone = op.customerPhone || op.customer_phone || op.phone || '';
      const opCustomerId = op.customerId || op.customer_id || '';

      setFormData((prev) => ({
        ...prev,
        customer: {
          ...prev.customer,
          name: opCustomerName || prev.customer.name,
          phone: opCustomerPhone || prev.customer.phone,
        },
        items: mappedItems.length > 0 ? mappedItems : prev.items,
        settings: {
          ...prev.settings,
          date: (op.date || op.op_date || op.createdAt || '').toString().slice(0, 10) || prev.settings.date,
          document_number: op.invoice_number || op.invoiceNumber || prev.settings.document_number || `OP-${op.id}`,
          document_title: documentTitle,
          notes: op.notes || prev.settings.notes,
        },
      }));

      if (opCustomerId && !opCustomerName) {
        loadCustomerData(opCustomerId);
      }
    } catch (e) {
      console.error('Error loading operation:', e);
    }
  };

  const handleWorkshopChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      workshop: { ...prev.workshop, [field]: value }
    }));
  };

  const handleCustomerChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      customer: { ...prev.customer, [field]: value }
    }));
  };

  const handleVehicleChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      vehicle: { ...prev.vehicle, [field]: value }
    }));
  };

  const handleItemChange = (index, field, value) => {
    const newItems = [...formData.items];
    newItems[index] = { 
      ...newItems[index], 
      [field]: field === 'description' ? value : parseFloat(value) || 0 
    };
    setFormData(prev => ({ ...prev, items: newItems }));
  };

  const addItem = () => {
    setFormData(prev => ({
      ...prev,
      items: [...prev.items, { description: '', quantity: 1, unit_price: 0, discount: 0 }]
    }));
  };

  const loadInvoiceData = async (invId) => {
    try {
      const { data: inv } = await axios.get(`${API_URL}/invoices/${invId}`);
      if (!inv) return;

      let invItems = inv.items || [];
      if (typeof invItems === 'string') {
        try {
          invItems = JSON.parse(invItems);
        } catch (e) {
          invItems = [];
        }
      }
      const mappedItems = (invItems || []).map((it) => ({
        description: it.description || it.name || '',
        quantity: Number(it.quantity || 1),
        unit_price: Number(it.unit_price || it.price || 0),
        discount: Number(it.discount || 0),
      }));

      const invVehicleId = inv.vehicleId || inv.vehicle_id;
      if (invVehicleId && !vehicleId) {
        loadVehicleData(invVehicleId, { preserveItems: true });
        loadLatestApprovalToken(invVehicleId);
      }

      setDocType(inv.type || 'invoice');

      const invCustomerName = inv.partner_name || inv.partnerName || '';
      const invCustomerId = inv.customer_id || inv.customerId || '';

      setFormData((prev) => ({
        ...prev,
        customer: {
          ...prev.customer,
          name: invCustomerName || prev.customer.name,
        },
        items: mappedItems.length > 0 ? mappedItems : prev.items,
        settings: {
          ...prev.settings,
          date: (inv.created_at || inv.createdAt || '').toString().slice(0, 10) || prev.settings.date,
          document_number: inv.invoice_number || inv.invoiceNumber || prev.settings.document_number,
          notes: inv.notes || prev.settings.notes,
        },
      }));

      if (invCustomerId && !invCustomerName) {
        loadCustomerData(invCustomerId);
      }
    } catch (e) {
      console.error('Error loading invoice:', e);
    }
  };

  const removeItem = (index) => {
    if (formData.items.length > 1) {
      setFormData(prev => ({
        ...prev,
        items: prev.items.filter((_, i) => i !== index)
      }));
    }
  };

  const handleSettingsChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      settings: { ...prev.settings, [field]: value }
    }));
  };

  const calculateTotal = () => {
    const subtotal = formData.items.reduce((sum, item) => {
      return sum + (item.quantity * item.unit_price) - item.discount;
    }, 0);
    const tax = 0;
    return { subtotal, tax, total: subtotal };
  };

  const buildDocumentPayload = () => ({
    doc_type: docType,
    workshop: formData.workshop,
    customer: formData.customer,
    vehicle: formData.vehicle,
    items: formData.items.filter(item => item.description),
    settings: {
      ...formData.settings,
      approval_token: formData.settings.approval_token || undefined,
      approval_vehicle_id: vehicleId || undefined,
      visit_id: visitId || undefined,
    },
  });

  const refreshDocumentData = async () => {
    await loadWorkshopSettings();
    if (vehicleId) {
      await loadVehicleData(vehicleId, { preserveItems: Boolean(visitId || operationId || invoiceId) });
      await loadLatestApprovalToken(vehicleId);
    }
    if (visitId) {
      await loadVisitItems(vehicleId || null, visitId);
    }
    if (operationId) {
      await loadOperationData(operationId);
    }
    if (invoiceId) {
      await loadInvoiceData(invoiceId);
    }
  };

  const getDocumentHtml = async () => {
    if ((!formData.workshop.name || !formData.customer.name) && !autoRefreshRef.current) {
      autoRefreshRef.current = true;
      await refreshDocumentData();
      await new Promise((r) => setTimeout(r, 120));
    }

    const response = await axios.post(`${API_URL}/documents/generate`, buildDocumentPayload());
    if (response.data?.success) {
      return response.data.html;
    }
    throw new Error(response.data?.message || 'فشل');
  };

  const getPdfBodyFromHtml = async (html) => {
    const previewIframe = previewRef?.current?.querySelector?.('iframe');
    if (previewIframe?.contentDocument?.readyState === 'complete' && previewIframe?.contentDocument?.body?.innerHTML?.trim()) {
      return { doc: previewIframe.contentDocument, body: previewIframe.contentDocument.body };
    }

    setPdfSourceHtml(html);
    await new Promise((r) => setTimeout(r, 60));
    const hiddenIframe = pdfIframeRef.current;
    if (!hiddenIframe) {
      throw new Error('تعذر إنشاء المعاينة المخفية');
    }

    await new Promise((resolve) => {
      if (hiddenIframe.contentDocument?.readyState === 'complete') {
        resolve();
        return;
      }
      const handler = () => {
        hiddenIframe.removeEventListener('load', handler);
        resolve();
      };
      hiddenIframe.addEventListener('load', handler);
      setTimeout(() => {
        hiddenIframe.removeEventListener('load', handler);
        resolve();
      }, 1200);
    });

    const doc = hiddenIframe.contentDocument;
    return { doc, body: doc?.body };
  };

  const handleDownloadPDF = async () => {
    setGeneratingPdf(true);
    try {
      const html = previewHtml || (await getDocumentHtml());
      const { doc, body } = await getPdfBodyFromHtml(html);
      if (!body) {
        throw new Error(isArabic ? 'تعذر تجهيز المعاينة للطباعة' : 'Unable to prepare preview');
      }

      if (doc?.fonts?.ready) {
        try {
          await doc.fonts.ready;
        } catch (_) {
          // ignore
        }
      }
      await new Promise((r) => setTimeout(r, 120));

      // Try multiple scales to avoid failures across devices.
      const fileName = `${docType}_${formData.settings.document_number || 'doc'}.pdf`;
      const scales = [2, 1.5, 1];
      let lastErr = null;
      for (const sc of scales) {
        try {
          await downloadPDF(body, fileName, {
            scale: sc,
            backgroundColor: '#ffffff',
          });
          lastErr = null;
          break;
        } catch (e) {
          lastErr = e;
        }
      }
      if (lastErr) throw lastErr;

    } catch (e) {
      console.error('PDF Download Error:', e);
      alert((isArabic ? 'فشل تحميل PDF: ' : 'PDF Download Failed: ') + (e?.message || ''));
    } finally {
      setGeneratingPdf(false);
    }
  };

  const handleWhatsAppSend = async ({ closeAfter = false } = {}) => {
    setGeneratingPdf(true);
    try {
      const html = previewHtml || (await getDocumentHtml());
      const { doc, body } = await getPdfBodyFromHtml(html);
      if (!body) {
        throw new Error(isArabic ? 'تعذر تجهيز المعاينة للطباعة' : 'Unable to prepare preview');
      }

      if (doc?.fonts?.ready) {
        try {
          await doc.fonts.ready;
        } catch (_) {
          // ignore
        }
      }
      await new Promise((r) => setTimeout(r, 120));

      const fileName = `${docType}_${formData.settings.document_number || 'doc'}.pdf`;
      await downloadPDF(body, fileName, {
        scale: 1.5,
        backgroundColor: '#ffffff',
      });

      const phone = formData.customer?.phone || formData.supplier?.phone || formData.customerPhone || '';
      if (phone) {
        const message = `فاتورة ${docType}\nالعميل: ${formData.customer?.name || formData.customerName || ''}\nالإجمالي: ${calculateTotal().total.toLocaleString('ar-SA', { minimumFractionDigits: 2 })}\n${formData.workshop?.name || ''}`;
        window.open(getWhatsAppLink(phone, message), '_blank');
      } else {
        alert(isArabic ? 'يرجى إضافة رقم الجوال للعميل لإرسال واتس اب' : 'Customer phone is missing');
      }
    } catch (e) {
      console.error('PDF WhatsApp Error:', e);
      alert((isArabic ? 'فشل تجهيز PDF للإرسال: ' : 'Failed to prepare PDF: ') + (e?.message || ''));
    } finally {
      setGeneratingPdf(false);
      if (closeAfter) {
        setTimeout(() => window.close(), 800);
      }
    }
  };

  const generateDocument = async (preview = false) => {
    if (!preview) {
      // If triggered by "Download" button that is not using handleDownloadPDF, use it
      return handleDownloadPDF();
    }
    
    setLoading(true);
    try {
      const html = await getDocumentHtml();
      setPreviewHtml(html);
      setShowPreview(true);
    } catch (error) {
      console.error('Error:', error);
      alert(error.message);
    } finally {
      setLoading(false);
    }
  };

  const printDocument = async ({ useCurrentWindow = false, closeAfter = false } = {}) => {
    const printWindow = useCurrentWindow ? window : window.open('', '_blank');
    if (!printWindow) {
      alert(isArabic ? 'تم حظر النافذة المنبثقة' : 'Popup blocked');
      return;
    }

    setLoading(true);
    try {
      const html = previewHtml || (await getDocumentHtml());
      if (html) {
        printWindow.document.open();
        printWindow.document.write(html);
        printWindow.document.close();
        printWindow.focus();
        setTimeout(() => {
          printWindow.print();
          if (closeAfter) {
            setTimeout(() => printWindow.close(), 800);
          }
        }, 800);
      }
    } catch (error) {
      if (!useCurrentWindow) {
        printWindow.close();
      }
      alert(isArabic ? 'فشل الطباعة' : 'Print failed');
    } finally {
      setLoading(false);
    }
  };

  const totals = calculateTotal();
  const DocIcon = docTypes[docType]?.icon || FileText;

  const saveDefaults = async () => {
    try {
      setLoading(true);
      await axios.post(`${API_URL}/settings/print-defaults`, {
        theme: formData.settings.theme,
        style: formData.settings.style,
        tax_rate: 0,
      });
      alert(isArabic ? 'تم حفظ الإعدادات الافتراضية' : 'Default settings saved');
    } catch (error) {
      alert(isArabic ? 'فشل الحفظ' : 'Failed to save');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-4 sm:p-6 max-w-6xl">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground flex items-center gap-2">
              <DocIcon size={28} />
              {isArabic ? 'طباعة المستندات' : 'Document Printing'}
            </h1>
            <p className="text-muted-foreground">
              {isArabic ? 'فواتير - تشخيص - عروض أسعار - إيصالات' : 'Invoices - Diagnosis - Quotes - Receipts'}
            </p>
          </div>
          <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
            <Button
              variant="outline"
              onClick={() => generateDocument(true)}
              disabled={loading}
              className="w-full sm:w-auto"
              data-testid="document-preview-button"
            >
              <Eye size={18} className={isArabic ? 'ml-2' : 'mr-2'} />
              {isArabic ? 'معاينة' : 'Preview'}
            </Button>
            <Button
              variant="outline"
              onClick={printDocument}
              disabled={loading}
              className="w-full sm:w-auto"
              data-testid="document-print-button"
            >
              <Printer size={18} className={isArabic ? 'ml-2' : 'mr-2'} />
              {isArabic ? 'طباعة' : 'Print'}
            </Button>
            <Button
              onClick={handleDownloadPDF}
              disabled={loading || generatingPdf}
              className="w-full sm:w-auto bg-gradient-to-r from-blue-600 to-indigo-600"
              data-testid="document-download-button"
            >
              {generatingPdf ? <Loader2 size={18} className="animate-spin" /> : <Download size={18} className={isArabic ? 'ml-2' : 'mr-2'} />}
              {isArabic ? 'تحميل PDF' : 'Download PDF'}
            </Button>
            <Button
              variant="outline"
              onClick={saveDefaults}
              disabled={loading}
              className="w-full sm:w-auto"
              data-testid="document-save-defaults-button"
            >
              <Save size={18} className={isArabic ? 'ml-2' : 'mr-2'} />
              {isArabic ? 'حفظ كافتراضي' : 'Save Default'}
            </Button>
          </div>
        </div>

        {/* Document Type Selection */}
        <Card className="mb-6 bg-slate-900">
          <CardContent className="p-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {Object.entries(docTypes).map(([type, { label, icon: Icon }]) => {
                const isActive = docType === type;
                return (
                  <button
                    key={type}
                    onClick={() => setDocType(type)}
                    className={`relative h-auto py-5 px-4 flex flex-col items-center gap-3 rounded-xl transition-all duration-300 ${
                      isActive 
                        ? 'bg-blue-600 text-white border-4 border-blue-400 shadow-2xl shadow-blue-500/50 scale-105' 
                        : 'bg-slate-800/80 text-slate-400 border-2 border-slate-700 hover:border-blue-600 hover:text-white hover:bg-slate-700'
                    }`}
                  >
                    {isActive && (
                      <div className="absolute -top-2 -right-2 w-7 h-7 bg-gradient-to-br from-green-400 to-green-600 rounded-full flex items-center justify-center shadow-lg animate-bounce">
                        <Check size={18} className="text-white font-bold" />
                      </div>
                    )}
                    <Icon size={32} className={isActive ? 'text-white' : 'text-slate-500'} strokeWidth={isActive ? 2.5 : 2} />
                    <span className={`text-sm font-bold text-center leading-tight ${isActive ? 'text-white' : 'text-slate-400'}`}>
                      {label}
                    </span>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <Tabs defaultValue="customer" className="space-y-6">
          <TabsList className="grid grid-cols-4 w-full max-w-md">
            <TabsTrigger value="customer">{isArabic ? 'العميل' : 'Customer'}</TabsTrigger>
            <TabsTrigger value="vehicle">{isArabic ? 'المركبة' : 'Vehicle'}</TabsTrigger>
            <TabsTrigger value="items">{isArabic ? 'البنود' : 'Items'}</TabsTrigger>
            <TabsTrigger value="settings">{isArabic ? 'الإعدادات' : 'Settings'}</TabsTrigger>
          </TabsList>

          {/* Customer Tab */}
          <TabsContent value="customer">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* بيانات الورشة */}
              <Card>
                <CardHeader>
                  <CardTitle>{isArabic ? 'بيانات الورشة' : 'Workshop Details'}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Logo & Slogan */}
                  {(formData.workshop.logo || formData.workshop.slogan) && (
                    <div className="flex items-center gap-4 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg border">
                      {formData.workshop.logo && (
                        <img src={formData.workshop.logo} alt="شعار الورشة" className="w-16 h-16 object-contain rounded" />
                      )}
                      {formData.workshop.slogan && (
                        <p className="text-sm text-muted-foreground italic">{formData.workshop.slogan}</p>
                      )}
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>{isArabic ? 'اسم الورشة' : 'Workshop Name'}</Label>
                      <Input value={formData.workshop.name} onChange={(e) => handleWorkshopChange('name', e.target.value)} />
                    </div>
                    <div>
                      <Label>{isArabic ? 'الهاتف' : 'Phone'}</Label>
                      <Input value={formData.workshop.phone} onChange={(e) => handleWorkshopChange('phone', e.target.value)} />
                    </div>
                  </div>
                  <div>
                    <Label>{isArabic ? 'العنوان' : 'Address'}</Label>
                    <Input value={formData.workshop.address} onChange={(e) => handleWorkshopChange('address', e.target.value)} />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>{isArabic ? 'البريد' : 'Email'}</Label>
                      <Input value={formData.workshop.email} onChange={(e) => handleWorkshopChange('email', e.target.value)} />
                    </div>
                    <div>
                      <Label>{isArabic ? 'السجل التجاري' : 'Commercial Register'}</Label>
                      <Input value={formData.workshop.commercial_register} onChange={(e) => handleWorkshopChange('commercial_register', e.target.value)} />
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* بيانات العميل */}
              <Card>
                <CardHeader>
                  <CardTitle>{isArabic ? 'بيانات العميل' : 'Customer Details'}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>{isArabic ? 'اسم العميل' : 'Customer Name'}</Label>
                      <Input value={formData.customer.name} onChange={(e) => handleCustomerChange('name', e.target.value)} />
                    </div>
                    <div>
                      <Label>{isArabic ? 'الشركة' : 'Company'}</Label>
                      <Input value={formData.customer.company} onChange={(e) => handleCustomerChange('company', e.target.value)} />
                    </div>
                  </div>
                  <div>
                    <Label>{isArabic ? 'العنوان' : 'Address'}</Label>
                    <Input value={formData.customer.address} onChange={(e) => handleCustomerChange('address', e.target.value)} />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>{isArabic ? 'الهاتف' : 'Phone'}</Label>
                      <Input value={formData.customer.phone} onChange={(e) => handleCustomerChange('phone', e.target.value)} />
                    </div>
                    <div>
                      <Label>{isArabic ? 'البريد' : 'Email'}</Label>
                      <Input value={formData.customer.email} onChange={(e) => handleCustomerChange('email', e.target.value)} />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Vehicle Tab */}
          <TabsContent value="vehicle">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Car size={20} />
                  {isArabic ? 'بيانات المركبة' : 'Vehicle Details'}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <Label>{isArabic ? 'الماركة' : 'Brand'}</Label>
                    <Input value={formData.vehicle.brand} onChange={(e) => handleVehicleChange('brand', e.target.value)} placeholder="تويوتا" />
                  </div>
                  <div>
                    <Label>{isArabic ? 'الموديل' : 'Model'}</Label>
                    <Input value={formData.vehicle.model} onChange={(e) => handleVehicleChange('model', e.target.value)} placeholder="كامري" />
                  </div>
                  <div>
                    <Label>{isArabic ? 'السنة' : 'Year'}</Label>
                    <Input value={formData.vehicle.year} onChange={(e) => handleVehicleChange('year', e.target.value)} placeholder="2022" />
                  </div>
                  <div>
                    <Label>{isArabic ? 'اللون' : 'Color'}</Label>
                    <Input value={formData.vehicle.color} onChange={(e) => handleVehicleChange('color', e.target.value)} placeholder="أبيض" />
                  </div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div>
                    <Label>{isArabic ? 'رقم اللوحة' : 'Plate Number'}</Label>
                    <Input value={formData.vehicle.plateNumber} onChange={(e) => handleVehicleChange('plateNumber', e.target.value)} />
                  </div>
                  <div>
                    <Label>{isArabic ? 'رقم الهيكل' : 'VIN'}</Label>
                    <Input value={formData.vehicle.vin} onChange={(e) => handleVehicleChange('vin', e.target.value)} />
                  </div>
                  <div>
                    <Label>{isArabic ? 'العداد (كم)' : 'Mileage (km)'}</Label>
                    <Input value={formData.vehicle.mileage} onChange={(e) => handleVehicleChange('mileage', e.target.value)} />
                  </div>
                </div>
                <div>
                  <Label>{isArabic ? 'ملاحظات' : 'Notes'}</Label>
                  <Textarea value={formData.vehicle.notes} onChange={(e) => handleVehicleChange('notes', e.target.value)} rows={3} />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Items Tab */}
          <TabsContent value="items">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>{isArabic ? 'البنود والخدمات' : 'Items & Services'}</CardTitle>
                <Button variant="outline" size="sm" onClick={addItem}>
                  <Plus size={16} className={isArabic ? 'ml-1' : 'mr-1'} />
                  {isArabic ? 'إضافة بند' : 'Add Item'}
                </Button>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {(formData.items || []).map((item, index) => (
                    <div key={`item-${index}`} className="flex flex-wrap gap-2 items-end p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                      <div className="flex-1 min-w-[200px]">
                        <Label>{isArabic ? 'الوصف' : 'Description'}</Label>
                        <Input
                          value={item.description}
                          onChange={(e) => handleItemChange(index, 'description', e.target.value)}
                          placeholder={isArabic ? 'وصف الخدمة أو القطعة' : 'Service or part description'}
                        />
                      </div>
                      <div className="w-20">
                        <Label>{isArabic ? 'الكمية' : 'Qty'}</Label>
                        <Input type="number" value={item.quantity} onChange={(e) => handleItemChange(index, 'quantity', e.target.value)} min="1" />
                      </div>
                      <div className="w-28">
                        <Label>{isArabic ? 'السعر' : 'Price'}</Label>
                        <Input type="number" value={item.unit_price} onChange={(e) => handleItemChange(index, 'unit_price', e.target.value)} min="0" />
                      </div>
                      <div className="w-24">
                        <Label>{isArabic ? 'الخصم' : 'Discount'}</Label>
                        <Input type="number" value={item.discount} onChange={(e) => handleItemChange(index, 'discount', e.target.value)} min="0" />
                      </div>
                      <div className="w-28 text-center">
                        <Label>{isArabic ? 'المجموع' : 'Total'}</Label>
                        <p className="font-bold text-lg">{((item.quantity * item.unit_price) - item.discount).toLocaleString()}</p>
                      </div>
                      <Button variant="ghost" size="icon" onClick={() => removeItem(index)} disabled={formData.items.length === 1} className="text-red-500">
                        <Trash2 size={18} />
                      </Button>
                    </div>
                  ))}
                </div>

                {/* الإجماليات */}
                <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <div className="flex justify-between py-2">
                    <span>{isArabic ? 'المجموع الفرعي:' : 'Subtotal:'}</span>
                    <span className="font-semibold">{totals.subtotal.toLocaleString()} {isArabic ? 'ر.س' : 'SAR'}</span>
                  </div>
                  {/* Tax removed */}
                  <div className="flex justify-between py-2 border-t-2 border-blue-200 text-lg font-bold text-blue-600">
                    <span>{isArabic ? 'المجموع الكلي:' : 'Total:'}</span>
                    <span>{totals.total.toLocaleString()} {isArabic ? 'ر.س' : 'SAR'}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Settings Tab */}
          <TabsContent value="settings">
            <Card>
              <CardHeader>
                <CardTitle>{isArabic ? 'إعدادات الطباعة' : 'Print Settings'}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <Label>{isArabic ? 'لون التصميم' : 'Theme Color'}</Label>
                    <Select value={formData.settings.theme} onValueChange={(v) => handleSettingsChange('theme', v)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {themes.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>{isArabic ? 'نمط التصميم' : 'Style'}</Label>
                    <Select value={formData.settings.style} onValueChange={(v) => handleSettingsChange('style', v)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {styles.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label style={{ display: 'none' }}>{isArabic ? 'نسبة الضريبة (%)' : 'Tax Rate (%)'}</Label>
                    <Input
                      type="number"
                      value={0}
                      onChange={() => {}}
                      min="0"
                      max="100"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                  <div>
                    <Label>{isArabic ? 'تاريخ الفاتورة' : 'Invoice Date'}</Label>
                    <Input
                      type="date"
                      value={formData.settings.date}
                      onChange={(e) => handleSettingsChange('date', e.target.value)}
                    />
                  </div>
                  <div>
                    <Label>{isArabic ? 'رمز طلب الاعتماد (APR-...)' : 'Approval Request Token (APR-...)'}</Label>
                    <Input
                      value={formData.settings.approval_token || ''}
                      onChange={(e) => handleSettingsChange('approval_token', e.target.value)}
                      readOnly={!!vehicleId}
                      placeholder={isArabic ? 'رمز الاعتماد (داخلي فقط - لا يظهر في المستند)' : 'Approval token (internal only - not printed)'}
                    />
                    <p className="mt-1 text-xs text-muted-foreground">
                      {isArabic
                        ? 'هذا الرمز للاستخدام الداخلي فقط (متابعة الاعتماد داخل النظام) ولن يظهر في المستند المطبوع.'
                        : 'This token is internal-only and will not be embedded in the printed document.'}
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-1 gap-4 mt-4">
                  <div>
                    <Label>{isArabic ? 'ملاحظات إضافية' : 'Additional Notes'}</Label>
                    <Textarea
                      value={formData.settings.notes}
                      onChange={(e) => handleSettingsChange('notes', e.target.value)}
                      placeholder={isArabic ? 'ملاحظات تظهر في المستند...' : 'Notes to appear in document...'}
                      rows={3}
                    />
                  </div>
                  <div>
                    <Label>{isArabic ? 'الشروط والأحكام (سطر واحد لكل شرط)' : 'Terms and Conditions (one per line)'}</Label>
                    <Textarea
                      value={formData.settings.terms?.join('\n') || ''}
                      onChange={(e) => handleSettingsChange('terms', e.target.value.split('\n').filter(t => t.trim()))}
                      placeholder={isArabic ? 'أدخل كل شرط في سطر منفصل...' : 'Enter each term on a new line...'}
                      rows={5}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Preview Modal */}
        {showPreview && previewHtml && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white dark:bg-slate-900 rounded-lg w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="p-4 border-b flex justify-between items-center">
                <h3 className="font-bold text-lg">{isArabic ? 'معاينة المستند' : 'Document Preview'}</h3>
                <div className="flex gap-2 flex-wrap">
                  <Button variant="outline" onClick={printDocument} className="w-full sm:w-auto" data-testid="document-preview-print-button">
                    <Printer size={16} className={isArabic ? 'ml-1' : 'mr-1'} />
                    {isArabic ? 'طباعة' : 'Print'}
                  </Button>
                  <Button variant="outline" onClick={handleDownloadPDF} disabled={generatingPdf} className="w-full sm:w-auto" data-testid="document-preview-download-button">
                    {generatingPdf ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} className={isArabic ? 'ml-1' : 'mr-1'} />}
                    {isArabic ? 'تحميل PDF' : 'Download PDF'}
                  </Button>
                  <Button variant="ghost" onClick={() => setShowPreview(false)} className="w-full sm:w-auto" data-testid="document-preview-close-button">
                    {isArabic ? 'إغلاق' : 'Close'}
                  </Button>
                </div>
              </div>
              <div className="flex-1 overflow-auto">
                <div className="w-full flex justify-center bg-gray-100 p-4">
                  <div className="bg-white shadow" style={{ width: 794 }}>
                    <div ref={previewRef}>
                      <iframe
                        srcDoc={previewHtml}
                        className="w-[794px] h-[1123px]"
                        title="Document Preview"
                        style={{ border: '0' }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
        <div className="hidden" data-testid="document-hidden-iframe">
          <iframe
            ref={pdfIframeRef}
            srcDoc={pdfSourceHtml}
            title="Document PDF Hidden"
          />
        </div>
    </div>
  );
};

export default DocumentPrint;