import React, { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { CheckCircle, FileText, Printer, Trash2, X, Share2, BadgeCheck, Package, Wrench, Upload, XCircle, Copy } from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import DocumentFormDialog from './DocumentFormDialog';
import QuickPrintDialog from './QuickPrintDialog';
import { useTranslation } from 'react-i18next';
import { resolveBackendBase } from '../utils/backendBase';

const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);

const VehicleQuickActions = ({ isOpen, onClose, vehicle, onStatusUpdate, onDelete }) => {
  const { t, i18n } = useTranslation();
  const isRTL = i18n.language === 'ar';
  const { toast } = useToast();
  const navigate = useNavigate();
  const [newStatus, setNewStatus] = useState(vehicle?.status || 'diagnosis');
  const [loading, setLoading] = useState(false);
  
  // Document form dialogs
  const [documentDialogOpen, setDocumentDialogOpen] = useState(false);
  const [currentDocType, setCurrentDocType] = useState('');
  const [printDialogOpen, setPrintDialogOpen] = useState(false);
  const [printDialogConfig, setPrintDialogConfig] = useState(null);

  useEffect(() => {
    setNewStatus(vehicle?.status || 'diagnosis');
  }, [vehicle]);

  const statusOptions = [
    { value: 'diagnosis', label: t('status.diagnosis'), color: 'bg-yellow-500' },
    { value: 'quotation', label: t('status.quotation'), color: 'bg-blue-500' },
    { value: 'approved', label: t('status.approved'), color: 'bg-green-500' },
    { value: 'waiting_for_parts', label: t('status.waiting_for_parts'), color: 'bg-amber-500' },
    { value: 'repair', label: t('status.repair'), color: 'bg-orange-500' },
    { value: 'quality_check', label: t('status.quality_check'), color: 'bg-purple-500' },
    { value: 'ready', label: t('status.ready'), color: 'bg-green-600' },
    { value: 'delivering', label: t('status.delivering'), color: 'bg-teal-500' },
    { value: 'delivered', label: t('status.delivered'), color: 'bg-gray-500' }
  ];

  const handleStatusUpdate = async () => {
    try {
      setLoading(true);
      await onStatusUpdate(newStatus);
      
      // Notify Dashboard and other pages to refresh
      window.dispatchEvent(new CustomEvent('vehicleUpdated', { 
        detail: { vehicleId: vehicle?.id, status: newStatus, timestamp: Date.now() } 
      }));
      
      toast({ title: t('common.success'), description: t('messages.success_updated') });
      onClose();
    } catch (error) {
      toast({ title: t('common.error'), description: t('messages.error_occurred'), variant: 'destructive' });
    } finally { setLoading(false); }
  };

  const openDocumentDialog = (docType) => {
    setCurrentDocType(docType);
    setDocumentDialogOpen(true);
  };

  const buildVehiclePayload = (docType) => {
    const labelMap = {
      invoice: 'فاتورة',
      diagnosis: 'تقرير تشخيص',
      quote: 'عرض سعر',
      receipt: 'سند قبض',
    };
    const items = (approvalItems || []).map((item) => {
      const quantity = Number(item?.quantity || 1);
      const price = Number(item?.price || 0);
      const itemName = item?.name || 'عنصر';
      return {
        name: itemName,
        description: itemName,
        quantity,
        price,
        total: Number(item?.total || quantity * price),
        unit: item?.unit || 'حبة',
      };
    });
    return {
      doc_type: docType,
      items,
      customer: {
        name: vehicle?.customerName || vehicle?.ownerName || '',
        phone: vehicle?.customerPhone || vehicle?.customerPhoneNumber || '',
      },
      vehicle: {
        plate: vehicle?.plateNumber || vehicle?.plate || '',
        model: vehicle?.vehicleModel || vehicle?.model || '',
        brand: vehicle?.vehicleBrand || vehicle?.brand || '',
      },
      settings: {
        document_number: '',
        document_title: labelMap[docType] || 'مستند',
      },
    };
  };

  const openPrintDialog = (docType) => {
    const labelMap = {
      invoice: 'فاتورة',
      diagnosis: 'تشخيص',
      quote: 'عرض سعر',
      receipt: 'سند قبض',
    };
    setPrintDialogConfig({
      title: labelMap[docType] || 'طباعة مستند',
      phone: vehicle?.customerPhone || vehicle?.customerPhoneNumber || '',
      payloadBuilder: () => buildVehiclePayload(docType),
    });
    setPrintDialogOpen(true);
  };

  const handleDocumentSaved = (savedDoc) => {
    toast({ title: t('common.success'), description: t('messages.success_saved') });
    setDocumentDialogOpen(false);
  };

  const [approvalDialogOpen, setApprovalDialogOpen] = useState(false);
  const [activeVisitId, setActiveVisitId] = useState(null);

  const [whatsappPreviewOpen, setWhatsappPreviewOpen] = useState(false);
  const [whatsappPreviewMessage, setWhatsappPreviewMessage] = useState('');
  const [whatsappPreviewLink, setWhatsappPreviewLink] = useState('');

  const [approvalForm, setApprovalForm] = useState({
    title: 'طلب اعتماد الإصلاح',
    amount: '',
    expiryDays: '7',
    images: []
  });

  const [approvalItems, setApprovalItems] = useState([]);
  const [approvalVisitId, setApprovalVisitId] = useState(null);
  const [workshopProfile, setWorkshopProfile] = useState(null);

  useEffect(() => {
    // Load workshop profile
    const loadProfile = async () => {
      try {
        const res = await axios.get(`${API_URL}/profile`);
        setWorkshopProfile(res.data);
      } catch (e) {
        console.error('Failed to load workshop profile:', e);
      }
    };
    loadProfile();
  }, []);

  const computeApprovalFromVehicle = async () => {
    if (!vehicle?.id) return;
    try {
      // Get latest visit
      const visitsRes = await axios.get(`${API_URL}/vehicles/${vehicle.id}/visits`);
      const visits = visitsRes.data || [];
      const latestVisit = visits[0] || null;
      const visitId = latestVisit?.id || null;
      setApprovalVisitId(visitId);

      let ops = [];
      if (visitId) {
        const opsRes = await axios.get(`${API_URL}/visits/${visitId}/operations`);
        ops = opsRes.data || [];
      } else {
        const opsRes = await axios.get(`${API_URL}/operations`, { params: { vehicle_id: vehicle.id } });
        ops = opsRes.data || [];
      }

      const items = [];
      for (const op of ops) {
        for (const it of (op.items || [])) {
          if (!it?.name) continue;
          items.push({
            name: it.name,
            quantity: Number(it.quantity || 1),
            price: Number(it.price || 0),
            itemType: it.itemType || it.type || 'service',
          });
        }
      }

      const total = items.reduce((sum, it) => sum + (it.price * it.quantity), 0);
      setApprovalItems(items);
      setApprovalForm((prev) => ({
        ...prev,
        amount: total ? String(Math.round(total * 100) / 100) : '',
      }));
    } catch (e) {
      console.error('Failed to compute approval from vehicle:', e);
      // keep manual fallback
    }

    try {
      const visitsRes = await axios.get(`${API_URL}/vehicles/${vehicle.id}/visits`);
      const visits = visitsRes.data || [];
      setActiveVisitId(visits?.[0]?.id || null);
    } catch (e) {
      // ignore
    }

  };

  const handleRequestApproval = async () => {
    setApprovalDialogOpen(true);
    await computeApprovalFromVehicle();
  };

  const handleApprovalImageChange = (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length + approvalForm.images.length > 5) {
      toast({ title: 'تنبيه', description: 'الحد الأقصى 5 صور', variant: 'destructive' });
      return;
    }
    
    // Convert to base64
    files.forEach(file => {
      const reader = new FileReader();
      reader.onload = (e) => {
        setApprovalForm(prev => ({
          ...prev,
          images: [...prev.images, { data: e.target.result, name: file.name }]
        }));
      };
      reader.readAsDataURL(file);
    });
  };

  const removeApprovalImage = (index) => {
    setApprovalForm(prev => ({
      ...prev,
      images: prev.images.filter((_, i) => i !== index)
    }));
  };

  const submitApprovalRequest = async () => {
    try {
      if (!approvalForm.title || !approvalForm.amount) {
        toast({ title: 'خطأ', description: 'الرجاء إدخال العنوان والمبلغ', variant: 'destructive' });
        return;
      }

      setLoading(true);
      const payload = {
        vehicleId: vehicle?.id,
        customerId: vehicle?.customerId,
        title: approvalForm.title,
        amount: parseFloat(approvalForm.amount || '0'),
        expiryDays: parseInt(approvalForm.expiryDays || '7'),
        images: approvalForm.images,
        // keep items in backend record for future (optional)
        serviceItems: approvalItems,
      };

      const { data } = await axios.post(`${API_URL}/approvals`, payload);
      toast({ title: 'تم الإرسال', description: 'تم إنشاء طلب الاعتماد' });
      const approvalLink = `${window.location.origin}/approval/${data.token}`;

      // بيانات الورشة (من /profile)
      const workshopName = workshopProfile?.name || 'ورشتي';
      const workshopSlogan = workshopProfile?.sloganAr || workshopProfile?.slogan || '';

      const currency = 'ر.س';
      const items = approvalItems || [];
      const services = items.filter((it) => (it.itemType || '').toLowerCase() !== 'part');
      const parts = items.filter((it) => (it.itemType || '').toLowerCase() === 'part');

      const fmtLine = (it, icon = '🔧') => {
        const qty = Number(it.quantity || 1);
        const price = Number(it.price || 0);
        const lineTotal = Math.round(qty * price * 100) / 100;
        return `${icon} ${it.name}${qty > 1 ? ` (x${qty})` : ''} — ${lineTotal} ${currency}`;
      };

      // رسالة واتساب مفصّلة ومنسقة (مع إيموجيات)
      let message = `*${workshopName}*\n`;
      if (workshopSlogan) message += `${workshopSlogan}\n`;
      message += `\nالسلام عليكم ${vehicle?.customerName || ''}\n`;
      message += `\n📝 *طلب اعتماد إصلاح*\n`;
      message += `🚗 المركبة: *${vehicle?.plateNumber || '-'}*\n`;

      if (services.length) {
        message += `\n🔧 *الخدمات:*\n`;
        message += services.map((it) => fmtLine(it, '🔧')).join('\n') + '\n';
      }
      if (parts.length) {
        message += `\n🧩 *القطع:*\n`;
        message += parts.map((it) => fmtLine(it, '🧩')).join('\n') + '\n';
      }

      message += `\n💸 *الإجمالي: ${approvalForm.amount} ${currency}*\n`;
      const otpCode = data?.otp || data?.otp_code;
      if (otpCode) {
        message += `\n🔐 *رمز التحقق (OTP): ${otpCode}*\n`;
      }
      message += `\n🔗 للموافقة على الطلب، تفضل الرابط التالي:\n${approvalLink}\n`;
      message += `\n⏳ الرابط صالح لمدة ${approvalForm.expiryDays} يوم.`;

      // عرض الرسالة قبل الإرسال (حسب طلبك)
      setWhatsappPreviewLink(approvalLink);
      setWhatsappPreviewMessage(message);
      setWhatsappPreviewOpen(true);
      setApprovalDialogOpen(false);

      setNewStatus('quotation');
      setApprovalForm({ title: 'طلب اعتماد الإصلاح', amount: '', expiryDays: '7', images: [] });
    } catch (e) {
      toast({ title: 'خطأ', description: 'تعذر إرسال طلب الاعتماد', variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  const [lastWhatsappUrl, setLastWhatsappUrl] = useState('');

  const sendToWhatsApp = (type, link, customMessage) => {
    const phone = vehicle?.customerPhone || '';
    if (!phone) {
      toast({ title: 'تنبيه', description: 'رقم هاتف العميل غير متوفر', variant: 'destructive' });
      return;
    }

    // تطبيع الرقم لصيغة دولية سعودية 9665xxxxxxx
    let norm = phone.replace(/[^0-9+]/g, '');
    if (norm.startsWith('00')) norm = norm.slice(2);
    if (norm.startsWith('+')) norm = norm.slice(1);
    if (norm.startsWith('05')) {
      norm = '966' + norm.slice(1);
    } else if (norm.startsWith('5') && norm.length === 9) {
      norm = '966' + norm;
    } else if (!norm.startsWith('966')) {
      norm = '966' + norm;
    }

    // رسالة بسيطة وواضحة لتقليل مشاكل iOS
    const msg = customMessage || `السلام عليكم ${vehicle?.customerName} - ${link}`;
    const encoded = encodeURIComponent(msg);

    const whatsappUrl = `https://api.whatsapp.com/send?phone=${norm}&text=${encoded}`;
    setLastWhatsappUrl(whatsappUrl);

    // إغلاق نافذة طلب الاعتماد قبل الانتقال
    try {
      setApprovalDialogOpen(false);
    } catch (e) {
      // تجاهل أي خطأ
    }

    // فتح الرابط مباشرة في نفس التبويب (الأكثر استقراراً على iOS)
    window.location.href = whatsappUrl;
  };


  const handlePrintAndSend = async (type) => {
    // Generate link for sharing
    const trackingLink = `${window.location.origin}/track/${vehicle?.trackingLink || vehicle?.id}`;
    let message = `السلام عليكم ${vehicle?.customerName}\n`;
    
    if (type === 'diagnosis') {
      message += `تقرير التشخيص للمركبة ${vehicle?.plateNumber}\nللاطلاع: ${trackingLink}`;
    } else if (type === 'invoice') {
      message += `فاتورة المركبة ${vehicle?.plateNumber}\nللاطلاع: ${trackingLink}`;
    } else if (type === 'quote') {
      message += `عرض السعر للمركبة ${vehicle?.plateNumber}\nللاطلاع: ${trackingLink}`;
    } else if (type === 'receipt') {
      message += `سند القبض\nللاطلاع: ${trackingLink}`;
    }
    
    await sendToWhatsApp(type, trackingLink, message);
  };

  const handleDelete = async () => {
    if (!window.confirm(t('quick_actions.confirm_delete'))) return;
    try {
      setLoading(true);
      await onDelete();
      toast({ title: t('common.success'), description: t('messages.success_deleted') });
      onClose();
    } catch (error) {
      toast({ title: t('common.error'), description: t('messages.error_occurred'), variant: 'destructive' });
    } finally { setLoading(false); }
  };

  const handleDialogOpenChange = (v) => {
    if (!v) {
      if (documentDialogOpen) setDocumentDialogOpen(false);
      onClose?.();
    }
  };

  if (!vehicle) return null;

  return (
    <>
      <Dialog open={isOpen} onOpenChange={handleDialogOpenChange}>
        <DialogContent
          data-testid="vehicle-quick-actions-dialog"
          className={`w-[95vw] max-w-[560px] max-h-[90vh] overflow-y-auto ${isRTL ? 'rtl' : 'ltr'} bg-white dark:bg-slate-900 border-2 border-purple-200 dark:border-purple-700/50 shadow-2xl`}
          dir={isRTL ? 'rtl' : 'ltr'}
        >
          <DialogHeader className="sticky top-0 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-950/40 dark:to-blue-950/40 -mx-6 -mt-6 px-6 pt-6 pb-4 z-10 border-b border-purple-200 dark:border-purple-700/30">
            <DialogTitle className="flex items-center justify-between text-base sm:text-lg text-purple-900 dark:text-purple-100">
              <span className="font-extrabold">{t('quick_actions.title')}</span>
              <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8 sm:h-10 sm:w-10 text-purple-700 dark:text-purple-200 hover:bg-purple-200/50 dark:hover:bg-purple-800/50"><X size={18} /></Button>
            </DialogTitle>
            <DialogDescription className="text-xs sm:text-sm text-purple-700/80 dark:text-purple-300/80 mt-1">
              {t('quick_actions.subtitle', { defaultValue: 'اختر إجراء لهذه المركبة' })}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 sm:space-y-6 pb-4 pt-4">
            {/* Vehicle Info Card */}
            <div className="bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-950/40 dark:to-blue-950/30 p-4 rounded-xl border-2 border-purple-200 dark:border-purple-700/40 shadow-sm">
              <h3 className="font-extrabold text-lg sm:text-xl text-purple-900 dark:text-purple-50 mb-1">{vehicle.plateNumber}</h3>
              <p className="text-slate-700 dark:text-slate-300 text-xs sm:text-sm font-medium">{vehicle.brand} {vehicle.model} - {vehicle.year}</p>
              <p className="text-slate-600 dark:text-slate-400 text-xs sm:text-sm">{vehicle.customerName}</p>
            </div>

            {/* Status Update */}
            <div className="space-y-2 sm:space-y-3">
              <Label className="text-sm sm:text-base font-bold text-slate-800 dark:text-slate-100">{t('quick_actions.change_status')}</Label>
              <Select value={newStatus} onValueChange={setNewStatus}>
                <SelectTrigger className="w-full h-10 sm:h-11 border-2 border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {statusOptions.map(option => (
                    <SelectItem key={`status-${option.value}`} value={option.value}>
                      <div className="flex items-center gap-2">
                        <div className={`w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full ${option.color}`}></div>
                        <span className="text-sm">{option.label}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button onClick={handleStatusUpdate} disabled={loading || newStatus === vehicle.status} className="w-full h-10 sm:h-11 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white text-sm font-bold shadow-md">
                <CheckCircle size={16} className="ml-2" />{t('quick_actions.change_status')}
              </Button>
            </div>

            {/* Quick Actions Grid - 2 columns on mobile */}
            <div className="space-y-2 sm:space-y-3">
              <Label className="text-sm sm:text-base font-bold text-slate-800 dark:text-slate-100">{t('quick_actions.title')}</Label>

              <div className="grid grid-cols-2 gap-2">
                {/* Approval Request */}
                <Button data-testid="quick-actions-send-approval" onClick={handleRequestApproval} disabled={loading} variant="outline" className="h-auto py-3 px-2 flex-col gap-1 text-xs bg-purple-50 dark:bg-purple-950/40 border-2 border-purple-300 dark:border-purple-700/50 text-purple-800 dark:text-purple-100 hover:bg-purple-100 dark:hover:bg-purple-900/60 hover:border-purple-500 font-semibold">
                  <BadgeCheck size={20} className="text-purple-600 dark:text-purple-300" />
                  <span>{t('quick_actions.send_approval')}</span>
                </Button>

                {/* Diagnosis Report - Quick print dialog */}
                <Button onClick={() => openPrintDialog('diagnosis')} disabled={loading} variant="outline" className="h-auto py-3 px-2 flex-col gap-1 text-xs bg-blue-50 dark:bg-blue-950/40 border-2 border-blue-300 dark:border-blue-700/50 text-blue-800 dark:text-blue-100 hover:bg-blue-100 dark:hover:bg-blue-900/60 hover:border-blue-500 font-semibold">
                  <FileText size={20} className="text-blue-600 dark:text-blue-300" />
                  <span>{t('quick_actions.diagnosis_report')}</span>
                </Button>

                {/* Quote - Quick print dialog */}
                <Button onClick={() => openPrintDialog('quote')} disabled={loading} variant="outline" className="h-auto py-3 px-2 flex-col gap-1 text-xs bg-amber-50 dark:bg-amber-950/40 border-2 border-amber-300 dark:border-amber-700/50 text-amber-800 dark:text-amber-100 hover:bg-amber-100 dark:hover:bg-amber-900/60 hover:border-amber-500 font-semibold">
                  <FileText size={20} className="text-amber-600 dark:text-amber-300" />
                  <span>{t('quick_actions.print_quotation')}</span>
                </Button>

                {/* Invoice - Quick print dialog */}
                <Button onClick={() => openPrintDialog('invoice')} disabled={loading} variant="outline" className="h-auto py-3 px-2 flex-col gap-1 text-xs bg-indigo-50 dark:bg-indigo-950/40 border-2 border-indigo-300 dark:border-indigo-700/50 text-indigo-800 dark:text-indigo-100 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 hover:border-indigo-500 font-semibold">
                  <Printer size={20} className="text-indigo-600 dark:text-indigo-300" />
                  <span>{t('quick_actions.print_invoice')}</span>
                </Button>

                {/* Receipt - Quick print dialog */}
                <Button onClick={() => openPrintDialog('receipt')} disabled={loading} variant="outline" className="h-auto py-3 px-2 flex-col gap-1 text-xs bg-emerald-50 dark:bg-emerald-950/40 border-2 border-emerald-300 dark:border-emerald-700/50 text-emerald-800 dark:text-emerald-100 hover:bg-emerald-100 dark:hover:bg-emerald-900/60 hover:border-emerald-500 font-semibold">
                  <FileText size={20} className="text-emerald-600 dark:text-emerald-300" />
                  <span>{t('quick_actions.receipt')}</span>
                </Button>

                {/* Details */}
                <Button onClick={() => navigate(`/vehicle/${vehicle.id}`)} disabled={loading} variant="outline" className="h-auto py-3 px-2 flex-col gap-1 text-xs bg-slate-50 dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-600 text-slate-800 dark:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-700 hover:border-slate-500 font-semibold">
                  <FileText size={20} className="text-slate-600 dark:text-slate-300" />
                  <span>{t('quick_actions.details')}</span>
                </Button>

                {/* Parts - Navigate to vehicle page with parts tab */}
                <Button onClick={() => navigate(`/vehicle/${vehicle.id}?tab=parts`)} disabled={loading} variant="outline" className="h-auto py-3 px-2 flex-col gap-1 text-xs bg-sky-50 dark:bg-sky-950/40 border-2 border-sky-300 dark:border-sky-700/50 text-sky-800 dark:text-sky-100 hover:bg-sky-100 dark:hover:bg-sky-900/60 hover:border-sky-500 font-semibold">
                  <Package size={20} className="text-sky-600 dark:text-sky-300" />
                  <span>{t('quick_actions.spare_parts')}</span>
                </Button>

                {/* Operations */}
                <Button
                  onClick={() => navigate(`/operations?vehicleId=${vehicle.id}&plate=${encodeURIComponent(vehicle.plateNumber || '')}`)}
                  disabled={loading}
                  variant="outline"
                  className="h-auto py-3 px-2 flex-col gap-1 text-xs bg-orange-50 dark:bg-orange-950/40 border-2 border-orange-300 dark:border-orange-700/50 text-orange-800 dark:text-orange-100 hover:bg-orange-100 dark:hover:bg-orange-900/60 hover:border-orange-500 font-semibold"
                >
                  <Wrench size={20} className="text-orange-600 dark:text-orange-300" />
                  <span>{t('quick_actions.operations')}</span>
                </Button>
              </div>

              {/* Full Width Actions */}
              <div className="space-y-2 pt-2">
                <Button onClick={() => handleStatusUpdate('delivered')} disabled={loading} variant="outline" className="w-full h-10 justify-start text-sm bg-green-50 dark:bg-green-950/40 border-2 border-green-300 dark:border-green-700/50 text-green-800 dark:text-green-100 hover:bg-green-100 dark:hover:bg-green-900/60 font-semibold">
                  <CheckCircle size={16} className="ml-2 text-green-600 dark:text-green-300" />{t('status.delivered')}

      {/* WhatsApp Preview Dialog */}
      <Dialog open={whatsappPreviewOpen} onOpenChange={setWhatsappPreviewOpen}>
        <DialogContent className="w-[95vw] max-w-[620px] max-h-[90vh] overflow-y-auto bg-white dark:bg-slate-900 border-2 border-purple-200 dark:border-purple-700/50 shadow-2xl" dir="rtl">
          <DialogHeader>
            <DialogTitle className="text-purple-900 dark:text-purple-100">معاينة رسالة واتساب قبل الإرسال</DialogTitle>
            <DialogDescription>
              يمكنك نسخ الرسالة أو فتح واتساب لإرسالها.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <Textarea value={whatsappPreviewMessage} readOnly className="min-h-[240px] bg-slate-50 dark:bg-slate-800 border-2 border-purple-200 dark:border-purple-700/40" />

            <div className="flex flex-col sm:flex-row gap-2">
              <Button
                type="button"
                className="flex-1 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-bold shadow-md"
                onClick={() => {
                  // فتح واتساب (سيحوّل إلى الرابط)
                  sendToWhatsApp('approval', whatsappPreviewLink, whatsappPreviewMessage);
                }}
              >
                <Share2 className="ml-2" size={16} />
                فتح واتساب للإرسال
              </Button>

              <Button
                type="button"
                variant="outline"
                className="flex-1 bg-blue-50 dark:bg-blue-950/40 border-2 border-blue-300 dark:border-blue-700/50 text-blue-800 dark:text-blue-100 hover:bg-blue-100 dark:hover:bg-blue-900/60 font-semibold"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(whatsappPreviewMessage || '');
                    toast({ title: 'تم النسخ', description: 'تم نسخ رسالة واتساب إلى الحافظة' });
                  } catch (e) {
                    toast({ title: 'تنبيه', description: 'تعذر النسخ تلقائياً. يمكنك النسخ يدوياً من مربع النص.' });
                  }
                }}
              >
                <Copy className="ml-2" size={16} />
                نسخ الرسالة
              </Button>

              <Button type="button" variant="outline" onClick={() => setWhatsappPreviewOpen(false)}>
                إغلاق
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

                </Button>

                <Button onClick={handleDelete} disabled={loading} variant="destructive" className="w-full h-10 justify-start text-sm bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white font-bold shadow-md">
                  <Trash2 size={16} className="ml-2" />{t('quick_actions.delete_vehicle')}
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <DocumentFormDialog
        isOpen={documentDialogOpen}
        onClose={() => setDocumentDialogOpen(false)}
        documentType={currentDocType}
        vehicle={vehicle}
        onSaved={handleDocumentSaved}
      />

      {/* Approval Request Dialog */}
      <Dialog open={approvalDialogOpen} onOpenChange={setApprovalDialogOpen}>
        <DialogContent className="w-[95vw] max-w-[560px] max-h-[90vh] overflow-y-auto bg-white dark:bg-slate-900 border-2 border-purple-200 dark:border-purple-700/50 shadow-2xl" dir="rtl">
          <DialogHeader>
            <DialogTitle>طلب اعتماد من العميل</DialogTitle>
            <DialogDescription>أضف تفاصيل طلب الاعتماد وصور الأعطال</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label>عنوان الطلب</Label>
              <Input 
                value={approvalForm.title} 
                onChange={(e) => setApprovalForm(prev => ({...prev, title: e.target.value}))}
                placeholder="مثال: طلب اعتماد إصلاح المحرك"
              />
            </div>

            <div>
              <Label>المبلغ المتوقع (ريال)</Label>
              <Input 
                type="number"
                value={approvalForm.amount} 
                onChange={(e) => setApprovalForm(prev => ({...prev, amount: e.target.value}))}
                placeholder="0"
              />
            </div>

            <div>
              <Label>صلاحية الرابط</Label>
              <Select 
                value={approvalForm.expiryDays} 
                onValueChange={(val) => setApprovalForm(prev => ({...prev, expiryDays: val}))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="3">3 أيام</SelectItem>
                  <SelectItem value="7">7 أيام (افتراضي)</SelectItem>
                  <SelectItem value="14">14 يوم</SelectItem>
                  <SelectItem value="30">30 يوم</SelectItem>
                  <SelectItem value="365">بدون انتهاء</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label>صور الأعطال (اختياري - حتى 5 صور)</Label>
              <div className="mt-2 space-y-2">
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleApprovalImageChange}
                  className="hidden"
                  id="approval-images"
                />
                <label htmlFor="approval-images">
                  <Button type="button" variant="outline" className="w-full" asChild>
                    <span><Upload className="ml-2" size={16} />اختر صور</span>
                  </Button>
                </label>
                
                {approvalForm.images.length > 0 && (
                  <div className="grid grid-cols-3 gap-2">
                    {approvalForm.images.map((img, idx) => (
                      <div key={idx} className="relative group">
                        <img src={img.data} alt={`صورة ${idx + 1}`} className="w-full h-20 object-cover rounded border" />
                        <button
                          onClick={() => removeApprovalImage(idx)}
                          className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-1 opacity-0 group-hover:opacity-100"
                        >
                          <XCircle size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="flex gap-2">
              <Button onClick={submitApprovalRequest} disabled={loading} className="flex-1 bg-purple-600 hover:bg-purple-700">
                إنشاء + معاينة رسالة واتساب
              </Button>
              <Button onClick={() => setApprovalDialogOpen(false)} variant="outline" className="bg-white/5 border-purple-500/20 hover:bg-purple-500/10">
                إلغاء
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <QuickPrintDialog
        open={printDialogOpen}
        title={printDialogConfig?.title || 'خيارات الطباعة'}
        description="معاينة المستند قبل الطباعة أو الإرسال"
        payloadBuilder={printDialogConfig?.payloadBuilder}
        initialPhone={printDialogConfig?.phone}
        onClose={() => setPrintDialogOpen(false)}
      />
    </>
  );
};

export default VehicleQuickActions;