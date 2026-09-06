import React from 'react';
import { ArrowRight, ClipboardList, FileCheck, Printer, Receipt, X } from 'lucide-react';
import { AuthenticatedFileImage } from '../AuthenticatedFileImage';
import { getStatusColor, getStatusLabel } from '../../mock/data';
import { formatCurrency } from '../../utils/formatters';
import { OPERATION_TYPE_LABELS, labelFromMap, resolveVisitDisplay } from '../../utils/displayLabels';

export const VehicleDetailsStyles = ({ printMenuOpen, printVisitPickerOpen, printDialogConfig }) => (
  <style>{`
    .mobile-first-vehicle {
      font-family: Tajawal, Cairo, system-ui, sans-serif;
      overflow-x: hidden;
    }
    .mobile-first-vehicle :not(.font-mono) {
      letter-spacing: 0 !important;
    }
    .mobile-first-vehicle .liquid-surface,
    .mobile-first-vehicle .dash-widget-shell {
      max-width: 100%;
    }
    .mobile-first-vehicle button,
    .mobile-first-vehicle a,
    .mobile-first-vehicle input,
    .mobile-first-vehicle select,
    .mobile-first-vehicle textarea {
      touch-action: manipulation;
    }
    @media (max-width: 640px) {
      .mobile-first-vehicle .dash-widget-shell {
        border-radius: 20px !important;
      }
      .mobile-first-vehicle table {
        min-width: 640px;
      }
      .mobile-first-vehicle .vehicle-mobile-sticky-actions {
        position: sticky;
        bottom: 0;
        z-index: 35;
        margin-inline: -12px;
        padding: 12px;
        background: rgba(255,255,255,0.96);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-top: 1px solid rgba(203,213,225,0.85);
        box-shadow: 0 -10px 30px rgba(15,23,42,0.08);
      }
    }
    select { color: rgba(15,23,42,0.92); }
    option { color: #0f172a; }
    .vehicle-details-page [style*="100, 116, 139"] { color: rgba(51,65,85,0.95) !important; }
    .vehicle-details-page [style*="248, 250, 252, 0.6"] { background: rgba(248,250,252,0.96) !important; }
    .vehicle-details-page [style*="255, 255, 255, 0.8"] { background: rgba(255,255,255,0.96) !important; }
    ${(printMenuOpen || printVisitPickerOpen || printDialogConfig) ? '[data-testid^="unified-assistant"], [data-testid^="unified-bot"] { display: none !important; pointer-events: none !important; }' : ''}
  `}</style>
);

export const ArchiveEditBanner = () => (
  <div
    className="mx-3 sm:mx-0 rounded-2xl px-4 py-3"
    style={{
      background: 'rgba(56,189,248,0.12)',
      border: '1px solid rgba(56,189,248,0.28)',
      color: 'rgba(3,105,161,0.95)',
    }}
    data-testid="vehicle-archive-edit-mode-banner"
  >
    <div className="text-sm font-bold">وضع تحرير الأرشيف مفعل</div>
    <div className="text-xs mt-1" style={{ color: 'rgba(71,85,105,0.9)' }}>
      يمكنك تعديل بيانات المركبة والعميل والزيارات والبنود بالكامل. يتم تسجيل التعديلات في سجل الأرشيف.
    </div>
  </div>
);

export const VehicleDetailsHeader = ({ vehicle, isArchiveSource, navigate, printMenuOpen, setPrintMenuOpen }) => (
  <div
    className="liquid-surface"
    style={{
      padding: 16,
      borderRadius: 24,
      background: 'radial-gradient(circle at 12% 18%, rgba(248,250,252,0.98), rgba(241,245,249,0.96))',
      border: '1px solid rgba(203,213,225,0.8)',
    }}
    data-testid="vehicle-header"
  >
    <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center sm:justify-between gap-4">
      <div className="flex items-center gap-3 sm:gap-4 min-w-0 w-full sm:w-auto">
        <button
          onClick={() => navigate(isArchiveSource ? '/archive' : '/')}
          className="min-h-11 min-w-11 p-2 rounded-xl transition-[transform,background-color] duration-200 active:scale-95"
          style={{ background: 'rgba(255,255,255,0.8)', border: '1px solid rgba(203,213,225,0.8)', color: 'rgba(71,85,105,0.9)' }}
          data-testid="vehicle-back-button"
        >
          <ArrowRight size={22} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
            <h1 className="text-2xl sm:text-4xl font-black leading-tight tracking-normal" style={{ color: 'rgba(15,23,42,0.95)' }} data-testid="vehicle-plate-header">
              {vehicle.plateNumber}
            </h1>
            <span className={`px-3 py-1 rounded-full text-xs sm:text-sm font-bold ${getStatusColor(vehicle.status)}`} style={{ color: 'white' }} data-testid="vehicle-status-badge">
              {getStatusLabel(vehicle.status)}
            </span>
          </div>
          <p className="mt-1 text-sm sm:text-base leading-relaxed" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid="vehicle-brand-model-header">
            {vehicle.brand} {vehicle.model} - {vehicle.year}
          </p>
        </div>
      </div>

      <div className="flex gap-2 w-full sm:w-auto">
        <div className="relative">
          <button
            type="button"
            onClick={() => setPrintMenuOpen((open) => !open)}
            aria-expanded={printMenuOpen}
            aria-controls="vehicle-print-menu"
            className="min-h-11 w-full sm:w-auto px-3 py-2 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-[transform,background-color] duration-200 active:scale-95"
            style={{ background: 'rgba(255,255,255,0.8)', border: '1px solid rgba(203,213,225,0.8)', color: 'rgba(15,23,42,0.92)' }}
            data-testid="vehicle-print-menu-button"
          >
            <Printer size={16} />
            <span className="hidden sm:inline">طباعة / PDF</span>
          </button>
        </div>
      </div>
    </div>
  </div>
);

export const VehiclePrintMenu = ({ open, onClose, onPrint }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[2147483500] flex items-start justify-center bg-black/25 px-4 pt-24" data-testid="vehicle-print-menu-overlay">
      <div id="vehicle-print-menu" className="w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden" style={{ background: 'rgba(255,255,255,0.99)', border: '1px solid rgba(203,213,225,0.9)' }} data-testid="vehicle-print-menu">
        <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid rgba(203,213,225,0.8)' }}>
          <span className="text-sm font-bold" style={{ color: 'rgba(15,23,42,0.95)' }}>اختر نوع الطباعة</span>
          <button type="button" onClick={onClose} className="text-xs px-2 py-1 rounded-lg" data-testid="vehicle-print-menu-close">إغلاق</button>
        </div>
        <button type="button" onClick={(event) => onPrint(event, 'invoice')} className="w-full text-right px-4 py-3 flex items-center gap-2 text-sm transition-colors" style={{ color: 'rgba(15,23,42,0.9)' }} data-testid="vehicle-print-invoice">
          <Receipt size={16} style={{ color: 'rgba(4,120,87,0.95)' }} />
          <span>فاتورة مبيعات</span>
        </button>
        <button type="button" onClick={(event) => onPrint(event, 'quote')} className="w-full text-right px-4 py-3 flex items-center gap-2 text-sm transition-colors" style={{ borderTop: '1px solid rgba(203,213,225,0.8)', color: 'rgba(15,23,42,0.9)' }} data-testid="vehicle-print-quote">
          <FileCheck size={16} style={{ color: 'rgba(3,105,161,0.95)' }} />
          <span>عرض سعر</span>
        </button>
        <button type="button" onClick={(event) => onPrint(event, 'diagnosis')} className="w-full text-right px-4 py-3 flex items-center gap-2 text-sm transition-colors" style={{ borderTop: '1px solid rgba(203,213,225,0.8)', color: 'rgba(15,23,42,0.9)' }} data-testid="vehicle-print-diagnosis">
          <ClipboardList size={16} style={{ color: 'rgba(180,83,9,0.95)' }} />
          <span>تقرير تشخيص</span>
        </button>
      </div>
    </div>
  );
};

export const VehiclePrintVisitPicker = ({ open, visits, pendingHeaderPrintType, onClose, onPick }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[2147483501] flex items-start justify-center bg-black/30 px-4 pt-24" data-testid="vehicle-print-visit-picker-overlay">
      <div className="w-full max-w-md rounded-2xl shadow-2xl overflow-hidden" style={{ background: 'rgba(255,255,255,0.99)', border: '1px solid rgba(203,213,225,0.9)' }} data-testid="vehicle-print-visit-picker">
        <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid rgba(203,213,225,0.8)' }}>
          <span className="text-sm font-bold" style={{ color: 'rgba(15,23,42,0.95)' }}>اختر الزيارة للطباعة</span>
          <button type="button" onClick={onClose} className="text-xs px-2 py-1 rounded-lg" data-testid="vehicle-print-visit-picker-close">إلغاء</button>
        </div>
        <div className="max-h-[60vh] overflow-y-auto p-2" data-testid="vehicle-print-visit-picker-list">
          {visits.length === 0 ? (
            <div className="px-4 py-5 text-sm text-slate-500" data-testid="vehicle-print-visit-picker-empty">لا توجد زيارات قابلة للطباعة</div>
          ) : visits.map((visit, index) => {
            const visitDate = String(visit.entryDate || visit.entry_date || visit.created_at || visit.createdAt || '').slice(0, 10) || '—';
            const visitLabel = visit.invoiceNumber || visit.invoice_number || visit.documentNumber || visit.document_number || `زيارة ${index + 1}`;
            let parsedNotes = {};
            try { parsedNotes = typeof visit.notes === 'string' ? JSON.parse(visit.notes || '{}') : (visit.notes || {}); } catch (e) { parsedNotes = {}; }
            const approvedFinal = parsedNotes?.financial_finalization?.final_customer_total ?? visit.final_customer_total ?? visit.finalCustomerTotal;
            const hasApprovedFinal = approvedFinal !== null && approvedFinal !== undefined && approvedFinal !== '';
            const visitTotal = Number(hasApprovedFinal ? approvedFinal : (visit.total_workshop ?? visit.workshop_total ?? visit.total ?? 0)).toLocaleString('ar-SA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            return (
              <button key={visit.id || index} type="button" onClick={() => onPick(pendingHeaderPrintType, visit.id)} className="mb-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-right transition-colors hover:bg-slate-50" data-testid={`vehicle-print-visit-option-${visit.id}`}>
                <span className="block text-sm font-bold text-slate-900" data-testid={`vehicle-print-visit-option-title-${visit.id}`}>{visitLabel}</span>
                <span className="mt-1 block text-xs text-slate-500" data-testid={`vehicle-print-visit-option-meta-${visit.id}`}>التاريخ: {visitDate} · {hasApprovedFinal ? 'الإجمالي المعتمد' : 'مبلغ الورشة'}: {visitTotal}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export const VehicleFinancialSourceModal = ({ open, title, rows, onClose }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" data-testid="vehicle-financial-source-modal-overlay">
      <div className="liquid-surface w-full max-w-3xl max-h-[85vh] overflow-hidden" style={{ background: 'rgba(255,255,255,0.98)', border: '1px solid rgba(148,163,184,0.22)', borderRadius: 16 }} data-testid="vehicle-financial-source-modal">
        <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'rgba(203,213,225,0.8)' }}>
          <h3 className="text-sm font-extrabold" style={{ color: 'rgba(15,23,42,0.95)' }} data-testid="vehicle-financial-source-title">{title || 'مصدر الرقم'}</h3>
          <button onClick={onClose} className="px-3 py-1.5 rounded-xl text-xs" style={{ background: 'rgba(255,255,255,0.96)', border: '1px solid rgba(203,213,225,0.8)', color: 'rgba(30,41,59,0.95)' }} data-testid="vehicle-financial-source-close">إغلاق</button>
        </div>
        <div className="p-4 overflow-auto max-h-[70vh]" data-testid="vehicle-financial-source-content">
          {rows.length === 0 ? (
            <div className="text-xs" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid="vehicle-financial-source-empty">لا توجد بيانات مصدر ضمن الفترة الحالية.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs" data-testid="vehicle-financial-source-table">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'rgba(203,213,225,0.8)', color: 'rgba(100,116,139,0.9)' }}>
                    <th className="py-2 px-2 text-right">التاريخ</th>
                    <th className="py-2 px-2 text-right">الزيارة</th>
                    <th className="py-2 px-2 text-right">النوع</th>
                    <th className="py-2 px-2 text-right">الوصف</th>
                    <th className="py-2 px-2 text-right">المبلغ</th>
                    <th className="py-2 px-2 text-right">ملاحظة</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, idx) => (
                    <tr key={`${row.visitId}-${idx}`} className="border-b" style={{ borderColor: 'rgba(203,213,225,0.8)', color: 'rgba(15,23,42,0.92)' }} data-testid={`vehicle-financial-source-row-${idx}`}>
                      <td className="py-2 px-2">{row.date && row.date !== '-' ? new Date(row.date).toLocaleDateString('ar-SA') : '-'}</td>
                      <td className="py-2 px-2">{resolveVisitDisplay(row, '-')}</td>
                      <td className="py-2 px-2">{labelFromMap(row.type, OPERATION_TYPE_LABELS, '-')}</td>
                      <td className="py-2 px-2">{row.label || '-'}</td>
                      <td className="py-2 px-2">{formatCurrency(Number(row.amount || 0))} ر.س</td>
                      <td className="py-2 px-2">{row.note || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const ScannerModal = ({ open, videoRef, canvasRef, capturedImage, setCapturedImage, captureImage, uploadScannedImage, closeScanner }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4">
      <div className="liquid-surface max-w-lg w-full p-4 relative" style={{ background: 'rgba(255,255,255,0.98)', border: '1px solid rgba(203,213,225,0.8)' }} data-testid="scanner-modal">
        <button onClick={closeScanner} className="absolute top-4 left-4 p-2 rounded-full" style={{ background: 'rgba(255,255,255,0.96)', border: '1px solid rgba(203,213,225,0.8)', color: 'rgba(30,41,59,0.95)' }} data-testid="scanner-close-button">
          <X size={20} />
        </button>
        <h3 className="text-lg font-bold mb-4 text-center" style={{ color: 'rgba(15,23,42,0.95)' }} data-testid="scanner-title">التقاط صورة</h3>
        {!capturedImage ? (
          <div className="relative aspect-video bg-black rounded-lg overflow-hidden mb-4"><video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover" /></div>
        ) : (
          <div className="relative aspect-video bg-black rounded-lg overflow-hidden mb-4"><img src={capturedImage} alt="Captured" className="w-full h-full object-contain" data-testid="scanner-captured-image" /></div>
        )}
        <div className="flex gap-3">
          {!capturedImage ? (
            <button onClick={captureImage} className="flex-1 py-3 rounded-xl font-bold" style={{ background: 'rgba(56,189,248,0.18)', border: '1px solid rgba(56,189,248,0.32)', color: 'rgba(3,105,161,0.95)' }} data-testid="scanner-capture-button">التقاط</button>
          ) : (
            <>
              <button onClick={() => setCapturedImage(null)} className="flex-1 py-3 rounded-xl font-bold" style={{ background: 'rgba(255,255,255,0.96)', border: '1px solid rgba(203,213,225,0.8)', color: 'rgba(30,41,59,0.95)' }} data-testid="scanner-retake-button">إعادة</button>
              <button onClick={uploadScannedImage} className="flex-1 py-3 rounded-xl font-bold" style={{ background: 'rgba(16,185,129,0.2)', border: '1px solid rgba(16,185,129,0.32)', color: 'rgba(4,120,87,0.95)' }} data-testid="scanner-save-button">حفظ</button>
            </>
          )}
        </div>
        <canvas ref={canvasRef} className="hidden" />
      </div>
    </div>
  );
};

export const PreviewOverlay = ({ previewImage, onClose }) => {
  if (!previewImage) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4" onClick={onClose} data-testid="preview-overlay">
      <button className="absolute top-4 left-4 p-2 rounded-full" style={{ background: 'rgba(255,255,255,0.96)', border: '1px solid rgba(203,213,225,0.8)', color: 'rgba(15,23,42,0.95)' }} onClick={onClose} data-testid="preview-close-button">
        <X size={32} />
      </button>
      <AuthenticatedFileImage
        src={previewImage}
        alt="Preview"
        className="max-w-full max-h-[90vh] object-contain rounded-lg"
        testId="vehicle-file-preview-image"
      />
    </div>
  );
};