import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import ConfirmPaymentDialog from '../components/ConfirmPaymentDialog';
import axios from 'axios';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { ArrowRight, Car, User, Phone, Calendar, Wrench, CheckCircle, FileText, Upload, Printer, Receipt, Clock, Trash2, Camera, X, Scan, Plus, ChevronDown, ChevronUp, Edit2, Save, XCircle, FileCheck, ClipboardList, MessageCircle } from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import GuidanceStepper from '../components/GuidanceStepper';
import { vehicleAPI, technicianAPI, financeAPI, customerAPI, visitAPI, serviceAPI, partAPI, supplierAPI, vehicleFinanceAPI } from '../services/api';
import VisitDeleteConfirmDialog from '../components/VisitDeleteConfirmDialog';
import WhatsAppPreviewDialog from '../components/WhatsAppPreviewDialog';
import VehicleFinancialSummary from '../components/VehicleFinancialSummary';
import QuickPrintDialog from '../components/QuickPrintDialog';
import { statusSteps, getStatusLabel, getStatusColor } from '../mock/data';
import { useTranslation } from 'react-i18next';
import { formatCurrency } from '../utils/formatters';
import { OPERATION_TYPE_LABELS, SOURCE_LABELS, labelFromMap, resolveVisitDisplay } from '../utils/displayLabels';
import {
  DndContext,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { userLayoutsAPI } from '../services/userLayoutsAPI';
import { resolveBackendBase } from '../utils/backendBase';
import { generateIdempotencyKey } from '../utils/idempotency';

const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase()}/api`.replace('//api', '/api')
);
const FILE_BASE = process.env.NODE_ENV === 'production' ? '' : (resolveBackendBase() || '');

const ARCHIVE_AUDIT_KEY = 'vehicle-archive-edit-audit-v1';

const appendArchiveAudit = (payload = {}) => {
  try {
    const raw = localStorage.getItem(ARCHIVE_AUDIT_KEY);
    const rows = raw ? JSON.parse(raw) : [];
    const entry = {
      timestamp: new Date().toISOString(),
      action: payload.action || 'archive_edit',
      actionLabel: payload.actionLabel || 'تعديل من الأرشيف',
      vehicleId: payload.vehicleId || '',
      plateNumber: payload.plateNumber || '',
      fileNumber: payload.fileNumber || '',
      details: payload.details || {},
      timeLabel: new Date().toLocaleString('ar-SA'),
    };
    const next = [entry, ...(Array.isArray(rows) ? rows : [])].slice(0, 120);
    localStorage.setItem(ARCHIVE_AUDIT_KEY, JSON.stringify(next));
  } catch (e) {
    console.warn('archive_audit_storage_failed', e);
  }
};

// --- Helper Components ---

const pickEntityName = (row) => {
  if (!row || typeof row !== 'object') return '';
  return (
    row.name ||
    row.fullName ||
    row.customerName ||
    row.customer_name ||
    row.supplierName ||
    row.supplier_name ||
    row.title ||
    ''
  )
    .toString()
    .trim();
};

const normalizePartyCatalog = (rows = [], entityPrefix = 'entity') => {
  if (!Array.isArray(rows)) return [];
  const seen = new Set();
  const normalized = [];

  rows.forEach((row, index) => {
    const name = pickEntityName(row);
    if (!name) return;
    const normalizedKey = name.toLowerCase();
    if (seen.has(normalizedKey)) return;
    seen.add(normalizedKey);

    normalized.push({
      ...row,
      id: row?.id || row?._id || `${entityPrefix}-${index}-${normalizedKey}`,
      name,
    });
  });

  return normalized;
};

const extractJournalTag = (text = '', tag = '') => {
  if (!tag) return '';
  const match = String(text || '').match(new RegExp(`\\[${tag}:([^\\]]+)\\]`, 'i'));
  return String(match?.[1] || '').trim();
};

const stripJournalTags = (text = '') => String(text || '')
  .replace(/\[PARTY:[^\]]+\]/gi, '')
  .replace(/\[PARTY_TYPE:[^\]]+\]/gi, '')
  .replace(/\[VEHICLE_REF:[^\]]+\]/gi, '')
  .replace(/\[VISIT:[^\]]+\]/gi, '')
  .replace(/\s{2,}/g, ' ')
  .trim();

const RAKAN_SUPPLIER_NAMES = new Set(['راكان', 'rakan', 'Rakan', 'RAKAN']);

const isRakanSupplierName = (value) => {
  const v = String(value || '').trim();
  if (!v) return false;
  if (RAKAN_SUPPLIER_NAMES.has(v)) return true;
  return v.includes('راكان') || v.toLowerCase().includes('rakan');
};

const ABU_KHALED_NAMES = new Set(['أبو خالد الكبير', 'ابو خالد الكبير', 'أبو خالد', 'ابو خالد']);

const isAbuKhaledSupplier = (value) => {
  const v = String(value || '').trim();
  if (!v) return false;
  if (ABU_KHALED_NAMES.has(v)) return true;
  return v.includes('أبو خالد الكبير') || v.includes('ابو خالد الكبير');
};

// ─── مكوّن اختيار قطعة لمورد أبو خالد الكبير → حساب 042 ────────────────────
const WorkshopSupplierPartPicker = ({ item, onChange, partsCatalog = [], rowId, visitId, variant = 'row' }) => {
  // يظهر فقط لمورد "أبو خالد الكبير"
  if (!isAbuKhaledSupplier(item.name)) return null;

  const linkedValue = String(item.linkedPart || '').trim();
  const matched = partsCatalog.find((p) => (p.name || '').trim() === linkedValue);
  const showManual = Boolean(item.linkedPartManualEntry || (linkedValue && !matched));
  const baseTestId = `visit-item-workshop-part-${variant}-${visitId}-${rowId}`;

  return (
    <div
      className="space-y-2 mt-2 p-2 rounded-lg"
      style={{
        background: 'rgba(239,246,255,0.8)',
        border: '1px solid rgba(59,130,246,0.22)',
      }}
      data-testid={`${baseTestId}-wrapper`}
    >
      <select
        value={showManual ? '__manual__' : linkedValue}
        onChange={(e) => {
          const val = e.target.value;
          if (val === '__manual__') {
            onChange('linkedPartManualEntry', true);
            onChange('linkedPart', '');
            onChange('revenueAccountCode', '042');
            return;
          }
          onChange('linkedPartManualEntry', false);
          onChange('linkedPart', val);
          onChange('revenueAccountCode', '042');
        }}
        className="w-full text-xs sm:text-sm rounded-lg p-2"
        style={{
          background: 'rgba(255,255,255,0.8)',
          border: '1px solid rgba(59,130,246,0.30)',
          color: 'rgba(15,23,42,0.92)',
        }}
        data-testid={`${baseTestId}-select`}
      >
        <option value="">اختر القطعة (ايراد قطع الورشة)</option>
        {partsCatalog.map((p) => (
          <option key={p.id || p.name} value={p.name}>
            {p.name}
          </option>
        ))}
        <option value="__manual__">إدخال يدوي</option>
      </select>

      {showManual && (
        <input
          type="text"
          value={item.linkedPart || ''}
          onChange={(e) => {
            onChange('linkedPartManualEntry', true);
            onChange('linkedPart', e.target.value);
            onChange('revenueAccountCode', '042');
          }}
          className="w-full text-xs sm:text-sm rounded-lg p-2"
          style={{
            background: 'rgba(255,255,255,0.8)',
            border: '1px solid rgba(59,130,246,0.30)',
            color: 'rgba(15,23,42,0.92)',
          }}
          placeholder="اكتب اسم القطعة يدوياً"
          data-testid={`${baseTestId}-manual`}
        />
      )}
    </div>
  );
};

const RakanLinkedPartPicker = ({ item, onChange, partsCatalog = [], rowId, visitId, variant = 'row' }) => {
  // 🔥 Rakan-specific component disabled (Feb 2026). Returns null — never renders.
  return null;
};

const VisitItemRow = ({
  item,
  isEditing,
  onChange,
  onDelete,
  servicesCatalog = [],
  partsCatalog = [],
  suppliersCatalog = [],
  customersCatalog = [],
  rowId,
  visitId,
}) => {
  if (!isEditing) {
    const typeLabel = item.itemType === 'part'
      ? 'قطعة'
      : item.itemType === 'supplier'
      ? 'مورد'
      : item.itemType === 'customer'
      ? 'عميل'
      : 'خدمة';
    return (
      <tr className="border-b" style={{ borderColor: 'rgba(203,213,225,0.8)', background: 'transparent' }}>
        <td className="py-2 px-3 text-xs" style={{ color: 'rgba(71,85,105,0.9)' }}>
          {typeLabel}
        </td>
        <td className="py-2 px-3 text-xs font-semibold" style={{ color: 'rgba(15,23,42,0.95)' }}>{item.name}</td>
        <td className="py-2 px-3 text-xs text-center font-medium" style={{ color: 'rgba(30,41,59,0.9)' }}>{item.quantity}</td>
        <td className="py-2 px-3 text-xs text-center font-medium" style={{ color: 'rgba(30,41,59,0.9)' }}>{item.price}</td>
        <td className="py-2 px-3 text-xs font-bold text-right tabular-nums" style={{ color: 'rgba(3,105,161,0.95)' }}>
          {formatCurrency(item.total ?? (item.quantity * item.price))}
          {item._priceQtyMismatch && (
            <span className="mr-1 text-[9px] text-amber-400" title={`السعر × الكمية = ${item.quantity * item.price} ر.س`}>⚠</span>
          )}
        </td>
      </tr>
    );
  }

  const options = item.itemType === 'part'
    ? partsCatalog
    : item.itemType === 'supplier'
    ? suppliersCatalog
    : item.itemType === 'customer'
    ? customersCatalog
    : servicesCatalog;
  const listId = `${item.itemType}-list-${rowId}`;
  const isPartyType = item.itemType === 'supplier' || item.itemType === 'customer';
  const partyLabel = item.itemType === 'supplier' ? 'المورد' : 'العميل';
  const matchedParty = options.find((opt) => (opt.name || '').trim() === (item.name || '').trim());
  const showManualPartyInput = Boolean(item.manualPartyEntry || (item.name && !matchedParty));

  const handleNameChange = (value) => {
    onChange('name', value);
    if (isPartyType) return;
    const match = options.find((opt) => (opt.name || '').trim() === value.trim());
    if (match) {
      const price = match.price ?? match.sellingPrice ?? match.selling_price ?? match.purchasePrice ?? 0;
      onChange('price', Number(price) || 0);
    }
  };

  return (
    <tr className="border-b" style={{ borderColor: 'rgba(56,189,248,0.18)', background: 'rgba(240,249,255,0.8)' }}>
      <td className="p-2 min-w-[90px]">
        <select
          value={item.itemType}
          onChange={(e) => onChange('itemType', e.target.value)}
          className="w-full text-xs sm:text-sm rounded-lg p-2"
          style={{
            background: 'rgba(255,255,255,0.8)',
            border: '1px solid rgba(203,213,225,0.8)',
            color: 'rgba(15,23,42,0.92)',
          }}
          data-testid={`visit-item-type-${visitId}-${rowId}`}
        >
          <option value="service">خدمة</option>
          <option value="part">قطعة</option>
          <option value="customer">عميل</option>
          <option value="supplier">مورد</option>
        </select>
      </td>
      <td className="p-2 min-w-[160px]">
        {isPartyType ? (
          <div className="space-y-2">
            <select
              value={showManualPartyInput ? '__manual__' : (item.name || '')}
              onChange={(e) => {
                const value = e.target.value;
                if (value === '__manual__') {
                  onChange('manualPartyEntry', true);
                  onChange('name', '');
                  return;
                }
                onChange('manualPartyEntry', false);
                handleNameChange(value);
              }}
              className="w-full min-w-[140px] sm:min-w-[220px] text-xs sm:text-sm rounded-lg p-2"
              style={{
                background: 'rgba(255,255,255,0.8)',
                border: '1px solid rgba(203,213,225,0.8)',
                color: 'rgba(15,23,42,0.92)',
              }}
              data-testid={`visit-item-party-select-${visitId}-${rowId}`}
            >
              <option value="">اختر {partyLabel}</option>
              {options.map((party) => (
                <option key={party.id || party.name} value={party.name}>
                  {party.name}
                </option>
              ))}
              <option value="__manual__">إدخال يدوي</option>
            </select>

            {showManualPartyInput && (
              <input
                type="text"
                value={item.name || ''}
                onChange={(e) => {
                  onChange('manualPartyEntry', true);
                  onChange('name', e.target.value);
                }}
                className="w-full min-w-[140px] sm:min-w-[220px] text-xs sm:text-sm rounded-lg p-2"
                style={{
                  background: 'rgba(255,255,255,0.8)',
                  border: '1px solid rgba(203,213,225,0.8)',
                  color: 'rgba(15,23,42,0.92)',
                }}
                placeholder={`اكتب اسم ${partyLabel} يدويًا`}
                data-testid={`visit-item-party-manual-${visitId}-${rowId}`}
              />
            )}

            {item.itemType === 'supplier' && (
              <>
                <RakanLinkedPartPicker
                  item={item}
                  onChange={onChange}
                  partsCatalog={partsCatalog}
                  rowId={rowId}
                  visitId={visitId}
                  variant="row"
                />
                <WorkshopSupplierPartPicker
                  item={item}
                  onChange={onChange}
                  partsCatalog={partsCatalog}
                  rowId={rowId}
                  visitId={visitId}
                  variant="row"
                />
              </>
            )}
          </div>
        ) : (
          <>
            <input
              type="text"
              list={listId}
              value={item.name}
              onChange={(e) => handleNameChange(e.target.value)}
              className="w-full min-w-[140px] sm:min-w-[220px] text-xs sm:text-sm rounded-lg p-2"
              style={{
                background: 'rgba(255,255,255,0.8)',
                border: '1px solid rgba(203,213,225,0.8)',
                color: 'rgba(15,23,42,0.92)',
              }}
              placeholder={item.itemType === 'part' ? 'اسم القطعة' : 'اسم الخدمة'}
              data-testid={`visit-item-name-${visitId}-${rowId}`}
            />
            <datalist id={listId}>
              {options.map((opt) => (
                <option key={opt.id || opt.name} value={opt.name} />
              ))}
            </datalist>
          </>
        )}
      </td>
      <td className="p-2">
        <input
          type="number"
          value={item.quantity}
          onChange={(e) => onChange('quantity', Number(e.target.value))}
          className="w-16 sm:w-20 text-xs sm:text-sm rounded-lg p-2 text-center"
          style={{
            background: 'rgba(255,255,255,0.8)',
            border: '1px solid rgba(203,213,225,0.8)',
            color: 'rgba(15,23,42,0.92)',
          }}
          min="1"
          data-testid={`visit-item-quantity-${visitId}-${rowId}`}
        />
      </td>
      <td className="p-2">
        <input
          type="number"
          value={item.price}
          onChange={(e) => onChange('price', Number(e.target.value))}
          className="w-20 sm:w-24 text-xs sm:text-sm rounded-lg p-2 text-center"
          style={{
            background: 'rgba(255,255,255,0.8)',
            border: '1px solid rgba(203,213,225,0.8)',
            color: 'rgba(15,23,42,0.92)',
          }}
          min="0"
          data-testid={`visit-item-price-${visitId}-${rowId}`}
        />
      </td>
      <td className="p-2 text-right">
        <button
          onClick={onDelete}
          className="p-2 rounded-lg"
          style={{ color: 'rgba(159,18,57,0.95)', background: 'rgba(254,242,242,0.8)', border: '1px solid rgba(244,63,94,0.3)' }}
          title="حذف"
          data-testid={`visit-item-delete-${visitId}-${rowId}`}
        >
          <Trash2 size={14} />
        </button>
      </td>
    </tr>
  );
};

const DragHandle = ({ listeners, attributes, blockId }) => {
  return (
    <button
      type="button"
      className="p-2 rounded-xl"
      style={{
        background: 'rgba(255,255,255,0.8)',
        border: '1px solid rgba(203,213,225,0.8)',
        color: 'rgba(71,85,105,0.9)',
        cursor: 'grab',
        touchAction: 'none',
      }}
      title="سحب لتغيير المكان"
      {...attributes}
      {...listeners}
      data-testid={`layout-drag-handle-${blockId}`}
    >
      <span className="text-lg leading-none">⋮⋮</span>
    </button>
  );
};

const SortableBlock = ({ id, title, children }) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.75 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} data-testid={`layout-block-${id}`}>
      <div
        className="liquid-surface"
        style={{
          borderRadius: 22,
          padding: 12,
          background: 'rgba(241,245,249,0.8)',
          border: '1px solid rgba(203,213,225,0.8)',
          boxShadow: '0 18px 60px rgba(2,6,23,0.55)',
        }}
      >
        <div className="flex items-center justify-between gap-3 mb-2">
          <div className="min-w-0">
            <div
              className="text-[13px] font-extrabold truncate"
              style={{ color: 'rgba(15,23,42,0.95)' }}
              data-testid={`layout-block-title-${id}`}
            >
              {title}
            </div>
          </div>
          <DragHandle listeners={listeners} attributes={attributes} blockId={id} />
        </div>
        <div>{children}</div>
      </div>
    </div>
  );
};

const VisitItemCard = ({
  item,
  isEditing,
  onChange,
  onDelete,
  servicesCatalog = [],
  partsCatalog = [],
  suppliersCatalog = [],
  customersCatalog = [],
  rowId,
  visitId,
}) => {
  const options = item.itemType === 'part'
    ? partsCatalog
    : item.itemType === 'supplier'
    ? suppliersCatalog
    : item.itemType === 'customer'
    ? customersCatalog
    : servicesCatalog;
  const listId = `${item.itemType}-list-card-${rowId}`;
  const amount = Number(item.quantity || 0) * Number(item.price || 0);
  const isPartyType = item.itemType === 'supplier' || item.itemType === 'customer';
  const partyLabel = item.itemType === 'supplier' ? 'المورد' : 'العميل';
  const matchedParty = options.find((opt) => (opt.name || '').trim() === (item.name || '').trim());
  const showManualPartyInput = Boolean(item.manualPartyEntry || (item.name && !matchedParty));

  const typeLabel = item.itemType === 'part'
    ? 'قطعة'
    : item.itemType === 'supplier'
    ? 'مورد'
    : item.itemType === 'customer'
    ? 'عميل'
    : 'خدمة';
  const typeAccent = item.itemType === 'part' ? 'rose' : isPartyType ? 'amber' : 'violet';
  const typeStyle =
    typeAccent === 'rose'
      ? {
          background: 'rgba(244,63,94,0.15)',
          border: '1px solid rgba(244,63,94,0.3)',
          color: 'rgba(159,18,57,0.95)',
        }
      : typeAccent === 'amber'
      ? {
          background: 'rgba(245,158,11,0.2)',
          border: '1px solid rgba(245,158,11,0.4)',
          color: 'rgba(180,83,9,0.95)',
        }
      : {
          background: 'rgba(168,85,247,0.15)',
          border: '1px solid rgba(168,85,247,0.3)',
          color: 'rgba(107,33,168,0.95)',
        };

  const handleNameChange = (value) => {
    onChange('name', value);
    if (isPartyType) return;
    const match = options.find((opt) => (opt.name || '').trim() === value.trim());
    if (match) {
      const price = match.price ?? match.sellingPrice ?? match.selling_price ?? match.purchasePrice ?? 0;
      onChange('price', Number(price) || 0);
    }
  };

  return (
    <div
      className="liquid-surface"
      style={{
        borderRadius: 18,
        padding: 12,
        background:
          'radial-gradient(circle at 14% 18%, rgba(248,250,252,0.98), rgba(241,245,249,0.96))',
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="inline-flex items-center gap-2">
            <span className="px-2 py-0.5 rounded-full text-[11px]" style={typeStyle}>
              {typeLabel}
            </span>
            <div className="text-[11px]" style={{ color: 'rgba(100,116,139,0.9)' }}>
              {isEditing ? 'تعديل بند' : 'بند'}
            </div>
          </div>
          {!isEditing ? (
            <div className="mt-2 text-sm font-semibold truncate" style={{ color: 'rgba(15,23,42,0.92)' }}>
              {item.name || '—'}
            </div>
          ) : (
            <div className="mt-2 grid grid-cols-1 gap-2">
              <select
                value={item.itemType}
                onChange={(e) => onChange('itemType', e.target.value)}
                className="w-full text-sm rounded-lg p-2"
                style={{
                  background: 'rgba(255,255,255,0.8)',
                  border: '1px solid rgba(203,213,225,0.8)',
                  color: 'rgba(15,23,42,0.92)',
                }}
                data-testid={`visit-item-type-card-${visitId}-${rowId}`}
              >
                <option value="service">خدمة</option>
                <option value="part">قطعة</option>
                <option value="customer">عميل</option>
                <option value="supplier">مورد</option>
              </select>

              {isPartyType ? (
                <div className="space-y-2">
                  <select
                    value={showManualPartyInput ? '__manual__' : (item.name || '')}
                    onChange={(e) => {
                      const value = e.target.value;
                      if (value === '__manual__') {
                        onChange('manualPartyEntry', true);
                        onChange('name', '');
                        return;
                      }
                      onChange('manualPartyEntry', false);
                      handleNameChange(value);
                    }}
                    className="w-full text-sm rounded-lg p-2"
                    style={{
                      background: 'rgba(255,255,255,0.8)',
                      border: '1px solid rgba(203,213,225,0.8)',
                      color: 'rgba(15,23,42,0.92)',
                    }}
                    data-testid={`visit-item-party-select-card-${visitId}-${rowId}`}
                  >
                    <option value="">اختر {partyLabel}</option>
                    {options.map((party) => (
                      <option key={party.id || party.name} value={party.name}>
                        {party.name}
                      </option>
                    ))}
                    <option value="__manual__">إدخال يدوي</option>
                  </select>

                  {showManualPartyInput && (
                    <input
                      type="text"
                      value={item.name || ''}
                      onChange={(e) => {
                        onChange('manualPartyEntry', true);
                        onChange('name', e.target.value);
                      }}
                      className="w-full text-sm rounded-lg p-2"
                      style={{
                        background: 'rgba(255,255,255,0.8)',
                        border: '1px solid rgba(203,213,225,0.8)',
                        color: 'rgba(15,23,42,0.92)',
                      }}
                      placeholder={`اكتب اسم ${partyLabel} يدويًا`}
                      data-testid={`visit-item-party-manual-card-${visitId}-${rowId}`}
                    />
                  )}

                  {item.itemType === 'supplier' && (
                    <>
                      <RakanLinkedPartPicker
                        item={item}
                        onChange={onChange}
                        partsCatalog={partsCatalog}
                        rowId={rowId}
                        visitId={visitId}
                        variant="card"
                      />
                      <WorkshopSupplierPartPicker
                        item={item}
                        onChange={onChange}
                        partsCatalog={partsCatalog}
                        rowId={rowId}
                        visitId={visitId}
                        variant="card"
                      />
                    </>
                  )}
                </div>
              ) : (
                <>
                  <input
                    type="text"
                    list={listId}
                    value={item.name}
                    onChange={(e) => handleNameChange(e.target.value)}
                    className="w-full text-sm rounded-lg p-2"
                    style={{
                      background: 'rgba(255,255,255,0.8)',
                      border: '1px solid rgba(203,213,225,0.8)',
                      color: 'rgba(15,23,42,0.92)',
                    }}
                    placeholder={item.itemType === 'part' ? 'اسم القطعة' : 'اسم الخدمة'}
                    data-testid={`visit-item-name-card-${visitId}-${rowId}`}
                  />
                  <datalist id={listId}>
                    {options.map((opt) => (
                      <option key={opt.id || opt.name} value={opt.name} />
                    ))}
                  </datalist>
                </>
              )}
            </div>
          )}
        </div>

        {isEditing && (
          <button
            onClick={onDelete}
            className="p-2 rounded-lg shrink-0"
            style={{
              color: 'rgba(159,18,57,0.95)',
              background: 'rgba(254,242,242,0.8)',
              border: '1px solid rgba(244,63,94,0.22)',
            }}
            title="حذف"
            data-testid={`visit-item-delete-card-${visitId}-${rowId}`}
          >
            <Trash2 size={16} />
          </button>
        )}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <div>
          <div className="text-[11px]" style={{ color: 'rgba(100,116,139,0.9)' }}>الكمية</div>
          {!isEditing ? (
            <div className="mt-1 text-sm font-semibold tabular-nums" style={{ color: 'rgba(15,23,42,0.92)' }}>
              {item.quantity}
            </div>
          ) : (
            <input
              type="number"
              value={item.quantity}
              onChange={(e) => onChange('quantity', Number(e.target.value))}
              className="mt-1 w-full text-sm rounded-lg p-2"
              style={{
                background: 'rgba(255,255,255,0.8)',
                border: '1px solid rgba(203,213,225,0.8)',
                color: 'rgba(15,23,42,0.92)',
              }}
              min="1"
              data-testid={`visit-item-quantity-card-${visitId}-${rowId}`}
            />
          )}
        </div>

        <div>
          <div className="text-[11px]" style={{ color: 'rgba(100,116,139,0.9)' }}>السعر</div>
          {!isEditing ? (
            <div className="mt-1 text-sm font-semibold tabular-nums" style={{ color: 'rgba(15,23,42,0.92)' }}>
              {item.price}
            </div>
          ) : (
            <input
              type="number"
              value={item.price}
              onChange={(e) => onChange('price', Number(e.target.value))}
              className="mt-1 w-full text-sm rounded-lg p-2"
              style={{
                background: 'rgba(255,255,255,0.8)',
                border: '1px solid rgba(203,213,225,0.8)',
                color: 'rgba(15,23,42,0.92)',
              }}
              min="0"
              data-testid={`visit-item-price-card-${visitId}-${rowId}`}
            />
          )}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <div className="text-[11px]" style={{ color: 'rgba(100,116,139,0.9)' }}>الإجمالي</div>
        <div className="text-sm font-extrabold tabular-nums" style={{ color: 'rgba(3,105,161,0.95)' }}>
          {formatCurrency(amount)}
        </div>
      </div>
    </div>
  );
};

const VisitCard = ({
  visit,
  vehicle,
  technicians,
  onUpdate,
  onDelete,
  onVisitClosed,
  onShowWhatsAppPreview,
  approvals = [],
  servicesCatalog = [],
  partsCatalog = [],
  suppliersCatalog = [],
  customersCatalog = [],
  onServiceAdded,
  onPartAdded,
  onSupplierAdded,
  canDelete = false,
  archiveMode = false,
  onAuditEvent,
  onOpenQuickPrintDialog,
}) => {
  const [isExpanded, setIsExpanded] = useState((visit.status || 'in_progress') === 'in_progress');
  const [items, setItems] = useState([]);
  const [payments, setPayments] = useState([]);
  const [originalPayments, setOriginalPayments] = useState([]);
  const [paymentDraft, setPaymentDraft] = useState({ kind: 'advance', amount: '', method: 'cash' });
  const [status, setStatus] = useState(visit.status);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [whatsappNotification, setWhatsappNotification] = useState(null);
  const [techId, setTechId] = useState(visit.technicianId || visit.technician_id || '');
  const visitNumberLabel = resolveVisitDisplay(visit, '---');
  const [notes, setNotes] = useState(visit.notes || '');
  const [mileage, setMileage] = useState(visit.mileage || '');
  const [confirmPayOpen, setConfirmPayOpen] = useState(false);
  const [confirmPayLoading, setConfirmPayLoading] = useState(false);

  // Ref to preserve whatsapp notification across re-renders
  const whatsappNotificationRef = useRef(null);

  const { toast } = useToast();
  const activeWorkshopId = process.env.REACT_APP_WORKSHOP_ID || vehicle?.workshopId || vehicle?.workshop_id || 'finmodule-sync';
  const paymentMethodLabelMap = {
    bank: 'بنك/تحويل',
    cash: 'نقد',
    pos: 'نقاط بيع',
    supplier_balance: 'رصيد مورد',
  };

  const deleteJournalEntries = async (entryIds = []) => {
    const ids = (entryIds || []).filter(Boolean);
    for (const entryId of ids) {
      await axios.delete(`${API_URL}/finance/journal-entries/${entryId}`, {
        params: { workshop_id: activeWorkshopId },
      });
    }
  };

  const syncPaymentJournalEntries = async (paymentRows = []) => {
    const paymentAccounts = {
      cash: { code: '003', name: 'النقد' },
      bank: { code: '004', name: 'البنك' },
      pos: { code: '006', name: 'نقاط بيع' },
    };
    const DISCOUNT_ACCOUNT = { code: '024', name: 'خصم مسموح به للعملاء' };
    const createdIds = [];
    const syncedPayments = [];

    for (const row of paymentRows) {
      const method = String(row?.paymentMethod || row?.method || 'cash').trim().toLowerCase();
      const amount = Number(row?.amount || 0);
      const rowKind = String(row?.kind || '').trim().toLowerCase();
      const isDiscount = rowKind === 'discount';
      const normalizedRow = {
        ...row,
        method,
        paymentMethod: method,
      };

      if (!(amount > 0) || method === 'supplier_balance' || row?.journalEntryId) {
        syncedPayments.push(normalizedRow);
        continue;
      }

      const paymentDate = String(row?.date || new Date().toISOString()).slice(0, 10);
      const customerName = String(vehicle?.customerName || 'عميل').trim() || 'عميل';
      const vehicleRef = String(vehicle?.plateNumber || vehicle?.plate_number || '').trim();

      let description;
      let lines;
      let txType;
      let source;

      if (isDiscount) {
        // قيد الخصم: مدين خصم مسموح به / دائن العملاء
        description = ['خصم ممنوح للعميل', customerName, vehicleRef].filter(Boolean).join(' — ');
        txType = 'discount';
        source = 'visit_discount';
        lines = [
          { account: DISCOUNT_ACCOUNT.code, account_name: DISCOUNT_ACCOUNT.name, debit: amount, credit: 0 },
          { account: '005', account_name: 'العملاء', debit: 0, credit: amount },
        ];
      } else {
        // قيد الدفع العادي
        const paymentAccount = paymentAccounts[method] || paymentAccounts.cash;
        const isAdvance = rowKind === 'advance';
        description = [
          isAdvance ? 'سند قبض — دفعة مقدمة' : 'سند قبض — تحت الحساب',
          customerName,
          vehicleRef,
        ].filter(Boolean).join(' — ');
        txType = 'payment';
        source = 'visit_receipt_voucher';
        lines = [
          { account: paymentAccount.code, account_name: paymentAccount.name, debit: amount, credit: 0 },
          { account: '005', account_name: 'العملاء', debit: 0, credit: amount },
        ];
      }

      // 🔒 مفتاح Idempotency فريد لكل دفعة — يحمي من التكرار/النقر المزدوج
      const idemKey = generateIdempotencyKey(
        isDiscount ? 'visit-discount' : 'visit-payment',
        `${visit.id}-${row?.id || amount}`
      );
      const response = await axios.post(`${API_URL}/finance/journal-entries`, {
        date: paymentDate,
        description: `${description} [PARTY:${customerName}] [PARTY_TYPE:customer]${vehicleRef ? ` [VEHICLE_REF:${vehicleRef}]` : ''} [VISIT:${visit.id}]`,
        transaction_type: txType,
        source,
        reference_id: visit.id,
        total: amount,
        lines,
      }, {
        params: { workshop_id: activeWorkshopId },
        headers: { 'Idempotency-Key': idemKey },
      });

      const journalEntryId = response?.data?.id || response?.data?.data?.[0]?.id || '';
      if (journalEntryId) {
        createdIds.push(journalEntryId);
      }

      syncedPayments.push({
        ...normalizedRow,
        receiptLabel: description,
        journalEntryId,
      });
    }

    return { syncedPayments, createdIds };
  };

  useEffect(() => {
    let parsedItems = [];
    let parsedPayments = [];
    try {
      if (visit.notes && visit.notes.trim().startsWith('{')) {
        const obj = JSON.parse(visit.notes);
        if (obj.items) parsedItems = obj.items;
        if (obj.payments) {
          parsedPayments = obj.payments.map((p, idx) => ({
            id: p.id || `pay-${idx}-${p.date || Date.now()}`,
            method: p.method || p.paymentMethod || 'cash',
            paymentMethod: p.paymentMethod || p.method || 'cash',
            ...p,
          }));
        }
        if (!obj.text) setNotes('');
        else setNotes(obj.text);
      } else {
        setNotes(visit.notes || '');
        parsedPayments = [];
      }
    } catch (e) {
      setNotes(visit.notes || '');
      parsedPayments = [];
    }

    const normalizedItems = (Array.isArray(parsedItems) ? parsedItems : []).map((item, idx) => {
      const quantity = Number(item?.quantity ?? item?.qty ?? 1) || 1;
      const price = Number(item?.price ?? 0) || 0;
      return {
        id: item?.id || `item-${visit.id}-${idx}`,
        itemType: item?.itemType || 'service',
        name: item?.name ?? '',
        details: item?.details ?? '',
        quantity,
        qty: quantity,
        price,
        discount: Number(item?.discount ?? 0) || 0,
        total: (() => {
          const qty   = Number(item?.quantity ?? item?.qty ?? 1) || 1;
          const price = Number(item?.price || 0);
          const storedTotal = item?.total !== null && item?.total !== undefined ? Number(item.total) : null;
          // استخدم الـ total المخزون دائماً (هو المبلغ الفعلي المتفق عليه)
          // إذا لم يوجد total → احسبه من price × qty
          return storedTotal !== null ? storedTotal : qty * price;
        })(),
        _priceQtyMismatch: (() => {
          // مؤشر للعرض فقط: هل يختلف price × qty عن total؟
          const qty   = Number(item?.quantity ?? item?.qty ?? 1) || 1;
          const price = Number(item?.price || 0);
          const total = item?.total !== null && item?.total !== undefined ? Number(item.total) : null;
          if (total === null || price === 0) return false;
          return Math.abs(total - qty * price) > 0.5;
        })(),
        taxRate: Number(item?.taxRate ?? 0) || 0,
        taxAmount: Number(item?.taxAmount ?? 0) || 0,
        unit: item?.unit ?? '',
        supplierName: item?.supplierName ?? '',
        customerName: item?.customerName ?? '',
        source_testid: item?.source_testid ?? '',
        sku: item?.sku ?? '',
      };
    });

    setItems(normalizedItems);
    setPayments(parsedPayments);
    setOriginalPayments(parsedPayments);
    setStatus(visit.status || 'in_progress');
    setTechId(visit.technicianId || visit.technician_id || '');
    setMileage(visit.mileage || '');
    setIsEditing(archiveMode || (visit.status || '').toLowerCase() === 'in_progress');

    if (whatsappNotificationRef.current) {
      setWhatsappNotification(whatsappNotificationRef.current);
    }
  }, [visit]);

  const persistCatalogEntries = async () => {
    const normalize = (val) => (val || '').trim().toLowerCase();
    const serviceNames = new Set(servicesCatalog.map((s) => normalize(s.name)));
    const partNames = new Set(partsCatalog.map((p) => normalize(p.name)));
    const supplierNames = new Set(suppliersCatalog.map((s) => normalize(s.name)));

    const newServices = items
      .filter((it) => it.itemType === 'service' && normalize(it.name))
      .filter((it) => !serviceNames.has(normalize(it.name)));

    const newParts = items
      .filter((it) => it.itemType === 'part' && normalize(it.name))
      .filter((it) => !partNames.has(normalize(it.name)));

    const uniqueServices = Array.from(
      new Map(newServices.map((it) => [normalize(it.name), it])).values()
    );
    const uniqueParts = Array.from(
      new Map(newParts.map((it) => [normalize(it.name), it])).values()
    );
    const newSuppliers = items
      .filter((it) => it.itemType === 'supplier' && normalize(it.name))
      .filter((it) => !supplierNames.has(normalize(it.name)));
    const uniqueSuppliers = Array.from(
      new Map(newSuppliers.map((it) => [normalize(it.name), it])).values()
    );

    for (const svc of uniqueServices) {
      try {
        const payload = {
          name: svc.name.trim(),
          category: 'خدمة عامة',
          price: Number(svc.price || 0),
          duration: 30,
          laborCost: 0,
          active: true,
        };
        const res = await serviceAPI.create(payload);
        onServiceAdded?.(res.data);
        serviceNames.add(normalize(svc.name));
      } catch (e) {
        console.error('Error creating service:', e);
      }
    }

    for (const part of uniqueParts) {
      try {
        const payload = {
          partNumber: `AUTO-${Date.now()}-${Math.floor(Math.random() * 9000 + 1000)}`,
          name: part.name.trim(),
          category: 'عام',
          purchasePrice: 0,
          sellingPrice: Number(part.price || 0),
          quantity: 0,
          minQuantity: 0,
          supplier: '',
        };
        const res = await partAPI.create(payload);
        onPartAdded?.(res.data);
        partNames.add(normalize(part.name));
      } catch (e) {
        console.error('Error creating part:', e);
      }
    }

    for (const supplier of uniqueSuppliers) {
      try {
        const payload = {
          name: supplier.name.trim(),
          phone: '',
          contactPerson: '',
          email: '',
          address: '',
          city: '',
          category: '',
        };
        const res = await supplierAPI.create(payload);
        onSupplierAdded?.(res.data || payload);
        supplierNames.add(normalize(supplier.name));
      } catch (e) {
        console.error('Error creating supplier:', e);
      }
    }
  };

  const handleSave = async () => {
    if (isSaving) return;
    setIsSaving(true);
    let createdJournalIds = [];
    try {
      await persistCatalogEntries();
      const removedPayments = originalPayments.filter(
        (payment) => payment?.journalEntryId && !payments.some((current) => current.id === payment.id)
      );
      const { syncedPayments, createdIds } = await syncPaymentJournalEntries(payments);
      createdJournalIds = createdIds;
      const itemsForSave = items.map((item) => ({
        ...item,
        billingType:
          item.itemType === 'supplier' || item.itemType === 'part'
            ? 'supplier'
            : 'workshop',
      }));
      const payload = {
        status,
        technicianId: techId || null,
        mileage: Number(mileage),
        notes: JSON.stringify({ text: notes, items: itemsForSave, payments: syncedPayments }),
      };

      await axios.put(`${API_URL}/visits/${visit.id}`, payload);
      await deleteJournalEntries(removedPayments.map((payment) => payment.journalEntryId));

      setPayments(syncedPayments);
      setOriginalPayments(syncedPayments);
      setIsEditing(archiveMode);
      onUpdate?.();

      // 🔄 إشعار باقي الصفحات (Operations / Dashboard / DebtFollowUp) بتحديث البنود
      try {
        window.dispatchEvent(new CustomEvent('finance:updated', {
          detail: {
            source: 'visit_items_save',
            visitId: visit.id,
            vehicleId: visit.vehicleId || visit.vehicle_id,
            itemsCount: items.length,
            totalAmount,
          },
        }));
      } catch (evtErr) { console.warn('finance:updated dispatch failed', evtErr); }

      onAuditEvent?.({
        action: 'visit_save',
        actionLabel: 'حفظ تعديل زيارة',
        visitId: visit.id,
        status,
        itemsCount: items.length,
        totalAmount,
      });
      toast({ title: 'تم الحفظ', description: `تم حفظ ${items.length} بند بنجاح` });
    } catch (e) {
      if (createdJournalIds.length > 0) {
        try {
          await deleteJournalEntries(createdJournalIds);
        } catch (cleanupErr) {
          console.warn('journal_cleanup_failed', cleanupErr);
        }
      }
      console.error('Save visit error:', e);
      const errMsg = e?.response?.data?.detail || e?.message || '';
      toast({ title: 'خطأ في الحفظ', description: errMsg || 'فشل الحفظ. تأكد من الاتصال وحاول مرة أخرى.', variant: 'destructive' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleReopen = async () => {
    try {
      await axios.put(`${API_URL}/visits/${visit.id}`, { status: 'in_progress' });
      setStatus('in_progress');
      setIsEditing(true);
      setIsExpanded(true);
      onUpdate?.();
      onAuditEvent?.({
        action: 'visit_reopen',
        actionLabel: 'إعادة فتح زيارة للتعديل',
        visitId: visit.id,
      });
      toast({ title: 'تم', description: 'تم إعادة فتح الزيارة للتعديل' });
    } catch (e) {
      toast({ title: 'خطأ', description: 'فشل إعادة فتح الزيارة', variant: 'destructive' });
    }
  };

  const latestApproval = approvals?.[0];

  // ─── تأكيد السداد من الزيارة مباشرة ────────────────────────────────────────
  const handleConfirmVisitPayment = async ({ paymentLines, date, archiveVehicle, viaSupplierBalance, supplierId: spId, discount = 0 }) => {
    // حساب الرصيد المتبقي للورشة
    const workshopTotal = items.reduce((sum, it) => {
      if (it.itemType === 'supplier') return sum;
      return sum + Number(it.total ?? (Number(it.quantity || 1) * Number(it.price || 0)));
    }, 0);
    const alreadyPaid = payments.reduce((sum, p) => sum + Number(p.amount || 0), 0);
    const remainingBalance = Math.round((workshopTotal - alreadyPaid) * 100) / 100;

    if (remainingBalance <= 0.01) {
      toast({ title: 'تنبيه', description: 'لا يوجد رصيد متبقٍ للسداد', variant: 'destructive' });
      setConfirmPayOpen(false);
      return;
    }

    // الخصم لا يتجاوز الرصيد المتبقي
    const safeDiscount = Math.max(0, Math.min(Number(discount) || 0, remainingBalance));
    const remainingAfterDiscount = Math.round((remainingBalance - safeDiscount) * 100) / 100;

    // توزيع الرصيد المتبقي بعد الخصم على الوسائل التي بدون مبلغ
    const linesWithNull = (paymentLines || []).filter(l => !l.amount);
    const linesWithAmount = (paymentLines || []).filter(l => l.amount && l.amount > 0);
    const sumWithAmount = linesWithAmount.reduce((s, l) => s + l.amount, 0);
    const leftover = Math.max(0, remainingAfterDiscount - sumWithAmount);

    // توزيع المتبقي على السطور بدون مبلغ بالتساوي
    const share = linesWithNull.length > 0 ? Math.round((leftover / linesWithNull.length) * 100) / 100 : 0;
    const resolvedLines = (paymentLines || []).map(l => ({
      ...l,
      amount: (l.amount && l.amount > 0) ? l.amount : share,
    })).filter(l => l.amount > 0.01);

    if (!resolvedLines.length && safeDiscount <= 0) {
      toast({ title: 'تنبيه', description: 'يرجى إدخال مبلغ أو خصم', variant: 'destructive' });
      return;
    }

    setConfirmPayLoading(true);
    let createdJournalIds = [];
    try {
      const supplierBalanceAmount = resolvedLines
        .filter((line) => line.method === 'supplier_balance')
        .reduce((sum, line) => sum + Number(line.amount || 0), 0);

      if (supplierBalanceAmount > 0) {
        if (!spId) {
          throw new Error('لا يمكن السداد من رصيد المورد بدون تحديد مورد واحد للزيارة.');
        }

        const activeWorkshopId =
          process.env.REACT_APP_WORKSHOP_ID
          || vehicle?.workshopId
          || vehicle?.workshop_id
          || 'finmodule-sync';

        await axios.post(`${API_URL}/smart-accounting/supplier-balance-payment`, {
          supplier_id: spId,
          amount: supplierBalanceAmount,
          workshop_id: activeWorkshopId,
          workshopId: activeWorkshopId,
          operation_id: visit.id,
          notes: `سداد زيارة مركبة ${vehicle?.plateNumber || vehicle?.plate_number || ''}`.trim(),
        });
      }
      const newPaymentEntries = resolvedLines.map(l => ({
        id: `pay-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        kind: 'payment',
        amount: l.amount,
        date: date || new Date().toISOString().split('T')[0],
        method: l.method,
        paymentMethod: l.method,
        label: `تسديد (${paymentMethodLabelMap[l.method] || l.method})`,
      }));

      const { syncedPayments: syncedNewPayments, createdIds } = await syncPaymentJournalEntries(newPaymentEntries);
      createdJournalIds = createdIds;

      const nextPayments = [...payments, ...syncedNewPayments];

      const totalConfirmed = resolvedLines.reduce((s, l) => s + l.amount, 0);

      // حفظ في DB
      const itemsForSave = items.map((item) => ({
        ...item,
        billingType: item.itemType === 'supplier' || item.itemType === 'part' ? 'supplier' : 'workshop',
      }));
      await axios.put(`${API_URL}/visits/${visit.id}`, {
        status,
        technicianId: techId || null,
        mileage: Number(mileage),
        notes: JSON.stringify({ text: notes, items: itemsForSave, payments: nextPayments }),
      });

      setPayments(nextPayments);
      setOriginalPayments(nextPayments);

      setConfirmPayOpen(false);
      const summaryParts = resolvedLines.map(l => `${(paymentMethodLabelMap[l.method] || l.method)}: ${l.amount.toLocaleString('ar-SA')} ر.س`);
      if (safeDiscount > 0) {
        summaryParts.push(`خصم: ${safeDiscount.toLocaleString('ar-SA')} ر.س`);
      }
      toast({
        title: 'تم السداد',
        description: summaryParts.join(' • '),
      });

      // 🔄 إشعار باقي الصفحات (Dashboard / Operations / DebtFollowUp) بالتحديث
      try {
        window.dispatchEvent(new CustomEvent('finance:updated', {
          detail: { source: 'visit_payment', visitId: visit.id, amount: totalConfirmed, discount: safeDiscount }
        }));
      } catch (evtErr) {
        console.warn('finance:updated dispatch failed', evtErr);
      }

      // أرشفة المركبة إذا اختار المستخدم ذلك
      if (archiveVehicle && (visit.vehicleId || visit.vehicle_id)) {
        try {
          await axios.post(`${API_URL}/smart-accounting/vehicle/${visit.vehicleId || visit.vehicle_id}/archive`);
          toast({ title: '📦 تم الأرشفة', description: 'انتقل ملف المركبة للأرشيف' });
        } catch (archiveErr) {
          console.warn('archive_after_payment_failed', archiveErr);
        }
      }

      onUpdate?.();
    } catch (e) {
      if (createdJournalIds.length > 0) {
        try {
          await deleteJournalEntries(createdJournalIds);
        } catch (cleanupErr) {
          console.warn('journal_cleanup_failed', cleanupErr);
        }
      }
      const errMsg = e?.response?.data?.detail || e?.message || '';
      toast({ title: 'خطأ', description: errMsg || 'فشل تسجيل السداد', variant: 'destructive' });
    } finally {
      setConfirmPayLoading(false);
    }
  };

  const handleCloseVisit = async () => {
    if (isSaving) return;

    // حساب رصيد الورشة المتبقي (الموردون مستثنون)
    const workshopTotal = items.reduce((sum, it) => {
      if (it.itemType === 'supplier') return sum;
      return sum + Number(it.total ?? (Number(it.quantity || 1) * Number(it.price || 0)));
    }, 0);
    const totalPaid = payments.reduce((sum, p) => sum + Number(p.amount || 0), 0);
    const remainingBalance = Math.round((workshopTotal - totalPaid) * 100) / 100;

    if (remainingBalance > 0.01) {
      toast({
        title: 'لا يمكن إغلاق الزيارة',
        description: `يجب سداد المتبقي ${remainingBalance.toLocaleString('ar-SA', { minimumFractionDigits: 2 })} ر.س قبل الإغلاق.`,
        variant: 'destructive',
      });
      return;
    }

    if (!window.confirm('هل تريد حفظ جميع البنود وإغلاق الزيارة؟')) return;
    setIsSaving(true);
    try {
      await persistCatalogEntries();
      const itemsForSave = items.map((item) => ({
        ...item,
        billingType:
          item.itemType === 'supplier' || item.itemType === 'part'
            ? 'supplier'
            : 'workshop',
      }));
      const payload = {
        status: 'completed',
        exitDate: new Date().toISOString(),
        technicianId: techId || null,
        mileage: Number(mileage),
        notes: JSON.stringify({ text: notes, items: itemsForSave, payments }),
      };
      const response = await axios.put(`${API_URL}/visits/${visit.id}`, payload);
      const whatsappUrl = response.data?.whatsappNotificationUrl;
      if (whatsappUrl) {
        const customerName = vehicle?.customerName || vehicle?.customer_name || 'العميل';
        let messageText = '';
        try {
          const u = new URL(whatsappUrl);
          messageText = decodeURIComponent(u.searchParams.get('text') || '');
        } catch {
          messageText = '';
        }

        const notification = {
          url: whatsappUrl,
          customerName,
          message: messageText,
        };

        if (onShowWhatsAppPreview) {
          onShowWhatsAppPreview(notification);
        }

        setWhatsappNotification(notification);
        whatsappNotificationRef.current = notification;
        onVisitClosed?.(notification);
      }

      setStatus('completed');
      setIsEditing(false);
      onUpdate?.();
      onAuditEvent?.({
        action: 'visit_close',
        actionLabel: 'حفظ وإغلاق زيارة',
        visitId: visit.id,
        itemsCount: items.length,
        totalAmount,
      });

      toast({ title: 'تم الحفظ والإغلاق', description: 'تم حفظ البنود وإغلاق الزيارة بنجاح' });
    } catch (e) {
      console.error('Close visit error:', e);
      const errMsg = e?.response?.data?.detail || e?.message || '';
      toast({ title: 'خطأ في الإغلاق', description: errMsg || 'فشل إغلاق الزيارة. تأكد من الاتصال وحاول مرة أخرى.', variant: 'destructive' });
    } finally {
      setIsSaving(false);
    }
  };

  const addItem = () => {
    setItems([...items, { itemType: 'service', name: '', quantity: 1, price: 0 }]);
  };

  const updateItem = (index, field, value) => {
    const next = [...items];
    next[index][field] = value;
    // إعادة حساب total تلقائياً عند تغيير price أو quantity
    if (field === 'price' || field === 'quantity' || field === 'qty') {
      const qty   = Number(next[index].quantity || next[index].qty || 1);
      const price = Number(next[index].price || 0);
      next[index].total = qty * price;
      next[index].quantity = qty;
      next[index].qty = qty;
    }
    setItems(next);
  };

  const deleteItem = (index) => {
    setItems(items.filter((_, i) => i !== index));
  };

  const addPayment = () => {
    const amount = Number(paymentDraft.amount);
    if (!Number.isFinite(amount) || amount <= 0) {
      toast({ title: 'تنبيه', description: 'يرجى إدخال مبلغ صحيح', variant: 'destructive' });
      return;
    }
    const entry = {
      id: `pay-${Date.now()}`,
      kind: paymentDraft.kind || 'advance',
      amount,
      date: new Date().toISOString(),
      method: paymentDraft.method || 'cash',
      paymentMethod: paymentDraft.method || 'cash',
    };
    setPayments([...payments, entry]);
    setPaymentDraft({ kind: paymentDraft.kind || 'advance', amount: '', method: paymentDraft.method || 'cash' });
  };

  const removePayment = (paymentId, index) => {
    setPayments(payments.filter((p, i) => (paymentId ? p.id !== paymentId : i !== index)));
  };

  const paymentsTotal = payments.reduce((sum, p) => sum + Number(p.amount || 0), 0);
  const advanceTotal = payments
    .filter((p) => (p.kind || '').toLowerCase() === 'advance')
    .reduce((sum, p) => sum + Number(p.amount || 0), 0);

  const supplierCandidates = useMemo(() => {
    const suppliersByName = new Map(
      (suppliersCatalog || [])
        .filter((row) => row?.id && row?.name)
        .map((row) => [String(row.name).trim().toLowerCase(), row])
    );

    const unique = new Map();
    (items || [])
      .filter((it) => it?.itemType === 'supplier' && String(it?.name || '').trim())
      .forEach((it) => {
        const key = String(it.name).trim().toLowerCase();
        const matched = suppliersByName.get(key);
        if (matched?.id) {
          unique.set(String(matched.id), { id: matched.id, name: matched.name });
        }
      });

    return Array.from(unique.values());
  }, [items, suppliersCatalog]);

  const singleSupplierForBalance = supplierCandidates.length === 1 ? supplierCandidates[0] : null;

  const totalAmount = items.reduce((sum, item) => {
    const qty   = Number(item.quantity || item.qty || 1);
    const price = Number(item.price || 0);
    const total = Number(item.total ?? (qty * price));
    return sum + total;
  }, 0);

  const openLabel = status === 'in_progress' ? 'جارية' : 'مكتملة';
  const statusPill =
    status === 'in_progress'
      ? {
          background: 'rgba(240,249,255,0.8)',
          border: '1px solid rgba(56,189,248,0.22)',
          color: 'rgba(3,105,161,0.95)',
        }
      : {
          background: 'rgba(236,253,245,0.8)',
          border: '1px solid rgba(16,185,129,0.22)',
          color: 'rgba(4,120,87,0.95)',
        };

  const entry = visit.entryDate || visit.entry_date || visit.createdAt || visit.created_at;

  const workshopDue = Number(visit.total_workshop ?? visit.totalWorkshop ?? 0);
  const suppliersDue = Number(visit.total_suppliers ?? visit.totalSuppliers ?? 0);
  const paid = Number(visit.total_paid ?? visit.totalPaid ?? 0);
  const balance = Number(visit.balance ?? 0);

  const statItems = [
    {
      k: 'workshop',
      label: 'ورشة',
      value: workshopDue,
      style: {
        background: 'rgba(250,245,255,0.8)',
        border: '1px solid rgba(168,85,247,0.22)',
        color: 'rgba(107,33,168,0.95)',
      },
    },
    {
      k: 'suppliers',
      label: 'مورد',
      value: suppliersDue,
      style: {
        background: 'rgba(254,242,242,0.8)',
        border: '1px solid rgba(244,63,94,0.22)',
        color: 'rgba(159,18,57,0.95)',
      },
    },
    {
      k: 'paid',
      label: 'مدفوع',
      value: paid,
      style: {
        background: 'rgba(236,253,245,0.8)',
        border: '1px solid rgba(16,185,129,0.22)',
        color: 'rgba(4,120,87,0.95)',
      },
    },
    {
      k: 'balance',
      label: 'متبقي',
      value: balance,
      style: {
        background: balance === 0 ? 'rgba(16,185,129,0.10)' : 'rgba(56,189,248,0.10)',
        border: `1px solid ${balance === 0 ? 'rgba(16,185,129,0.22)' : 'rgba(56,189,248,0.22)'}`,
        color: balance === 0 ? 'rgba(4,120,87,0.95)' : 'rgba(3,105,161,0.95)',
      },
    },
  ];

  return (
    <div
      className="dash-widget-shell"
      data-expanded={isExpanded ? 'true' : 'false'}
      data-testid={`visit-card-${visit.id}`}
      style={{
        cursor: 'default',
        background: 'rgba(255,255,255,0.96)',
        border: `1px solid ${isExpanded ? 'rgba(56,189,248,0.42)' : 'rgba(203,213,225,0.78)'}`,
        boxShadow: isExpanded ? '0 18px 60px rgba(15,23,42,0.1)' : '0 4px 20px rgba(15,23,42,0.05)',
        padding: 0,
      }}
    >
      {/* Header */}
      <button
        type="button"
        className="w-full text-right px-4 py-4 flex items-start justify-between gap-3"
        onClick={() => setIsExpanded((v) => !v)}
        data-testid={`visit-card-toggle-${visit.id}`}
        style={{ background: 'transparent' }}
      >
        <div className="flex items-start gap-3 min-w-0">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
            style={{
              background:
                status === 'in_progress'
                  ? 'rgba(56,189,248,0.10)'
                  : 'rgba(16,185,129,0.10)',
              border:
                status === 'in_progress'
                  ? '1px solid rgba(56,189,248,0.22)'
                  : '1px solid rgba(16,185,129,0.22)',
              color:
                status === 'in_progress'
                  ? 'rgba(3,105,161,0.95)'
                  : 'rgba(4,120,87,0.95)',
            }}
          >
            <Calendar size={18} />
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className="px-2 py-0.5 rounded-full text-[11px] font-bold tabular-nums"
                style={{ background: 'rgba(56,189,248,0.12)', border: '1px solid rgba(56,189,248,0.24)', color: 'rgba(3,105,161,0.95)' }}
                data-testid={`visit-number-${visit.id}`}
              >
                زيارة {visitNumberLabel}
              </span>
              <div
                className="text-sm font-extrabold tabular-nums"
                style={{ color: 'rgba(15,23,42,0.95)' }}
                data-testid={`visit-entry-date-${visit.id}`}
              >
                {entry ? new Date(entry).toLocaleDateString('ar-SA') : '—'}
              </div>
              <span
                className="px-2 py-0.5 rounded-full text-[11px]"
                style={statusPill}
                data-testid={`visit-status-pill-${visit.id}`}
              >
                {openLabel}
              </span>
            </div>

            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]" style={{ color: 'rgba(100,116,139,0.9)' }}>
              <span data-testid={`visit-mileage-${visit.id}`}>
                {mileage ? `${Number(mileage).toLocaleString()} كم` : 'بدون عداد'}
              </span>
              {items.length > 0 && <span data-testid={`visit-items-count-${visit.id}`}>• {items.length} بنود</span>}
              {totalAmount > 0 && (
                <span
                  style={{ color: 'rgba(4,120,87,0.95)' }}
                  className="font-semibold tabular-nums"
                  data-testid={`visit-total-amount-${visit.id}`}
                >
                  • {formatCurrency(totalAmount)}
                </span>
              )}
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              {statItems.map((s) => (
                <span
                  key={s.k}
                  className="px-2 py-1 rounded-full text-[11px] tabular-nums"
                  style={s.style}
                  data-testid={`visit-stat-${visit.id}-${s.k}`}
                >
                  {s.label}: {formatCurrency(s.value)}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="shrink-0 pt-1" style={{ color: 'rgba(100,116,139,0.9)' }}>
          {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-4 pb-4 pt-0" style={{ borderTop: '1px solid rgba(203,213,225,0.8)' }}>
          {/* Controls */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 py-4" onClick={(e) => e.stopPropagation()}>
            <div>
              <label className="block text-[11px] font-medium mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>
                الفني المسؤول
              </label>
              <select
                className="w-full text-sm rounded-lg p-2 disabled:opacity-60"
                style={{
                  background: 'rgba(255,255,255,0.8)',
                  border: '1px solid rgba(203,213,225,0.8)',
                  color: 'rgba(15,23,42,0.92)',
                }}
                value={techId}
                onChange={(e) => setTechId(e.target.value)}
                disabled={!isEditing}
                data-testid={`visit-tech-select-${visit.id}`}
              >
                <option value="">— غير محدد —</option>
                {technicians.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-medium mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>
                قراءة العداد
              </label>
              <input
                type="number"
                className="w-full text-sm rounded-lg p-2 disabled:opacity-60"
                style={{
                  background: 'rgba(255,255,255,0.8)',
                  border: '1px solid rgba(203,213,225,0.8)',
                  color: 'rgba(15,23,42,0.92)',
                }}
                value={mileage}
                onChange={(e) => setMileage(e.target.value)}
                disabled={!isEditing}
                data-testid={`visit-mileage-input-${visit.id}`}
              />
            </div>
          </div>

          {/* Items */}
          <div className="mb-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between gap-2 mb-2">
              <div>
                <div className="text-sm font-bold" style={{ color: 'rgba(15,23,42,0.95)' }}>
                  البنود
                </div>
                <div className="text-[11px]" style={{ color: 'rgba(100,116,139,0.9)' }}>
                  خدمات / قطع — إضافة وتعديل بسهولة
                </div>
              </div>
              <div className="text-sm font-extrabold tabular-nums" style={{ color: 'rgba(3,105,161,0.95)' }}>
                {formatCurrency(totalAmount)}
              </div>
            </div>

            {/* Mobile: cards */}
            <div className="space-y-2 sm:hidden">
              {items.length === 0 ? (
                <div
                  className="liquid-surface"
                  style={{
                    borderRadius: 18,
                    padding: 14,
                    textAlign: 'center',
                    color: 'rgba(100,116,139,0.9)',
                    background: 'rgba(241,245,249,0.8)',
                  }}
                >
                  لا توجد بنود مسجلة لهذه الزيارة
                </div>
              ) : (
                items.map((item, idx) => (
                  <VisitItemCard
                    key={item?.id ?? item?.uid ?? `item-${idx}`}
                    item={item}
                    isEditing={isEditing}
                    onChange={(f, v) => updateItem(idx, f, v)}
                    onDelete={() => deleteItem(idx)}
                    servicesCatalog={servicesCatalog}
                    partsCatalog={partsCatalog}
                    suppliersCatalog={suppliersCatalog}
                    customersCatalog={customersCatalog}
                    rowId={idx}
                    visitId={visit.id}
                  />
                ))
              )}

              {isEditing && (
                <button
                  type="button"
                  onClick={addItem}
                  className="w-full rounded-2xl px-4 py-3 text-sm font-bold flex items-center justify-center gap-2"
                  style={{
                    background: 'rgba(240,249,255,0.8)',
                    border: '1px solid rgba(56,189,248,0.22)',
                    color: 'rgba(3,105,161,0.95)',
                  }}
                  data-testid={`visit-add-item-button-mobile-${visit.id}`}
                >
                  <Plus size={16} /> إضافة بند
                </button>
              )}
            </div>

            {/* Desktop: table */}
            <div className="hidden sm:block liquid-surface" style={{ borderRadius: 20, overflow: 'hidden' }}>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[620px]">
                  <thead style={{ background: 'rgba(241,245,249,0.8)', borderBottom: '1px solid rgba(203,213,225,0.8)' }}>
                    <tr>
                      <th className="py-2 px-3 text-right text-xs font-medium" style={{ color: 'rgba(100,116,139,0.9)' }}>النوع</th>
                      <th className="py-2 px-3 text-right text-xs font-medium" style={{ color: 'rgba(100,116,139,0.9)' }}>البند</th>
                      <th className="py-2 px-3 text-center text-xs font-medium" style={{ color: 'rgba(100,116,139,0.9)' }}>الكمية</th>
                      <th className="py-2 px-3 text-center text-xs font-medium" style={{ color: 'rgba(100,116,139,0.9)' }}>السعر</th>
                      <th className="py-2 px-3 text-right text-xs font-medium" style={{ color: 'rgba(100,116,139,0.9)' }}>الإجمالي</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.length === 0 ? (
                      <tr>
                        <td colSpan="5" className="py-8 text-center text-xs" style={{ color: 'rgba(100,116,139,0.9)' }}>
                          لا توجد بنود مسجلة لهذه الزيارة
                        </td>
                      </tr>
                    ) : (
                      items.map((item, idx) => (
                        <VisitItemRow
                          key={item?.id ?? item?.uid ?? `row-${idx}`}
                          item={item}
                          isEditing={isEditing}
                          onChange={(f, v) => updateItem(idx, f, v)}
                          onDelete={() => deleteItem(idx)}
                          servicesCatalog={servicesCatalog}
                          partsCatalog={partsCatalog}
                          suppliersCatalog={suppliersCatalog}
                          customersCatalog={customersCatalog}
                          rowId={idx}
                          visitId={visit.id}
                        />
                      ))
                    )}
                  </tbody>
                  <tfoot style={{ background: 'rgba(241,245,249,0.8)', borderTop: '1px solid rgba(203,213,225,0.8)' }}>
                    <tr>
                      <td colSpan="4" className="py-2 px-3 text-left text-xs font-bold" style={{ color: 'rgba(100,116,139,0.9)' }}>
                        المجموع
                      </td>
                      <td className="py-2 px-3 text-right text-xs font-extrabold tabular-nums" style={{ color: 'rgba(3,105,161,0.95)' }}>
                        {formatCurrency(totalAmount)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              {isEditing && (
                <button
                  type="button"
                  onClick={addItem}
                  className="w-full py-2 text-xs font-bold flex items-center justify-center gap-2"
                  style={{
                    background: 'rgba(240,249,255,0.8)',
                    borderTop: '1px solid rgba(56,189,248,0.18)',
                    color: 'rgba(3,105,161,0.95)',
                  }}
                  data-testid={`visit-add-item-button-${visit.id}`}
                >
                  <Plus size={14} /> إضافة بند جديد
                </button>
              )}
            </div>
          </div>

          {/* Payments */}
          <div
            className="mb-4 liquid-surface"
            style={{
              borderRadius: 20,
              padding: 12,
              background: 'rgba(248,250,252,0.96)',
              border: '1px solid rgba(203,213,225,0.8)',
            }}
            onClick={(e) => e.stopPropagation()}
            data-testid={`visit-payments-${visit.id}`}
          >
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <div>
                <div className="text-sm font-bold" style={{ color: 'rgba(15,23,42,0.95)' }}>
                  المدفوعات
                </div>
                <div className="text-[11px]" style={{ color: 'rgba(100,116,139,0.9)' }}>
                  تحت الحساب / دفعة مقدمة
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="text-[11px] font-semibold" style={{ color: 'rgba(3,105,161,0.95)' }} data-testid={`visit-payments-summary-${visit.id}`}>
                  إجمالي الدفعات: {formatCurrency(paymentsTotal)} • المقدّم: {formatCurrency(advanceTotal)}
                </div>
                {/* زر تأكيد السداد */}
                <button
                  type="button"
                  onClick={() => setConfirmPayOpen(true)}
                  className="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-bold transition-all hover:opacity-90 active:scale-95"
                  style={{
                    background: 'rgba(34,197,94,0.18)',
                    border: '1px solid rgba(34,197,94,0.40)',
                    color: 'rgba(4,120,87,0.95)',
                  }}
                  data-testid={`visit-confirm-payment-btn-${visit.id}`}
                >
                  <span>✓</span>
                  <span>تأكيد السداد</span>
                </button>
              </div>
            </div>

            {supplierCandidates.length > 1 && (
              <div
                className="mb-3 rounded-lg border border-amber-500/35 bg-amber-100 px-3 py-2 text-[11px] text-amber-900"
                data-testid={`visit-supplier-balance-multi-suppliers-note-${visit.id}`}
              >
                يوجد أكثر من مورد في هذه الزيارة. عند اختيار «السداد من رصيد المورد» سيتم طلب تحديد المورد داخل نافذة السداد.
              </div>
            )}

            {payments.length === 0 ? (
              <div className="text-xs" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid={`visit-payments-empty-${visit.id}`}>
                لا توجد دفعات مسجلة لهذه الزيارة
              </div>
            ) : (
              <div className="space-y-2">
                {payments.map((payment, idx) => {
                  const kindLabel = (payment.kind || '').toLowerCase() === 'advance' ? 'دفعة مقدمة' : 'تحت الحساب';
                  const methodLabel = paymentMethodLabelMap[payment.paymentMethod || payment.method || 'cash'] || (payment.paymentMethod || payment.method || 'cash');
                  return (
                    <div
                      key={payment.id || idx}
                      className="flex items-center justify-between gap-2 rounded-xl px-3 py-2"
                      style={{
                        background: 'rgba(255,255,255,0.8)',
                        border: '1px solid rgba(203,213,225,0.8)',
                      }}
                      data-testid={`visit-payment-row-${visit.id}-${idx}`}
                    >
                      <div className="text-xs font-semibold" style={{ color: 'rgba(71,85,105,0.9)' }} data-testid={`visit-payment-kind-${visit.id}-${idx}`}>
                        {kindLabel}
                        <div className="text-[10px] mt-1" style={{ color: 'rgba(71,85,105,0.95)' }} data-testid={`visit-payment-method-${visit.id}-${idx}`}>
                          {methodLabel}
                        </div>
                      </div>
                      <div className="text-xs font-extrabold tabular-nums" style={{ color: 'rgba(4,120,87,0.95)' }} data-testid={`visit-payment-amount-${visit.id}-${idx}`}>
                        {formatCurrency(payment.amount || 0)}
                      </div>
                      {isEditing && (
                        <button
                          type="button"
                          onClick={() => removePayment(payment.id, idx)}
                          className="p-2 rounded-lg"
                          style={{
                            background: 'rgba(244,63,94,0.14)',
                            border: '1px solid rgba(244,63,94,0.28)',
                            color: 'rgba(159,18,57,0.95)',
                          }}
                          data-testid={`visit-payment-remove-${visit.id}-${idx}`}
                        >
                          <Trash2 size={12} />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {isEditing && (
              <div className="mt-3 grid grid-cols-1 sm:grid-cols-[1fr_1fr_1fr_auto] gap-2">
                <select
                  value={paymentDraft.kind}
                  onChange={(e) => setPaymentDraft({ ...paymentDraft, kind: e.target.value })}
                  className="w-full text-xs rounded-lg p-2"
                  style={{
                    background: 'rgba(255,255,255,0.8)',
                    border: '1px solid rgba(203,213,225,0.8)',
                    color: 'rgba(15,23,42,0.92)',
                  }}
                  data-testid={`visit-payment-kind-select-${visit.id}`}
                >
                  <option value="advance">دفعة مقدمة</option>
                  <option value="payment">تحت الحساب</option>
                </select>
                <select
                  value={paymentDraft.method || 'cash'}
                  onChange={(e) => setPaymentDraft({ ...paymentDraft, method: e.target.value })}
                  className="w-full text-xs rounded-lg p-2"
                  style={{
                    background: 'rgba(255,255,255,0.8)',
                    border: '1px solid rgba(203,213,225,0.8)',
                    color: 'rgba(15,23,42,0.92)',
                  }}
                  data-testid={`visit-payment-method-select-${visit.id}`}
                >
                  <option value="cash">نقد</option>
                  <option value="bank">بنك/تحويل</option>
                  <option value="pos">نقاط بيع</option>
                </select>
                <input
                  type="number"
                  value={paymentDraft.amount}
                  onChange={(e) => setPaymentDraft({ ...paymentDraft, amount: e.target.value })}
                  className="w-full text-xs rounded-lg p-2"
                  style={{
                    background: 'rgba(255,255,255,0.8)',
                    border: '1px solid rgba(203,213,225,0.8)',
                    color: 'rgba(15,23,42,0.92)',
                  }}
                  placeholder="المبلغ"
                  data-testid={`visit-payment-amount-input-${visit.id}`}
                />
                <button
                  type="button"
                  onClick={addPayment}
                  className="w-full sm:w-auto px-3 py-2 rounded-xl text-xs font-bold"
                  style={{
                    background: 'rgba(56,189,248,0.14)',
                    border: '1px solid rgba(56,189,248,0.28)',
                    color: 'rgba(3,105,161,0.95)',
                  }}
                  data-testid={`visit-payment-add-${visit.id}`}
                >
                  إضافة دفعة
                </button>
              </div>
            )}
          </div>

          {/* Notes */}
          <div className="mb-4" onClick={(e) => e.stopPropagation()}>
            <label className="block text-[11px] font-medium mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>
              ملاحظات الزيارة
            </label>
            <textarea
              className="w-full text-sm rounded-2xl p-3 min-h-[90px] resize-none disabled:opacity-60"
              style={{
                background: 'rgba(255,255,255,0.8)',
                border: '1px solid rgba(203,213,225,0.8)',
                color: 'rgba(15,23,42,0.92)',
              }}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={!isEditing}
              placeholder="أي ملاحظات إضافية..."
              data-testid={`visit-notes-textarea-${visit.id}`}
            />
          </div>

          {latestApproval && (
            <div
              className="liquid-surface"
              style={{
                borderRadius: 20,
                padding: 12,
                background:
                  'radial-gradient(circle at 12% 18%, rgba(248,250,252,0.98), rgba(241,245,249,0.96))',
                border: '1px solid rgba(245,158,11,0.22)',
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="text-sm font-bold" style={{ color: 'rgba(180,83,9,0.95)' }}>
                اعتماد واتساب
              </div>
              <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs" style={{ color: 'rgba(120,53,15,0.95)' }}>
                <div>
                  الحالة: <span className="font-semibold">{latestApproval.status}</span>
                </div>
                <div>
                  الرمز: <span className="font-mono">{latestApproval.token}</span>
                </div>
                {latestApproval.respondedAt && (
                  <div>
                    وقت الرد:{' '}
                    <span className="font-semibold">
                      {String(latestApproval.respondedAt).slice(0, 19).replace('T', ' ')}
                    </span>
                  </div>
                )}
                {latestApproval.responderName && (
                  <div>
                    المعتمد: <span className="font-semibold">{latestApproval.responderName}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* WhatsApp Auto-Notification */}
          {whatsappNotification && (
            <div
              className="liquid-surface mb-3"
              style={{
                borderRadius: 20,
                padding: 12,
                border: '1px solid rgba(16,185,129,0.22)',
                background:
                  'radial-gradient(circle at 12% 18%, rgba(248,250,252,0.98), rgba(241,245,249,0.96))',
              }}
              data-testid={`visit-whatsapp-notification-${visit.id}`}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-sm flex items-center gap-2" style={{ color: 'rgba(4,120,87,0.95)' }}>
                    <MessageCircle size={16} />
                    إبلاغ العميل بجاهزية المركبة
                  </div>
                  <p className="mt-1 text-xs truncate" style={{ color: 'rgba(6,95,70,0.95)' }}>
                    {whatsappNotification.customerName} - اضغط لإرسال الإشعار عبر واتساب
                  </p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <a
                    href={whatsappNotification.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-2 rounded-xl text-xs font-bold flex items-center gap-2"
                    style={{
                      background: 'rgba(16,185,129,0.16)',
                      border: '1px solid rgba(16,185,129,0.28)',
                      color: 'rgba(4,120,87,0.95)',
                    }}
                    data-testid={`visit-whatsapp-send-${visit.id}`}
                  >
                    <MessageCircle size={14} /> إرسال
                  </a>
                  <button
                    type="button"
                    onClick={() => {
                      setWhatsappNotification(null);
                      whatsappNotificationRef.current = null;
                    }}
                    className="p-2 rounded-xl"
                    style={{
                      background: 'rgba(255,255,255,0.8)',
                      border: '1px solid rgba(203,213,225,0.8)',
                      color: 'rgba(100,116,139,0.9)',
                    }}
                    title="إغلاق"
                    data-testid={`visit-whatsapp-dismiss-${visit.id}`}
                  >
                    <X size={14} />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Print */}
          <div className="flex justify-end gap-2 pb-3" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              onClick={() => {
                const vId = visit.id;
                const st = (visit.status || '').toLowerCase();
                const type = st === 'quotation' ? 'quote' : st === 'diagnosis' ? 'diagnosis' : 'invoice';
                onOpenQuickPrintDialog?.({ type, visitId: vId });
              }}
              className="w-full sm:w-auto px-3 py-2 rounded-xl text-xs font-bold flex items-center justify-center gap-2"
              style={{
                background: 'rgba(255,255,255,0.8)',
                border: '1px solid rgba(203,213,225,0.8)',
                color: 'rgba(15,23,42,0.92)',
              }}
              title="طباعة هذه الزيارة"
              data-testid={`visit-print-button-${visit.id}`}
            >
              <Printer size={14} /> طباعة الزيارة
            </button>
          </div>

          {/* Actions */}
          <div
            className="flex flex-col sm:flex-row sm:flex-wrap justify-end gap-2 pt-3"
            style={{ borderTop: '1px solid rgba(203,213,225,0.8)' }}
            onClick={(e) => e.stopPropagation()}
          >
            {isEditing ? (
              <>
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="w-full sm:w-auto px-4 py-2 rounded-xl text-xs font-bold"
                  style={{
                    background: 'rgba(255,255,255,0.8)',
                    border: '1px solid rgba(203,213,225,0.8)',
                    color: 'rgba(71,85,105,0.95)',
                  }}
                  data-testid={`visit-cancel-edit-${visit.id}`}
                  disabled={isSaving}
                >
                  إلغاء
                </button>

                <button
                  type="button"
                  onClick={handleSave}
                  disabled={isSaving}
                  className="w-full sm:w-auto px-4 py-2 rounded-xl text-xs font-bold flex items-center justify-center gap-2 disabled:opacity-50"
                  style={{
                    background: 'rgba(56,189,248,0.14)',
                    border: '1px solid rgba(56,189,248,0.28)',
                    color: 'rgba(3,105,161,0.95)',
                  }}
                  data-testid={`visit-save-button-${visit.id}`}
                >
                  <Save size={14} /> {isSaving ? 'جاري الحفظ...' : 'حفظ'}
                </button>

                <button
                  type="button"
                  onClick={handleCloseVisit}
                  disabled={isSaving}
                  className="w-full sm:w-auto px-4 py-2 rounded-xl text-xs font-bold flex items-center justify-center gap-2 disabled:opacity-50"
                  style={{
                    background: 'rgba(16,185,129,0.14)',
                    border: '1px solid rgba(16,185,129,0.28)',
                    color: 'rgba(4,120,87,0.95)',
                  }}
                  data-testid={`visit-close-button-${visit.id}`}
                >
                  <CheckCircle size={14} /> {isSaving ? 'جاري الإغلاق...' : 'حفظ وإغلاق'}
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={handleReopen}
                className="w-full sm:w-auto px-4 py-2 rounded-xl text-xs font-bold flex items-center justify-center gap-2"
                style={{
                  background: 'rgba(245,158,11,0.14)',
                  border: '1px solid rgba(245,158,11,0.28)',
                  color: 'rgba(180,83,9,0.95)',
                }}
                data-testid={`visit-reopen-button-${visit.id}`}
              >
                <Edit2 size={14} /> {archiveMode ? 'إعادة فتح تلقائي للتعديل' : 'إعادة فتح للتعديل'}
              </button>
            )}

            {canDelete && (
              <button
                type="button"
                onClick={() => onDelete?.(visit.id)}
                className="w-full sm:w-auto px-4 py-2 rounded-xl text-xs font-bold flex items-center justify-center gap-2"
                style={{
                  background: 'rgba(244,63,94,0.12)',
                  border: '1px solid rgba(244,63,94,0.28)',
                  color: 'rgba(159,18,57,0.95)',
                }}
                data-testid={`visit-delete-button-${visit.id}`}
              >
                <Trash2 size={14} /> حذف الزيارة
              </button>
            )}
          </div>
        </div>
      )}

      {/* ─── نافذة تأكيد السداد للزيارة ─── */}
      <ConfirmPaymentDialog
        open={confirmPayOpen}
        onOpenChange={setConfirmPayOpen}
        onConfirm={handleConfirmVisitPayment}
        loading={confirmPayLoading}
        supplierId={singleSupplierForBalance?.id || null}
        allowSupplierBalance={true}
        vehicleId={visit.vehicleId || visit.vehicle_id}
        showArchiveOption={true}
        remainingBalance={Math.max(0, Math.round((
          items.filter(it => it.itemType !== 'supplier').reduce((s, it) => s + Number(it.total ?? (Number(it.quantity||1) * Number(it.price||0))), 0)
          - paymentsTotal
        ) * 100) / 100)}
      />
    </div>
  );
};

// --- Main Page Component ---

const VehicleDetails = () => {
  const { t, i18n } = useTranslation();
  const isRTL = i18n.language === 'ar';
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();

  const isArchiveSource = useMemo(() => {
    const params = new URLSearchParams(location.search || '');
    return params.get('source') === 'archive' || params.get('editMode') === 'full';
  }, [location.search]);

  const DEFAULT_BLOCKS = useMemo(
    () => [
      'vehicle_info',
      'visits',
      'financial_summary',
      'guidance',
      'status_actions',
    ],
    []
  );

  const [layoutBlocks, setLayoutBlocks] = useState(DEFAULT_BLOCKS);
  const [layoutLoaded, setLayoutLoaded] = useState(false);

  const session = useMemo(() => {
    try {
      const raw = localStorage.getItem('session');
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }, []);
  const guidanceEnabled = session?.guidanceEnabled !== false;
  const userId = session?.id || session?.name || 'default';

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 2 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 60, tolerance: 3 } })
  );

  const [vehicle, setVehicle] = useState(null);
  const [approvals, setApprovals] = useState([]);
  const [showFiles, setShowFiles] = useState(false);
  const [showApprovals, setShowApprovals] = useState(false);
  const [technicians, setTechnicians] = useState([]);
  const [printDialogOpen, setPrintDialogOpen] = useState(false);
  const [printDialogConfig, setPrintDialogConfig] = useState(null);

  const extractVisitItems = (visit) => {
    if (!visit) return [];
    if (Array.isArray(visit.items) && visit.items.length) return visit.items;
    if (typeof visit.notes === 'string' && visit.notes.trim().startsWith('{')) {
      try {
        const parsed = JSON.parse(visit.notes);
        return parsed?.items || [];
      } catch (e) {
        return [];
      }
    }
    return [];
  };

  const buildVisitPayload = (docType, visit) => {
    const labelMap = {
      invoice: 'فاتورة',
      diagnosis: 'تقرير تشخيص',
      quote: 'عرض سعر',
      receipt: 'سند قبض',
    };
    const visitItems = extractVisitItems(visit);
    const items = visitItems.map((item) => {
      const quantity = Number(item?.quantity || item?.qty || 1);
      const price = Number(item?.price || item?.unitPrice || 0);
      const itemName = item?.name || item?.description || 'عنصر';
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
        phone: vehicle?.customerPhone || vehicle?.ownerPhone || '',
      },
      vehicle: {
        plate: vehicle?.plateNumber || vehicle?.plate || '',
        model: vehicle?.vehicleModel || vehicle?.model || '',
        brand: vehicle?.vehicleBrand || vehicle?.brand || '',
      },
      notes: visit?.notes || '',
      date: visit?.created_at || visit?.createdAt || '',
      settings: {
        document_number: visit?.invoiceNumber || visit?.id || '',
        document_title: labelMap[docType] || 'مستند',
      },
    };
  };

  const openQuickPrintDialog = ({ type, visitId }) => {
    const labelMap = {
      invoice: 'فاتورة',
      diagnosis: 'تشخيص',
      quote: 'عرض سعر',
      receipt: 'سند قبض',
    };
    const visit = visitId ? visits.find((v) => v.id === visitId) : visits[0];
    setPrintDialogConfig({
      title: labelMap[type] || 'طباعة مستند',
      phone: vehicle?.customerPhone || vehicle?.ownerPhone || '',
      payloadBuilder: () => buildVisitPayload(type, visit),
    });
    setPrintDialogOpen(true);
  };

  useEffect(() => {
    let mounted = true;

    const loadLayout = async () => {
      try {
        const res = await userLayoutsAPI.getVehicleDetailsLayout(userId);
        const blocks = res?.data?.blocks || [];
        const normalized = Array.isArray(blocks) ? blocks.filter(Boolean) : [];

        if (!mounted) return;

        // Merge with defaults to handle new blocks added later
        const merged = [
          ...normalized.filter((b) => DEFAULT_BLOCKS.includes(b)),
          ...DEFAULT_BLOCKS.filter((b) => !normalized.includes(b)),
        ];

        setLayoutBlocks(merged.length ? merged : DEFAULT_BLOCKS);
      } catch (e) {
        setLayoutBlocks(DEFAULT_BLOCKS);
      } finally {
        if (mounted) setLayoutLoaded(true);
      }
    };

    loadLayout();

    return () => {
      mounted = false;
    };
  }, [userId, DEFAULT_BLOCKS]);

  const handleLayoutDragEnd = async (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    setLayoutBlocks((items) => {
      const oldIndex = items.indexOf(active.id);
      const newIndex = items.indexOf(over.id);
      const next = arrayMove(items, oldIndex, newIndex);

      // Auto-save (fire & forget)
      userLayoutsAPI.saveVehicleDetailsLayout(userId, next).catch(() => {});
      return next;
    });
  };

  const [visits, setVisits] = useState([]);
  const [servicesCatalog, setServicesCatalog] = useState([]);
  const [partsCatalog, setPartsCatalog] = useState([]);
  const [suppliersCatalog, setSuppliersCatalog] = useState([]);
  const [customersCatalog, setCustomersCatalog] = useState([]);
  const [visitFilter, setVisitFilter] = useState('all');
  const [createVisitConfirmAt, setCreateVisitConfirmAt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState(0);
  
  // Page-level WhatsApp notification (persists across filter changes)
  const [pageWhatsappNotification, setPageWhatsappNotification] = useState(null);
  
  // Status & Notes (Vehicle Level)
  const [status, setStatus] = useState('diagnosis');
  const [notes, setNotes] = useState('');
  const [assignedTech, setAssignedTech] = useState('');
  
  // Edit Vehicle & Customer State
  const [isEditingVehicle, setIsEditingVehicle] = useState(false);
  const [isEditingCustomer, setIsEditingCustomer] = useState(false);
  const [isVehicleInfoCollapsed, setIsVehicleInfoCollapsed] = useState(true);
  const [isCustomerInfoCollapsed, setIsCustomerInfoCollapsed] = useState(true);
  const [vehicleForm, setVehicleForm] = useState({});
  const [customerForm, setCustomerForm] = useState({});
  
  const [scannerOpen, setScannerOpen] = useState(false);
  const [previewImage, setPreviewImage] = useState(null);
  const [vehicleFiles, setVehicleFiles] = useState([]);
  const [fileType, setFileType] = useState('photo');
  const [capturedImage, setCapturedImage] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmTarget, setConfirmTarget] = useState(null);

  const [deleteVisitOpen, setDeleteVisitOpen] = useState(false);
  const [deleteVisitTarget, setDeleteVisitTarget] = useState(null);
  const [deleteVisitLoading, setDeleteVisitLoading] = useState(false);

  const [waPreviewOpen, setWaPreviewOpen] = useState(false);
  const [waPreview, setWaPreview] = useState(null);

  const [financeSummary, setFinanceSummary] = useState(null);
  const [linkedJournalEntries, setLinkedJournalEntries] = useState([]);
  const [vehicleLinkSummary, setVehicleLinkSummary] = useState({ total: 0, ok: 0, warnings: 0, duplicates: 0 });
  const [vehicleLinkIssues, setVehicleLinkIssues] = useState([]);
  const integrityLabelMap = {
    missing_journal_entry: 'لا يوجد قيد يومية مرتبط',
    vehicle_not_found: 'المركبة غير موجودة',
    visit_not_found: 'الزيارة غير موجودة',
    visit_vehicle_mismatch: 'الزيارة لا تطابق المركبة',
    vehicle_scope_without_vehicle: 'عملية مركبة بدون مركبة مرتبطة',
    potential_duplicate: 'تكرار محتمل',
  };
  const [financialSourceOpen, setFinancialSourceOpen] = useState(false);
  const [financialSourceTitle, setFinancialSourceTitle] = useState('');
  const [financialSourceRows, setFinancialSourceRows] = useState([]);
  const workshopId = process.env.REACT_APP_WORKSHOP_ID;

  useEffect(() => {
    if (!isArchiveSource) return;
    setIsEditingVehicle(true);
    setIsEditingCustomer(true);
    setIsVehicleInfoCollapsed(false);
    setIsCustomerInfoCollapsed(false);
    setVisitFilter('all');
  }, [isArchiveSource]);

  
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  const API_URL = (
    process.env.NODE_ENV === 'production'
      ? '/api'
      : `${resolveBackendBase()}/api`.replace('//api', '/api')
  );

  // session/userId now initialized at top of component for layout saving

  const appendService = useCallback((service) => {
    if (!service) return;

    setServicesCatalog((prev) => {
      const exists = prev.some((s) => s.id === service.id || (s.name || '').trim() === (service.name || '').trim());
      return exists ? prev : [...prev, service];
    });
  }, []);

  const appendPart = useCallback((part) => {
    if (!part) return;
    setPartsCatalog((prev) => {
      const exists = prev.some((p) => p.id === part.id || (p.name || '').trim() === (part.name || '').trim());
      return exists ? prev : [...prev, part];
    });
  }, []);

  const appendSupplier = useCallback((supplier) => {
    if (!supplier) return;
    const normalizedSupplier = normalizePartyCatalog([supplier], 'supplier')[0];
    if (!normalizedSupplier) return;
    setSuppliersCatalog((prev) => {
      const exists = prev.some(
        (s) =>
          s.id === normalizedSupplier.id ||
          (s.name || '').trim().toLowerCase() === (normalizedSupplier.name || '').trim().toLowerCase()
      );
      return exists ? prev : [...prev, normalizedSupplier];
    });
  }, []);

  const activeVisit = useMemo(
    () => visits.find((v) => (v.status || '').toLowerCase() === 'in_progress'),
    [visits]
  );

  const guidanceSteps = useMemo(() => {
    const vehicleReady = Boolean(
      vehicle && (vehicle.customerName || vehicle.customerId) && vehicle.plateNumber
    );
    const hasItems = visits.some((visit) => (visit.items || []).length > 0);
    const statusUpdated = !activeVisit;

    return [
      {
        id: 'vehicle',
        title: 'بيانات العميل والمركبة',
        hint: 'تأكد من الاسم والجوال ولوحة المركبة لتجنب الأخطاء الإملائية.',
        done: vehicleReady,
      },
      {
        id: 'items',
        title: 'تسجيل البنود',
        hint: 'أضف الخدمات أو القطع وتحقق من الأسعار قبل الحفظ.',
        done: hasItems,
      },
      {
        id: 'status',
        title: 'تحديث حالة الزيارة',
        hint: 'غيّر الحالة عند الانتهاء لإغلاق الزيارة وعدم نسيانها.',
        done: statusUpdated,
      },
    ];
  }, [vehicle, visits, activeVisit]);

  const canDeleteVisit = ['manager', 'admin'].includes(session?.role);

  const filteredVisits = useMemo(() => {
    const sorted = [...visits].sort((a, b) => {
      const da = new Date(a.entryDate || a.entry_date || a.createdAt || a.created_at || 0).getTime();
      const db = new Date(b.entryDate || b.entry_date || b.createdAt || b.created_at || 0).getTime();
      return db - da;
    });

    if (visitFilter === 'open') {
      return sorted.filter((v) => (v.status || '').toLowerCase() !== 'completed');
    }
    if (visitFilter === 'closed') {
      return sorted.filter((v) => (v.status || '').toLowerCase() === 'completed');
    }
    return sorted;
  }, [visits, visitFilter]);

  // Handler for when a visit is closed - shows WhatsApp notification at page level
  const handleVisitClosed = useCallback((notification) => {
    if (notification) {
      setPageWhatsappNotification(notification);
      // Switch filter to 'all' so user can see the closed visit
      setVisitFilter('all');
    }
    fetchDataLight(); // Refresh visits without full loading
  }, []);

  const normalizeListPayload = useCallback((response, preferredKeys = []) => {
    const payload = response?.data;
    if (Array.isArray(payload)) return payload;
    if (payload && typeof payload === 'object') {
      for (const key of preferredKeys) {
        if (Array.isArray(payload?.[key])) return payload[key];
      }
      if (Array.isArray(payload?.data)) return payload.data;
      if (Array.isArray(payload?.items)) return payload.items;
      if (Array.isArray(payload?.results)) return payload.results;
    }
    return [];
  }, []);

  // Lightweight fetch that doesn't show loading spinner
  const fetchDataLight = useCallback(async () => {
    try {
      const visitsRes = await axios.get(`${API_URL}/vehicles/${id}/visits`).catch(() => ({ data: [] }));
      setVisits(normalizeListPayload(visitsRes, ['visits']));
    } catch (e) {
      console.error('fetchDataLight error:', e);
    }
  }, [id, API_URL, normalizeListPayload]);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setLoadingProgress(10);

      const vehiclePromise = vehicleAPI.getById(id).then((r) => {
        setLoadingProgress(40);
        return r;
      });
      const techPromise = technicianAPI.getAll().then((r) => {
        setLoadingProgress(65);
        return r;
      });
      const visitsPromise = axios
        .get(`${API_URL}/vehicles/${id}/visits`)
        .catch(() => ({ data: [] }))
        .then((r) => {
          setLoadingProgress(80);
          return r;
        });

      // Load vehicle + technicians + visits first (core UI)
      const [vehicleRes, techniciansRes, visitsRes] = await Promise.all([
        vehiclePromise,
        techPromise,
        visitsPromise,
      ]);
      
      setVehicle(vehicleRes.data);
      setStatus(vehicleRes.data.status || 'diagnosis');
      setNotes(vehicleRes.data.notes || '');
      setAssignedTech(vehicleRes.data.technicianId || '');
      
      setVehicleForm({
        plateNumber: vehicleRes.data.plateNumber,
        brand: vehicleRes.data.brand,
        model: vehicleRes.data.model,
        vin: vehicleRes.data.vin,
        color: vehicleRes.data.color,
        fileNumber: vehicleRes.data.fileNumber || ''
      });
      setCustomerForm({
        name: vehicleRes.data.customerName,
        phone: vehicleRes.data.customerPhone,
        email: vehicleRes.data.customerEmail,
        fileNumber: vehicleRes.data.customerFileNumber || ''
      });
      
      setTechnicians(normalizeListPayload(techniciansRes, ['technicians']));
      setVisits(normalizeListPayload(visitsRes, ['visits']));
      

      // Vehicle financial summary (async, non-blocking)
      vehicleFinanceAPI
        .summary(id)
        .then((r) => setFinanceSummary(r.data))
        .catch(() => setFinanceSummary(null));

      // Show loading state as false for core UI
      setLoadingProgress(85);
      setLoading(false);
      
      // Load files and approvals in background
      const filesPromise = fetch(`${API_URL}/vehicles/${id}/files`)
        .then((r) => r.json())
        .catch(() => ({ files: [] }))
        .then((r) => {
          setLoadingProgress(92);
          return r;
        });

      const approvalsPromise = axios
        .get(`${API_URL}/approvals?vehicle_id=${id}`)
        .catch(() => ({ data: [] }))
        .then((r) => {
          setLoadingProgress(98);
          return r;
        });

      const servicesPromise = serviceAPI.getAll().catch(() => ({ data: [] }));
      const partsPromise = partAPI.getAll().catch(() => ({ data: [] }));
      const suppliersPromise = supplierAPI
        .getAll(workshopId ? { workshop_id: workshopId } : {})
        .catch(() => ({ data: [] }));
      const customersPromise = customerAPI.getAll().catch(() => ({ data: [] }));
      const journalEntriesPromise = financeAPI
        .getJournalEntries({ workshop_id: workshopId || process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync', limit: 300 })
        .catch(() => ({ data: { data: [] } }));
      const operationsPromise = axios
        .get(`${API_URL}/operations`, { params: { vehicle_id: id, limit: 200 } })
        .catch(() => ({ data: [] }));

      const [filesRes, approvalsRes, servicesRes, partsRes, suppliersRes, customersRes, journalEntriesRes, operationsRes] = await Promise.all([
        filesPromise,
        approvalsPromise,
        servicesPromise,
        partsPromise,
        suppliersPromise,
        customersPromise,
        journalEntriesPromise,
        operationsPromise,
      ]);
      
      setVehicleFiles(filesRes.files || []);
      setServicesCatalog(normalizeListPayload(servicesRes, ['services']));
      setPartsCatalog(normalizeListPayload(partsRes, ['parts']));
      setSuppliersCatalog(normalizePartyCatalog(normalizeListPayload(suppliersRes, ['suppliers']), 'supplier'));
      setCustomersCatalog(normalizePartyCatalog(normalizeListPayload(customersRes, ['customers']), 'customer'));

      const journalRows = Array.isArray(journalEntriesRes?.data?.data)
        ? journalEntriesRes.data.data
        : (Array.isArray(journalEntriesRes?.data) ? journalEntriesRes.data : []);
      const vehicleOps = normalizeListPayload(operationsRes, ['operations']);
      const vehicleOpIds = new Set((vehicleOps || []).map((row) => String(row?.id || '')).filter(Boolean));
      const visitRows = normalizeListPayload(visitsRes, ['visits']);
      const visitIds = new Set((visitRows || []).map((row) => String(row?.id || row?.visitId || '')).filter(Boolean));
      const vehicleTokens = [
        String(vehicleRes.data?.plateNumber || '').trim(),
        String(vehicleRes.data?.fileNumber || '').trim(),
      ].filter(Boolean);
      const customerToken = String(vehicleRes.data?.customerName || '').trim().toLowerCase();
      const filteredJournalEntries = (journalRows || []).filter((entry) => {
        const description = String(entry?.description || '');
        const vehicleRef = extractJournalTag(description, 'VEHICLE_REF').toLowerCase();
        const partyRef = extractJournalTag(description, 'PARTY').toLowerCase();
        const referenceId = String(entry?.reference_id || entry?.referenceId || '').trim();
        const vehicleLabel = String(entry?.vehicle_label || entry?.vehicleLabel || '').toLowerCase();
        const partyLabel = String(entry?.party_label || entry?.partyLabel || '').toLowerCase();
        return vehicleTokens.some((token) => vehicleRef === token.toLowerCase())
          || (customerToken && partyRef === customerToken)
          || visitIds.has(referenceId)
          || vehicleOpIds.has(referenceId)
          || vehicleTokens.some((token) => vehicleLabel.includes(token.toLowerCase()))
          || (customerToken && partyLabel.includes(customerToken));
      }).slice(0, 8);
      setLinkedJournalEntries(filteredJournalEntries);

      const vehicleOpIdList = Array.from(vehicleOpIds);
      if (vehicleOpIdList.length > 0) {
        try {
          const integrityRes = await axios.post(`${API_URL}/operations/integrity/check`, {
            op_ids: vehicleOpIdList,
            vehicle_id: id,
            workshop_id: workshopId || process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync',
          });
          const integrityItems = integrityRes?.data?.data?.items || [];
          const integritySummary = integrityRes?.data?.data?.summary || { total: 0, ok: 0, warnings: 0, duplicates: 0 };
          setVehicleLinkSummary(integritySummary);
          setVehicleLinkIssues(integrityItems.filter((row) => Array.isArray(row?.warnings) && row.warnings.length > 0).slice(0, 5));
        } catch {
          setVehicleLinkSummary({ total: vehicleOpIdList.length, ok: 0, warnings: 0, duplicates: 0 });
          setVehicleLinkIssues([]);
        }
      } else {
        setVehicleLinkSummary({ total: 0, ok: 0, warnings: 0, duplicates: 0 });
        setVehicleLinkIssues([]);
      }
      
      const approvalsRows = normalizeListPayload(approvalsRes, ['approvals']);
      const approvalsByVisit = new Map();
      approvalsRows.forEach((a) => {
        const vId = a.visitId || a.visit_id;
        if (!vId) return;
        if (!approvalsByVisit.has(vId)) approvalsByVisit.set(vId, []);
        approvalsByVisit.get(vId).push(a);
      });
      setApprovals(approvalsRows);

    } catch (error) {
      console.error(error);
      toast({ title: 'خطأ', description: 'فشل تحميل البيانات', variant: 'destructive' });
      setLoading(false);
    } finally {
      setLoadingProgress(100);
    }
  }, [id, API_URL, toast, normalizeListPayload, workshopId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Handle Updates
  const handleUpdateVehicleInfo = async () => {
    try {
      await vehicleAPI.update(id, vehicleForm);
      setVehicle(prev => ({ ...prev, ...vehicleForm }));
      if (isArchiveSource) {
        appendArchiveAudit({
          action: 'vehicle_update',
          actionLabel: 'تحديث بيانات المركبة من الأرشيف',
          vehicleId: id,
          plateNumber: vehicleForm?.plateNumber || vehicle?.plateNumber || '-',
          fileNumber: vehicleForm?.fileNumber || vehicle?.fileNumber || '-',
          details: {
            brand: vehicleForm?.brand,
            model: vehicleForm?.model,
            vin: vehicleForm?.vin,
          },
        });
      }
      setIsEditingVehicle(false);
      toast({ title: 'تم الحفظ', description: 'تم تحديث بيانات المركبة' });
    } catch (e) {
      toast({ title: 'خطأ', description: 'فشل تحديث بيانات المركبة', variant: 'destructive' });
    }
  };

  const handleUpdateCustomerInfo = async () => {
    try {
      // If backend supports updating customer from vehicle update endpoint, use that
      // Or update customer directly. For MVP, we update vehicle record which often holds denormalized data
      // But ideally we update customer entity too.
      await vehicleAPI.update(id, {
        customerName: customerForm.name,
        customerPhone: customerForm.phone,
        customerEmail: customerForm.email,
        customerFileNumber: customerForm.fileNumber || ''
      });
      
      if (vehicle.customerId) {
        await customerAPI.update(vehicle.customerId, {
          name: customerForm.name,
          phone: customerForm.phone,
          email: customerForm.email,
          fileNumber: customerForm.fileNumber || ''
        });
      }
      
      setVehicle(prev => ({ 
        ...prev, 
        customerName: customerForm.name, 
        customerPhone: customerForm.phone,
        customerEmail: customerForm.email,
        customerFileNumber: customerForm.fileNumber || ''
      }));
      if (isArchiveSource) {
        appendArchiveAudit({
          action: 'customer_update',
          actionLabel: 'تحديث بيانات العميل من الأرشيف',
          vehicleId: id,
          plateNumber: vehicle?.plateNumber || vehicleForm?.plateNumber || '-',
          fileNumber: vehicleForm?.fileNumber || vehicle?.fileNumber || '-',
          details: {
            name: customerForm.name,
            phone: customerForm.phone,
            customerFileNumber: customerForm.fileNumber || '-',
          },
        });
      }
      setIsEditingCustomer(false);
      toast({ title: 'تم الحفظ', description: 'تم تحديث بيانات العميل' });
    } catch (e) {
      toast({ title: 'خطأ', description: 'فشل تحديث بيانات العميل', variant: 'destructive' });
    }
  };

  const handleArchiveAuditEvent = useCallback((event = {}) => {
    if (!isArchiveSource) return;
    appendArchiveAudit({
      action: event.action || 'archive_edit',
      actionLabel: event.actionLabel || 'تعديل من الأرشيف',
      vehicleId: id,
      plateNumber: vehicle?.plateNumber || vehicleForm?.plateNumber || '-',
      fileNumber: vehicleForm?.fileNumber || vehicle?.fileNumber || '-',
      details: {
        visitId: event.visitId,
        status: event.status,
        itemsCount: event.itemsCount,
        totalAmount: event.totalAmount,
      },
    });
  }, [isArchiveSource, id, vehicle?.plateNumber, vehicle?.fileNumber, vehicleForm?.plateNumber, vehicleForm?.fileNumber]);

  const requestDeleteVisit = (visitId) => {
    const v = visits.find((x) => x.id === visitId) || visits.find((x) => x.visitId === visitId);
    setDeleteVisitTarget(v || { id: visitId });
    setDeleteVisitOpen(true);
  };

  const confirmDeleteVisit = async () => {
    if (!deleteVisitTarget?.id) return;
    try {
      setDeleteVisitLoading(true);
      await visitAPI.delete(deleteVisitTarget.id);
      handleArchiveAuditEvent({
        action: 'visit_delete',
        actionLabel: 'حذف زيارة من الأرشيف',
        visitId: deleteVisitTarget.id,
      });
      toast({ title: 'تم الحذف', description: 'تم حذف الزيارة بنجاح' });
      setDeleteVisitOpen(false);
      setDeleteVisitTarget(null);
      fetchData();
    } catch (e) {
      toast({ title: 'خطأ', description: 'فشل حذف الزيارة', variant: 'destructive' });
    } finally {
      setDeleteVisitLoading(false);
    }
  };

  // Create new visit handler
  const handleCreateVisit = async () => {
    const missingCustomer = !vehicle?.customerName && !vehicle?.customerId;
    if (missingCustomer) {
      toast({
        title: 'تنبيه',
        description: 'يرجى إدخال بيانات العميل والمركبة قبل استقبال الزيارة.',
        variant: 'destructive',
      });
      return;
    }

    const hasOpenVisit = visits.some((v) => (v.status || '').toLowerCase() === 'in_progress');
    if (hasOpenVisit) {
      const now = Date.now();
      if (!createVisitConfirmAt || now - createVisitConfirmAt > 8000) {
        setCreateVisitConfirmAt(now);
        toast({
          title: 'تنبيه',
          description: 'يوجد زيارة مفتوحة بالفعل. اضغط مرة أخرى للتأكيد وتجنب التكرار.',
          variant: 'destructive',
        });
        return;
      }
    }

    const mileage = prompt("أدخل قراءة العداد الحالية (كم):");
    if (mileage === null) return; // Cancelled
    
    try {
      await axios.post(`${API_URL}/vehicles/${id}/visits`, {
        entryDate: new Date().toISOString(),
        status: 'in_progress',
        mileage: Number(mileage) || 0,
        technicianId: null, // Default none
        notes: JSON.stringify({ items: [], text: '' })
      });
      handleArchiveAuditEvent({
        action: 'visit_create',
        actionLabel: 'إنشاء زيارة جديدة من الأرشيف',
      });
      toast({ title: 'تم', description: 'تم فتح زيارة جديدة' });
      setCreateVisitConfirmAt(null);
      fetchData();
    } catch (e) {
      toast({ title: 'خطأ', description: 'فشل إنشاء زيارة', variant: 'destructive' });
    }
  };

  // Handle status update (Vehicle Level)
  const handleStatusUpdate = async () => {
    try {
      await vehicleAPI.update(id, { 
        status, 
        notes, 
        technicianId: assignedTech || null
      });
      if (isArchiveSource) {
        appendArchiveAudit({
          action: 'vehicle_status_update',
          actionLabel: 'تحديث حالة المركبة من الأرشيف',
          vehicleId: id,
          plateNumber: vehicle?.plateNumber || vehicleForm?.plateNumber || '-',
          fileNumber: vehicleForm?.fileNumber || vehicle?.fileNumber || '-',
          details: {
            status,
            assignedTech,
          },
        });
      }
      toast({ title: 'تم الحفظ', description: 'تم تحديث حالة المركبة' });
      fetchData();
    } catch (e) {
      toast({ title: 'خطأ', description: 'فشل تحديث الحالة', variant: 'destructive' });
    }
  };

  // Scanner Functions
  const openScanner = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        streamRef.current = stream;
      }
      setScannerOpen(true);
    } catch (err) {
      toast({ title: 'خطأ', description: 'فشل في فتح الكاميرا', variant: 'destructive' });
    }
  };

  const closeScanner = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setScannerOpen(false);
    setCapturedImage(null);
  };

  const captureImage = () => {
    if (videoRef.current && canvasRef.current) {
      const canvas = canvasRef.current;
      const video = videoRef.current;
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0);
      canvas.toBlob(async (blob) => {
        const reader = new FileReader();
        reader.onload = (e) => setCapturedImage(e.target.result);
        reader.readAsDataURL(blob);
      }, 'image/jpeg', 0.7);
    }
  };

  const uploadScannedImage = async () => {
    if (!capturedImage) return;
    try {
      const blob = await fetch(capturedImage).then(r => r.blob());
      const file = new File([blob], `scan_${Date.now()}.jpg`, { type: 'image/jpeg' });
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(`${API_URL}/vehicles/${id}/upload-file?file_type=photo`, { method: 'POST', body: formData });
      if (response.ok) {
        toast({ title: 'تم الحفظ', description: 'تم حفظ الصورة بنجاح' });
        closeScanner();
        fetchData();
      }
    } catch (err) {
      toast({ title: 'خطأ', description: 'فشل في رفع الصورة', variant: 'destructive' });
    }
  };

  const blockTitles = {
    vehicle_info: 'معلومات المركبة',
    visits: 'الزيارات',
    financial_summary: 'الملخص المالي',
    guidance: 'إرشادات الملف',
    status_actions: 'الحالة والإجراءات',
  };

  const supplierArchiveRows = useMemo(() => {
    const rows = [];
    (visits || []).forEach((visit) => {
      const visitDate = visit.entryDate || visit.entry_date || visit.createdAt || visit.created_at || '';
      (visit.items || []).forEach((item) => {
        if (String(item?.itemType || '').toLowerCase() !== 'supplier') return;
        const qty = Number(item?.quantity || 1);
        const price = Number(item?.price || 0);
        const amount = Number(item?.total ?? (qty * price));
        rows.push({
          date: visitDate,
          visitId: visit.id,
          supplier: item?.name || 'مورد غير محدد',
          movementType: 'توريد/مشتريات للزيارة',
          qty,
          price,
          amount,
          description: item?.name || '',
        });
      });
    });
    return rows.sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')));
  }, [visits]);

  const openFinancialSource = useCallback((sourceKey) => {
    const allItems = (visits || []).flatMap((visit) =>
      (visit.items || []).map((item) => {
        const qty = Number(item?.quantity || 1);
        const price = Number(item?.price || 0);
        const amount = Number(item?.total ?? (qty * price));
        return {
          date: visit.entryDate || visit.entry_date || visit.createdAt || visit.created_at || '',
          visitId: visit.id,
          itemType: String(item?.itemType || '').toLowerCase(),
          name: item?.name || '-',
          qty,
          price,
          amount,
        };
      })
    );

    const allPayments = (visits || []).flatMap((visit) =>
      (visit.payments || []).map((payment) => ({
        date: payment.date || payment.createdAt || payment.created_at || visit.entryDate || '',
        visitId: visit.id,
        kind: payment.kind || 'payment',
        amount: Number(payment.amount || 0),
        method: payment.method || payment.payment_method || 'cash',
      }))
    );

    let title = 'مصدر الرقم';
    let rows = [];

    if (sourceKey === 'workshop_due') {
      title = 'مصدر رقم ذمم الورشة';
      rows = allItems.filter((it) => it.itemType !== 'supplier').map((it) => ({
        date: it.date,
        visitId: it.visitId,
        type: 'بند ورشة',
        label: it.name,
        amount: it.amount,
        note: `الكمية ${it.qty} × السعر ${it.price}`,
      }));
    } else if (sourceKey === 'suppliers_due') {
      title = 'مصدر رقم ذمم الموردين (أرشيف)';
      rows = supplierArchiveRows.map((it) => ({
        date: it.date,
        visitId: it.visitId,
        type: it.movementType,
        label: it.supplier,
        amount: it.amount,
        note: `الكمية ${it.qty} × السعر ${it.price}`,
      }));
    } else if (sourceKey === 'paid') {
      title = 'مصدر رقم المدفوع';
      rows = allPayments.map((p) => ({
        date: p.date,
        visitId: p.visitId,
        type: 'دفعة',
        label: p.kind,
        amount: p.amount,
        note: `طريقة الدفع: ${p.method}`,
      }));
    } else if (sourceKey === 'advance') {
      title = 'مصدر رقم الدفعة المقدمة';
      rows = allPayments.filter((p) => String(p.kind || '').toLowerCase() === 'advance').map((p) => ({
        date: p.date,
        visitId: p.visitId,
        type: 'دفعة مقدمة',
        label: p.kind,
        amount: p.amount,
        note: `طريقة الدفع: ${p.method}`,
      }));
    } else if (sourceKey === 'balance') {
      title = 'كيف تم احتساب المتبقي';
      const summary = financeSummary || {};
      rows = [
        { date: '-', visitId: '-', type: 'ذمم الورشة', label: 'إجمالي', amount: Number(summary.total_workshop || 0), note: 'إيراد الورشة' },
        { date: '-', visitId: '-', type: 'ذمم الموردين', label: 'إجمالي', amount: Number(summary.total_suppliers || 0), note: 'أرشيف منفصل' },
        { date: '-', visitId: '-', type: 'المدفوع', label: 'إجمالي', amount: Number(summary.total_paid || 0), note: 'إجمالي الدفعات' },
        { date: '-', visitId: '-', type: 'المتبقي', label: 'إجمالي', amount: Number(summary.balance || 0), note: 'المعادلة: (ذمم الورشة + ذمم الموردين) - المدفوع' },
      ];
    }

    setFinancialSourceTitle(title);
    setFinancialSourceRows(rows);
    setFinancialSourceOpen(true);
  }, [visits, supplierArchiveRows, financeSummary]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin" />
        <div className="text-xs" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid="vehicle-loading-status">
          جاري التحميل... {loadingProgress}%
        </div>
      </div>
    );
  }
  if (!vehicle) return (
    <div className="text-center py-20" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid="vehicle-not-found">
      المركبة غير موجودة
    </div>
  );

  // MARKER: VehicleDetails content begins

  const renderBlock = (blockId) => {
    // On mobile we use lighter internal headings because the block already has a title.
    switch (blockId) {
      case 'vehicle_info':
        return (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3" data-testid="vehicle-info-block">
            {/* Vehicle Info Card */}
            <div
              className="liquid-surface relative"
              data-testid="vehicle-info-card"
              style={{
                borderRadius: 20,
                padding: 14,
                background:
                  'radial-gradient(circle at 12% 18%, rgba(248,250,252,0.98), rgba(241,245,249,0.96))',
                border: '1px solid rgba(203,213,225,0.8)',
              }}
            >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2" style={{ color: 'rgba(3,105,161,0.95)' }}>
                    <Car size={18} />
                    <h3 className="text-sm font-extrabold" style={{ color: 'rgba(15,23,42,0.95)' }}>
                      {t('vehicle_details.vehicle_info')}
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setIsVehicleInfoCollapsed((v) => !v)}
                      className="px-3 py-1.5 rounded-xl text-xs"
                      style={{
                        background: 'rgba(255,255,255,0.8)',
                        border: '1px solid rgba(203,213,225,0.8)',
                        color: 'rgba(71,85,105,0.9)',
                      }}
                      data-testid="vehicle-info-collapse-toggle"
                    >
                      {isVehicleInfoCollapsed ? 'فتح' : 'إخفاء'}
                    </button>
                    <button
                      onClick={() => {
                        setIsEditingVehicle(!isEditingVehicle);
                        setIsVehicleInfoCollapsed(false);
                      }}
                      className="p-2 rounded-xl"
                      style={{
                        background: 'rgba(255,255,255,0.8)',
                        border: '1px solid rgba(203,213,225,0.8)',
                        color: 'rgba(71,85,105,0.9)',
                      }}
                      data-testid="vehicle-edit-toggle"
                    >
                      {isEditingVehicle ? <X size={16} /> : <Edit2 size={16} />}
                    </button>
                  </div>
                </div>

                {(!isVehicleInfoCollapsed || isEditingVehicle) ? (
                <div className="space-y-3" data-testid="vehicle-info-content">
                  <div className="flex flex-col py-2" style={{ borderBottom: '1px solid rgba(203,213,225,0.8)' }}>
                    <span className="text-[11px] mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>{t('vehicles.plate_number')}</span>
                    {isEditingVehicle ? (
                      <input
                        className="w-full text-sm rounded-xl px-3 py-2"
                        style={{
                          background: 'rgba(255,255,255,0.8)',
                          border: '1px solid rgba(203,213,225,0.8)',
                          color: 'rgba(15,23,42,0.92)',
                        }}
                        value={vehicleForm.plateNumber}
                        onChange={(e) => setVehicleForm({ ...vehicleForm, plateNumber: e.target.value })}
                        data-testid="vehicle-plate-input"
                      />
                    ) : (
                      <span
                        className="text-sm font-semibold"
                        style={{ color: 'rgba(15,23,42,0.92)' }}
                        data-testid="vehicle-plate-value"
                      >
                        {vehicle.plateNumber}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-col py-2" style={{ borderBottom: '1px solid rgba(203,213,225,0.8)' }}>
                    <span className="text-[11px] mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>{t('vehicle_details.brand_model')}</span>
                    {isEditingVehicle ? (
                      <div className="flex gap-2">
                        <input
                          className="text-sm rounded-xl px-3 py-2 w-1/2"
                          style={{
                            background: 'rgba(255,255,255,0.8)',
                            border: '1px solid rgba(203,213,225,0.8)',
                            color: 'rgba(15,23,42,0.92)',
                          }}
                          value={vehicleForm.brand}
                          onChange={(e) => setVehicleForm({ ...vehicleForm, brand: e.target.value })}
                          placeholder="الماركة"
                          data-testid="vehicle-brand-input"
                        />
                        <input
                          className="text-sm rounded-xl px-3 py-2 w-1/2"
                          style={{
                            background: 'rgba(255,255,255,0.8)',
                            border: '1px solid rgba(203,213,225,0.8)',
                            color: 'rgba(15,23,42,0.92)',
                          }}
                          value={vehicleForm.model}
                          onChange={(e) => setVehicleForm({ ...vehicleForm, model: e.target.value })}
                          placeholder="الموديل"
                          data-testid="vehicle-model-input"
                        />
                      </div>
                    ) : (
                      <span
                        className="text-sm font-semibold"
                        style={{ color: 'rgba(15,23,42,0.92)' }}
                        data-testid="vehicle-brand-model-value"
                      >
                        {vehicle.brand} {vehicle.model}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-col py-2" style={{ borderBottom: '1px solid rgba(203,213,225,0.8)' }}>
                    <span className="text-[11px] mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>{t('vehicle_details.vin_number')}</span>
                    {isEditingVehicle ? (
                      <input
                        className="w-full text-sm rounded-xl px-3 py-2"
                        style={{
                          background: 'rgba(255,255,255,0.8)',
                          border: '1px solid rgba(203,213,225,0.8)',
                          color: 'rgba(15,23,42,0.92)',
                        }}
                        value={vehicleForm.vin}
                        onChange={(e) => setVehicleForm({ ...vehicleForm, vin: e.target.value })}
                        data-testid="vehicle-vin-input"
                      />
                    ) : (
                      <span
                        className="text-sm font-semibold font-mono"
                        style={{ color: 'rgba(15,23,42,0.92)' }}
                        data-testid="vehicle-vin-value"
                      >
                        {vehicle.vin || '-'}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-col py-2" style={{ borderBottom: '1px solid rgba(203,213,225,0.8)' }}>
                    <span className="text-[11px] mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>رقم ملف المركبة</span>
                    {isEditingVehicle ? (
                      <input
                        className="w-full text-sm rounded-xl px-3 py-2"
                        style={{
                          background: 'rgba(255,255,255,0.8)',
                          border: '1px solid rgba(203,213,225,0.8)',
                          color: 'rgba(15,23,42,0.92)',
                        }}
                        value={vehicleForm.fileNumber || ''}
                        onChange={(e) => setVehicleForm({ ...vehicleForm, fileNumber: e.target.value })}
                        data-testid="vehicle-file-number-input"
                      />
                    ) : (
                      <span
                        className="text-sm font-semibold"
                        style={{ color: 'rgba(3,105,161,0.95)' }}
                        data-testid="vehicle-file-number-value"
                      >
                        {vehicle.fileNumber || '-'}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-col py-2">
                    <span className="text-[11px] mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>{t('vehicle_details.color')}</span>
                    {isEditingVehicle ? (
                      <input
                        className="w-full text-sm rounded-xl px-3 py-2"
                        style={{
                          background: 'rgba(255,255,255,0.8)',
                          border: '1px solid rgba(203,213,225,0.8)',
                          color: 'rgba(15,23,42,0.92)',
                        }}
                        value={vehicleForm.color}
                        onChange={(e) => setVehicleForm({ ...vehicleForm, color: e.target.value })}
                        data-testid="vehicle-color-input"
                      />
                    ) : (
                      <span
                        className="text-sm font-semibold"
                        style={{ color: 'rgba(15,23,42,0.92)' }}
                        data-testid="vehicle-color-value"
                      >
                        {vehicle.color || '-'}
                      </span>
                    )}
                  </div>

                  {isEditingVehicle && (
                    <button
                      onClick={handleUpdateVehicleInfo}
                      className="w-full rounded-2xl px-4 py-3 text-sm font-extrabold mt-2"
                      style={{
                        background: 'rgba(56,189,248,0.14)',
                        border: '1px solid rgba(56,189,248,0.28)',
                        color: 'rgba(3,105,161,0.95)',
                      }}
                      data-testid="vehicle-save-button"
                    >
                      حفظ التعديلات
                    </button>
                  )}
                </div>
                ) : (
                  <div className="text-xs" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid="vehicle-info-collapsed-hint">
                    البلوك منكمش — اضغط فتح لعرض التفاصيل.
                  </div>
                )}
              </div>

            {/* Customer Info */}
            <div
              className="liquid-surface relative"
              data-testid="customer-info-card"
              style={{
                borderRadius: 20,
                padding: 14,
                background:
                  'radial-gradient(circle at 12% 18%, rgba(248,250,252,0.98), rgba(241,245,249,0.96))',
                border: '1px solid rgba(203,213,225,0.8)',
              }}
            >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2" style={{ color: 'rgba(4,120,87,0.95)' }}>
                    <User size={18} />
                    <h3 className="text-sm font-extrabold" style={{ color: 'rgba(15,23,42,0.95)' }}>
                      {t('vehicle_details.customer_info')}
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setIsCustomerInfoCollapsed((v) => !v)}
                      className="px-3 py-1.5 rounded-xl text-xs"
                      style={{
                        background: 'rgba(255,255,255,0.8)',
                        border: '1px solid rgba(203,213,225,0.8)',
                        color: 'rgba(71,85,105,0.9)',
                      }}
                      data-testid="customer-info-collapse-toggle"
                    >
                      {isCustomerInfoCollapsed ? 'فتح' : 'إخفاء'}
                    </button>
                    <button
                      onClick={() => {
                        setIsEditingCustomer(!isEditingCustomer);
                        setIsCustomerInfoCollapsed(false);
                      }}
                      className="p-2 rounded-xl"
                      style={{
                        background: 'rgba(255,255,255,0.8)',
                        border: '1px solid rgba(203,213,225,0.8)',
                        color: 'rgba(71,85,105,0.9)',
                      }}
                      data-testid="customer-edit-toggle"
                    >
                      {isEditingCustomer ? <X size={16} /> : <Edit2 size={16} />}
                    </button>
                  </div>
                </div>

                {(!isCustomerInfoCollapsed || isEditingCustomer) ? (
                <div className="space-y-3" data-testid="customer-info-content">
                  <div className="flex flex-col py-2" style={{ borderBottom: '1px solid rgba(203,213,225,0.8)' }}>
                    <span className="text-[11px] mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>{t('vehicles_page.customer_name')}</span>
                    {isEditingCustomer ? (
                      <input
                        className="w-full text-sm rounded-xl px-3 py-2"
                        style={{
                          background: 'rgba(255,255,255,0.8)',
                          border: '1px solid rgba(203,213,225,0.8)',
                          color: 'rgba(15,23,42,0.92)',
                        }}
                        value={customerForm.name}
                        onChange={(e) => setCustomerForm({ ...customerForm, name: e.target.value })}
                        data-testid="customer-name-input"
                      />
                    ) : (
                      <span
                        className="text-sm font-semibold"
                        style={{ color: 'rgba(15,23,42,0.92)' }}
                        data-testid="customer-name-value"
                      >
                        {vehicle.customerName}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-col py-2" style={{ borderBottom: '1px solid rgba(203,213,225,0.8)' }}>
                    <span className="text-[11px] mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>رقم الجوال</span>
                    {isEditingCustomer ? (
                      <input
                        className="w-full text-sm rounded-xl px-3 py-2"
                        style={{
                          background: 'rgba(255,255,255,0.8)',
                          border: '1px solid rgba(203,213,225,0.8)',
                          color: 'rgba(15,23,42,0.92)',
                        }}
                        value={customerForm.phone}
                        onChange={(e) => setCustomerForm({ ...customerForm, phone: e.target.value })}
                        data-testid="customer-phone-input"
                      />
                    ) : (
                      <span
                        className="text-sm font-semibold"
                        style={{ color: 'rgba(15,23,42,0.92)' }}
                        dir="ltr"
                        data-testid="customer-phone-value"
                      >
                        {vehicle.customerPhone}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-col py-2">
                    <span className="text-[11px] mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>رقم ملف المركبة</span>
                    <span
                      className="text-sm font-semibold"
                      style={{ color: 'rgba(3,105,161,0.95)' }}
                      data-testid="customer-file-number-value"
                    >
                      {vehicle.fileNumber || '-'}
                    </span>
                  </div>
                  <div className="flex flex-col py-2">
                    <span className="text-[11px] mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>رقم ملف العميل المرتبط</span>
                    {isEditingCustomer ? (
                      <input
                        className="w-full text-sm rounded-xl px-3 py-2"
                        style={{
                          background: 'rgba(255,255,255,0.8)',
                          border: '1px solid rgba(203,213,225,0.8)',
                          color: 'rgba(15,23,42,0.92)',
                        }}
                        value={customerForm.fileNumber || ''}
                        onChange={(e) => setCustomerForm({ ...customerForm, fileNumber: e.target.value })}
                        data-testid="customer-file-number-input"
                      />
                    ) : (
                      <span
                        className="text-sm font-semibold"
                        style={{ color: 'rgba(4,120,87,0.95)' }}
                        data-testid="customer-linked-file-number-value"
                      >
                        {vehicle.customerFileNumber || '-'}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-col py-2">
                    <span className="text-[11px] mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>البريد الإلكتروني</span>
                    {isEditingCustomer ? (
                      <input
                        className="w-full text-sm rounded-xl px-3 py-2"
                        style={{
                          background: 'rgba(255,255,255,0.8)',
                          border: '1px solid rgba(203,213,225,0.8)',
                          color: 'rgba(15,23,42,0.92)',
                        }}
                        value={customerForm.email}
                        onChange={(e) => setCustomerForm({ ...customerForm, email: e.target.value })}
                        data-testid="customer-email-input"
                      />
                    ) : (
                      <span
                        className="text-sm font-semibold"
                        style={{ color: 'rgba(15,23,42,0.92)' }}
                        data-testid="customer-email-value"
                      >
                        {vehicle.customerEmail || '-'}
                      </span>
                    )}
                  </div>

                  {isEditingCustomer && (
                    <button
                      onClick={handleUpdateCustomerInfo}
                      className="w-full rounded-2xl px-4 py-3 text-sm font-extrabold mt-2"
                      style={{
                        background: 'rgba(16,185,129,0.14)',
                        border: '1px solid rgba(16,185,129,0.28)',
                        color: 'rgba(4,120,87,0.95)',
                      }}
                      data-testid="customer-save-button"
                    >
                      حفظ التعديلات
                    </button>
                  )}
                </div>
                ) : (
                  <div className="text-xs" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid="customer-info-collapsed-hint">
                    البلوك منكمش — اضغط فتح لعرض التفاصيل.
                  </div>
                )}
              </div>

            {/* Files Section (Load on demand) */}
            <div
              className="liquid-surface lg:col-span-2"
              style={{
                borderRadius: 20,
                padding: 16,
                background:
                  'radial-gradient(circle at 12% 18%, rgba(248,250,252,0.98), rgba(241,245,249,0.96))',
                border: '1px solid rgba(203,213,225,0.8)',
              }}
              data-testid="vehicle-files-card"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2" style={{ color: 'rgba(3,105,161,0.95)' }}>
                  <FileText size={18} />
                  <h3
                    className="text-sm font-extrabold"
                    style={{ color: 'rgba(15,23,42,0.95)' }}
                    data-testid="vehicle-files-title"
                  >
                    {t('vehicle_details.files')}
                  </h3>
                </div>
                <button
                  onClick={() => setShowFiles((v) => !v)}
                  className="text-xs px-3 py-1.5 rounded-xl"
                  style={{
                    background: 'rgba(255,255,255,0.8)',
                    border: '1px solid rgba(203,213,225,0.8)',
                    color: 'rgba(71,85,105,0.9)',
                  }}
                  data-testid="vehicle-files-toggle"
                >
                  {showFiles ? 'إخفاء' : 'عرض'}
                </button>
              </div>

              {showFiles && (
                <>
                  <div className="flex gap-2 mb-4">
                    <button
                      onClick={openScanner}
                      className="p-2 rounded-xl"
                      style={{
                        background: 'rgba(255,255,255,0.8)',
                        border: '1px solid rgba(203,213,225,0.8)',
                        color: 'rgba(71,85,105,0.9)',
                      }}
                      data-testid="vehicle-files-scan-button"
                    >
                      <Scan size={16} />
                    </button>
                    <label
                      className="p-2 rounded-xl cursor-pointer inline-flex"
                      style={{
                        background: 'rgba(255,255,255,0.8)',
                        border: '1px solid rgba(203,213,225,0.8)',
                        color: 'rgba(71,85,105,0.9)',
                      }}
                      data-testid="vehicle-files-upload-button"
                    >
                      <Upload size={16} />
                      <input
                        type="file"
                        className="hidden"
                        onChange={async (e) => {
                          const file = e.target.files[0];
                          if (file) {
                            const formData = new FormData();
                            formData.append('file', file);
                            await fetch(`${API_URL}/vehicles/${id}/upload-file?file_type=other`, {
                              method: 'POST',
                              body: formData,
                            });
                            fetchData();
                          }
                        }}
                        data-testid="vehicle-files-upload-input"
                      />
                    </label>
                  </div>

                  <div className="grid grid-cols-3 gap-2" data-testid="vehicle-files-grid">
                    {vehicleFiles.slice(0, 6).map((file, idx) => (
                      <div
                        key={idx}
                        className="aspect-square rounded-xl flex items-center justify-center text-xs overflow-hidden relative group cursor-pointer"
                        style={{
                          background: 'rgba(248,250,252,0.6)',
                          border: '1px solid rgba(203,213,225,0.8)',
                          color: 'rgba(100,116,139,0.9)',
                        }}
                        onClick={() => setPreviewImage(`${FILE_BASE}/api/vehicles/${id}/files/${file.id}`)}
                        data-testid={`vehicle-file-item-${file.id || idx}`}
                      >
                        {file.filename.match(/\.(jpg|jpeg|png|gif)$/i) ? (
                          <img
                            src={`${FILE_BASE}/api/vehicles/${id}/files/${file.id}`}
                            alt="file"
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <FileText size={24} />
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}

              {!showFiles && (
                <div className="text-xs" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid="vehicle-files-placeholder">
                  اضغط “عرض” لتحميل ملفات المركبة
                </div>
              )}
            </div>

            <div
              className="liquid-surface lg:col-span-2"
              style={{
                borderRadius: 20,
                padding: 16,
                background:
                  'radial-gradient(circle at 12% 18%, rgba(248,250,252,0.98), rgba(241,245,249,0.96))',
                border: '1px solid rgba(203,213,225,0.8)',
              }}
              data-testid="vehicle-linked-journal-card"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2" style={{ color: 'rgba(4,120,87,0.95)' }}>
                  <Receipt size={18} />
                  <h3 className="text-sm font-extrabold" style={{ color: 'rgba(15,23,42,0.95)' }}>
                    قيود دفتر اليومية المرتبطة
                  </h3>
                </div>
                <div className="text-[11px]" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid="vehicle-linked-journal-count">
                  {linkedJournalEntries.length} قيد
                </div>
              </div>

              {linkedJournalEntries.length === 0 ? (
                <div className="text-xs" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid="vehicle-linked-journal-empty">
                  لا توجد قيود مرتبطة بالمركبة أو العميل حالياً.
                </div>
              ) : (
                <div className="space-y-2" data-testid="vehicle-linked-journal-list">
                  {linkedJournalEntries.map((entry, index) => (
                    <div
                      key={entry?.id || `linked-journal-${index}`}
                      className="rounded-xl px-3 py-2.5"
                      style={{
                        background: 'rgba(248,250,252,0.6)',
                        border: '1px solid rgba(203,213,225,0.8)',
                      }}
                      data-testid={`vehicle-linked-journal-row-${entry?.id || index}`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-semibold truncate" style={{ color: 'rgba(15,23,42,0.92)' }}>
                            {stripJournalTags(entry?.description || 'قيد مرتبط')}
                          </div>
                          <div className="text-[11px] mt-1" style={{ color: 'rgba(100,116,139,0.9)' }}>
                            {String(entry?.date || '').slice(0, 10) || '-'} • {labelFromMap(entry?.source, SOURCE_LABELS, 'قيد يومية')}
                            {entry?.vehicle_label ? ` • مركبة: ${entry.vehicle_label}` : ''}
                            {entry?.party_label ? ` • عميل: ${entry.party_label}` : ''}
                          </div>
                        </div>
                        <div className="text-sm font-extrabold tabular-nums" style={{ color: 'rgba(4,120,87,0.95)' }}>
                          {formatCurrency(entry?.total || 0)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        );

      case 'financial_summary':
        return (
          <div
            className="liquid-surface liquid-section space-y-3"
            style={{ padding: 0, background: 'transparent', border: '0' }}
            data-testid="vehicle-financial-summary-block"
          >
            <VehicleFinancialSummary summary={financeSummary || {}} t={t} onShowSource={openFinancialSource} />

            {/* supplier archive block removed - visible only in /suppliers page */}
          </div>
        );

      case 'guidance':
        return (
          <div data-testid="vehicle-guidance-stepper">
            <GuidanceStepper
              title="إرشادات ملف المركبة"
              subtitle="خطوات سريعة لتجنب التكرار والأخطاء الإملائية والمالية."
              steps={guidanceSteps}
              enabled={guidanceEnabled}
              storageKey={`guidance-vehicle-${userId}`}
            />
          </div>
        );

      case 'visits':
        return (
          <div className="space-y-4" data-testid="vehicle-visits-block">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <button
                onClick={handleCreateVisit}
                className="px-3 py-2 rounded-xl text-xs font-bold shadow-sm transition-all flex items-center gap-2"
                style={{
                  background: 'rgba(56,189,248,0.16)',
                  border: '1px solid rgba(56,189,248,0.28)',
                  color: 'rgba(3,105,161,0.95)',
                }}
                data-testid="visit-create-button"
              >
                <Plus size={14} /> زيارة جديدة
              </button>
              <div className="text-[11px]" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid="visit-items-edit-hint">
                {t('vehicle_details.items_edit_hint')}
              </div>
            </div>

            <div
              className="rounded-xl px-3 py-2.5 flex flex-wrap gap-2 items-center"
              style={{
                background: 'rgba(241,245,249,0.8)',
                border: '1px solid rgba(148,163,184,0.20)',
              }}
              data-testid="vehicle-linkage-summary-card"
            >
              <span className="px-2 py-1 rounded-full text-[11px]" style={{ background: 'rgba(34,197,94,0.16)', color: 'rgba(21,128,61,0.95)' }} data-testid="vehicle-linkage-ok-count">
                مترابط: {vehicleLinkSummary.ok || 0}
              </span>
              <span className="px-2 py-1 rounded-full text-[11px]" style={{ background: 'rgba(239,68,68,0.14)', color: 'rgba(185,28,28,0.95)' }} data-testid="vehicle-linkage-warning-count">
                ملاحظات: {vehicleLinkSummary.warnings || 0}
              </span>
              <span className="px-2 py-1 rounded-full text-[11px]" style={{ background: 'rgba(245,158,11,0.16)', color: 'rgba(180,83,9,0.95)' }} data-testid="vehicle-linkage-duplicate-count">
                تكرار محتمل: {vehicleLinkSummary.duplicates || 0}
              </span>
              <span className="text-[11px]" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid="vehicle-linkage-location-hint">
                كشف الربط: ملف المركبة ↔ العمليات ↔ دفتر اليومية.
              </span>
            </div>

            {vehicleLinkIssues.length > 0 && (
              <div className="rounded-xl px-3 py-2 text-[11px] space-y-1" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.26)', color: 'rgba(159,18,57,0.95)' }} data-testid="vehicle-linkage-issues-list">
                {vehicleLinkIssues.map((issue, idx) => (
                  <div key={`vehicle-link-issue-${idx}`} data-testid={`vehicle-linkage-issue-${idx}`}>
                    • {issue?.invoice_number ? `فاتورة ${issue.invoice_number}` : `عملية مرتبطة ${String(issue?.op_id || '').slice(0, 8)}`} فيها: {(issue?.warnings || []).map((w) => integrityLabelMap[w] || w).join('، ')}
                  </div>
                ))}
              </div>
            )}

            <div
              className="flex gap-2 text-xs overflow-x-auto whitespace-nowrap pb-1"
              style={{ WebkitOverflowScrolling: 'touch' }}
              data-testid="visit-filter-controls"
            >
              {[
                { key: 'all', label: 'كل الزيارات', count: visits.length },
                {
                  key: 'open',
                  label: 'المفتوحة',
                  count: visits.filter((v) => (v.status || '').toLowerCase() !== 'completed').length,
                },
                {
                  key: 'closed',
                  label: 'المغلقة',
                  count: visits.filter((v) => (v.status || '').toLowerCase() === 'completed').length,
                },
              ].map((filter) => {
                const isActive = visitFilter === filter.key;
                return (
                  <button
                    key={filter.key}
                    onClick={() => setVisitFilter(filter.key)}
                    className="px-3 py-1.5 rounded-full text-xs font-bold transition-all"
                    style={{
                      background: isActive ? 'rgba(56,189,248,0.16)' : 'rgba(241,245,249,0.8)',
                      border: `1px solid ${isActive ? 'rgba(56,189,248,0.28)' : 'rgba(203,213,225,0.8)'}`,
                      color: isActive ? 'rgba(3,105,161,0.95)' : 'rgba(100,116,139,0.9)',
                    }}
                    data-testid={`visit-filter-${filter.key}`}
                  >
                    {filter.label} ({filter.count})
                  </button>
                );
              })}
            </div>

            {visitFilter !== 'all' && filteredVisits.length === 0 && visits.length > 0 && (
              <div
                className="rounded-xl px-3 py-2 text-xs flex items-center justify-between"
                style={{
                  background: 'rgba(245,158,11,0.08)',
                  border: '1px solid rgba(245,158,11,0.22)',
                  color: 'rgba(180,83,9,0.95)',
                }}
                data-testid="visit-filter-empty-hint"
              >
                <span>لا توجد زيارات في هذا الفلتر. الزيارات موجودة في فلاتر أخرى.</span>
                <button
                  onClick={() => setVisitFilter('all')}
                  className="font-bold underline mr-2"
                  style={{ color: 'rgba(180,83,9,0.95)' }}
                  data-testid="visit-filter-show-all"
                >
                  عرض الكل
                </button>
              </div>
            )}

            <div className="space-y-4">
              {filteredVisits.length === 0 && (visitFilter === 'all' || visits.length === 0) ? (
                <div
                  className="text-center py-8 rounded-xl"
                  style={{
                    background: 'rgba(241,245,249,0.8)',
                    border: '1px dashed rgba(148,163,184,0.20)',
                    color: 'rgba(100,116,139,0.9)',
                  }}
                  data-testid="visits-empty-state"
                >
                  <Calendar size={32} className="mx-auto mb-2" style={{ color: 'rgba(148,163,184,0.55)' }} />
                  <p className="text-xs" data-testid="visits-empty-title">لا توجد زيارات بعد</p>
                  <p className="text-[11px] mt-1" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid="visits-empty-subtitle">
                    اضغط "زيارة جديدة" لاستقبال المركبة
                  </p>
                </div>
              ) : (
                filteredVisits.map((visit) => {
                  const normVisit = {
                    ...visit,
                    entryDate: visit.entryDate || visit.entry_date,
                    exitDate: visit.exitDate || visit.exit_date,
                    technicianId: visit.technicianId || visit.technician_id,
                    createdAt: visit.createdAt || visit.created_at,
                  };
                  const visitApprovals = approvals
                    .filter((a) => (a.visitId || a.visit_id) === normVisit.id)
                    .sort((x, y) =>
                      String(y.createdAt || y.created_at || '').localeCompare(
                        String(x.createdAt || x.created_at || '')
                      )
                    );

                  return (
                    <VisitCard
                      key={normVisit.id}
                      visit={normVisit}
                      vehicle={vehicle}
                      technicians={technicians}
                      onUpdate={fetchData}
                      onVisitClosed={handleVisitClosed}
                      onShowWhatsAppPreview={(notification) => {
                        setWaPreview(notification);
                        setWaPreviewOpen(true);
                      }}
                      approvals={visitApprovals}
                      onDelete={requestDeleteVisit}
                      servicesCatalog={servicesCatalog}
                      partsCatalog={partsCatalog}
                      suppliersCatalog={suppliersCatalog}
                      customersCatalog={customersCatalog}
                      onServiceAdded={appendService}
                      onPartAdded={appendPart}
                      onSupplierAdded={appendSupplier}
                      canDelete={canDeleteVisit}
                      archiveMode={isArchiveSource}
                      onAuditEvent={handleArchiveAuditEvent}
                      onOpenQuickPrintDialog={openQuickPrintDialog}
                    />
                  );
                })
              )}
            </div>
          </div>
        );

      case 'status_actions':
        return (
          <div className="space-y-4" data-testid="vehicle-status-block">
            <div
              className="liquid-surface"
              style={{
                borderRadius: 20,
                padding: 16,
                background: 'rgba(248,250,252,0.6)',
                border: '1px solid rgba(203,213,225,0.8)',
              }}
              data-testid="vehicle-status-card"
            >
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-[11px] font-medium" style={{ color: 'rgba(100,116,139,0.9)' }}>
                    {t('quick_actions.change_status')}
                  </label>
                  <select
                    className="w-full text-sm rounded-xl p-2"
                    style={{
                      background: 'rgba(255,255,255,0.8)',
                      border: '1px solid rgba(203,213,225,0.8)',
                      color: 'rgba(15,23,42,0.92)',
                    }}
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    data-testid="vehicle-status-select"
                  >
                    {statusSteps.map((s) => (
                      <option key={s.key} value={s.key}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-[11px] font-medium" style={{ color: 'rgba(100,116,139,0.9)' }}>
                    الفني المسؤول
                  </label>
                  <select
                    className="w-full text-sm rounded-xl p-2"
                    style={{
                      background: 'rgba(255,255,255,0.8)',
                      border: '1px solid rgba(203,213,225,0.8)',
                      color: 'rgba(15,23,42,0.92)',
                    }}
                    value={assignedTech}
                    onChange={(e) => setAssignedTech(e.target.value)}
                    data-testid="vehicle-assigned-tech-select"
                  >
                    <option value="">اختر الفني...</option>
                    {technicians.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-[11px] font-medium" style={{ color: 'rgba(100,116,139,0.9)' }}>
                    ملاحظات عامة
                  </label>
                  <textarea
                    className="w-full text-sm rounded-2xl p-3 min-h-[120px] resize-none"
                    style={{
                      background: 'rgba(255,255,255,0.8)',
                      border: '1px solid rgba(203,213,225,0.8)',
                      color: 'rgba(15,23,42,0.92)',
                    }}
                    placeholder="ملاحظات..."
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    data-testid="vehicle-notes-textarea"
                  />
                </div>

                <button
                  onClick={handleStatusUpdate}
                  className="w-full rounded-2xl px-4 py-3 text-sm font-extrabold"
                  style={{
                    background: 'rgba(56,189,248,0.14)',
                    border: '1px solid rgba(56,189,248,0.28)',
                    color: 'rgba(3,105,161,0.95)',
                  }}
                  data-testid="vehicle-status-save-button"
                >
                  حفظ التحديثات
                </button>
              </div>
            </div>

            <div
              className="liquid-surface"
              style={{
                borderRadius: 20,
                padding: 16,
                background: 'rgba(241,245,249,0.8)',
                border: '1px solid rgba(203,213,225,0.8)',
              }}
              data-testid="vehicle-dates-card"
            >
              <div className="space-y-3 text-xs" style={{ color: 'rgba(100,116,139,0.9)' }}>
                <div className="flex justify-between">
                  <span>تاريخ الدخول</span>
                  <span className="font-semibold" style={{ color: 'rgba(15,23,42,0.92)' }} data-testid="vehicle-entry-date">
                    {vehicle.entryDate ? new Date(vehicle.entryDate).toLocaleDateString('ar-SA') : '-'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>آخر تحديث</span>
                  <span className="font-semibold" style={{ color: 'rgba(15,23,42,0.92)' }} data-testid="vehicle-updated-date">
                    {vehicle.updatedAt || vehicle.updated_at
                      ? new Date(vehicle.updatedAt || vehicle.updated_at).toLocaleDateString('ar-SA')
                      : '-'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="vehicle-details-page max-w-6xl mx-auto pb-20 space-y-6" style={{ direction: isRTL ? 'rtl' : 'ltr' }}>
      <style>{`
        /* Make native select/options readable (browser renders options in its own UI) */
        select { color: rgba(15,23,42,0.92); }
        option { color: #0f172a; }

        /* Contrast hardening for remaining legacy inline colors in this page */
        .vehicle-details-page [style*="100, 116, 139"] { color: rgba(51,65,85,0.95) !important; }
        .vehicle-details-page [style*="248, 250, 252, 0.6"] { background: rgba(248,250,252,0.96) !important; }
        .vehicle-details-page [style*="255, 255, 255, 0.8"] { background: rgba(255,255,255,0.96) !important; }
      `}</style>

      {isArchiveSource && (
        <div
          className="mx-4 sm:mx-0 rounded-2xl px-4 py-3"
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
      )}

      {/* Header */}
      <div
        className="liquid-surface"
        style={{
          padding: 16,
          borderRadius: 24,
          background:
            'radial-gradient(circle at 12% 18%, rgba(248,250,252,0.98), rgba(241,245,249,0.96))',
          border: '1px solid rgba(203,213,225,0.8)',
        }}
        data-testid="vehicle-header"
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4 min-w-0">
            <button
              onClick={() => navigate(isArchiveSource ? '/archive' : '/')}
              className="p-2 rounded-xl transition-colors"
              style={{
                background: 'rgba(255,255,255,0.8)',
                border: '1px solid rgba(203,213,225,0.8)',
                color: 'rgba(71,85,105,0.9)',
              }}
              data-testid="vehicle-back-button"
            >
              <ArrowRight size={22} />
            </button>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 flex-wrap">
                <h1
                  className="text-xl sm:text-3xl font-extrabold"
                  style={{ color: 'rgba(15,23,42,0.95)' }}
                  data-testid="vehicle-plate-header"
                >
                  {vehicle.plateNumber}
                </h1>
                <span
                  className={`px-3 py-1 rounded-full text-xs sm:text-sm font-semibold ${getStatusColor(vehicle.status)}`}
                  style={{ color: 'white' }}
                  data-testid="vehicle-status-badge"
                >
                  {getStatusLabel(vehicle.status)}
                </span>
              </div>
              <p
                className="mt-1 text-sm"
                style={{ color: 'rgba(100,116,139,0.9)' }}
                data-testid="vehicle-brand-model-header"
              >
                {vehicle.brand} {vehicle.model} - {vehicle.year}
              </p>
            </div>
          </div>

          <div className="flex gap-2">
            <div className="relative group">
              <button
                className="px-3 py-2 rounded-xl text-xs font-bold flex items-center gap-2"
                style={{
                  background: 'rgba(255,255,255,0.8)',
                  border: '1px solid rgba(203,213,225,0.8)',
                  color: 'rgba(15,23,42,0.92)',
                }}
                data-testid="vehicle-print-menu-button"
              >
                <Printer size={16} />
                <span className="hidden sm:inline">طباعة / PDF</span>
              </button>
              {/* Dropdown Menu */}
              <div
                className="absolute top-full left-0 mt-2 w-48 rounded-xl shadow-xl overflow-hidden hidden group-hover:block z-50"
                style={{
                  background: 'rgba(255,255,255,0.98)',
                  border: '1px solid rgba(203,213,225,0.8)',
                }}
                data-testid="vehicle-print-menu"
              >
                <button
                  onClick={() => {
                    const active = visits.find(v => (v.status || '') === 'in_progress') || visits[0];
                    const vid = active?.id;
                    openQuickPrintDialog({ type: 'invoice', visitId: vid });
                  }}
                  className="w-full text-right px-4 py-3 flex items-center gap-2 text-sm transition-colors"
                  style={{ color: 'rgba(15,23,42,0.9)' }}
                  data-testid="vehicle-print-invoice"
                >
                  <Receipt size={16} style={{ color: 'rgba(4,120,87,0.95)' }} />
                  فاتورة مبيعات
                </button>
                <button
                  onClick={() => {
                    const active = visits.find(v => (v.status || '') === 'in_progress') || visits[0];
                    const vid = active?.id;
                    openQuickPrintDialog({ type: 'quote', visitId: vid });
                  }}
                  className="w-full text-right px-4 py-3 flex items-center gap-2 text-sm transition-colors"
                  style={{
                    borderTop: '1px solid rgba(203,213,225,0.8)',
                    color: 'rgba(15,23,42,0.9)',
                  }}
                  data-testid="vehicle-print-quote"
                >
                  <FileCheck size={16} style={{ color: 'rgba(3,105,161,0.95)' }} />
                  عرض سعر
                </button>
                <button
                  onClick={() => {
                    const active = visits.find(v => (v.status || '') === 'in_progress') || visits[0];
                    const vid = active?.id;
                    openQuickPrintDialog({ type: 'diagnosis', visitId: vid });
                  }}
                  className="w-full text-right px-4 py-3 flex items-center gap-2 text-sm transition-colors"
                  style={{
                    borderTop: '1px solid rgba(203,213,225,0.8)',
                    color: 'rgba(15,23,42,0.9)',
                  }}
                  data-testid="vehicle-print-diagnosis"
                >
                  <ClipboardList size={16} style={{ color: 'rgba(253,230,138,0.95)' }} />
                  تقرير تشخيص
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>


      {/* Financial Summary (moved into draggable layout) */}

      {/* Draggable Layout Blocks */}
      {layoutLoaded ? (
        <div className="px-4 sm:px-0">
          <div className="hidden md:block text-[11px] mb-2" style={{ color: 'rgba(100,116,139,0.9)' }}>
            اسحب البلوكات من زر (⋮⋮) لترتيب الصفحة كما تريد — يتم الحفظ تلقائياً.
          </div>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleLayoutDragEnd}
          >
            <SortableContext items={layoutBlocks} strategy={verticalListSortingStrategy}>
              <div className="space-y-3" data-testid="vehicle-layout">
                {layoutBlocks.map((blockId) => (
                  <SortableBlock key={blockId} id={blockId} title={blockTitles[blockId] || blockId}>
                    {renderBlock(blockId)}
                  </SortableBlock>
                ))}
              </div>
            </SortableContext>
          </DndContext>
        </div>
      ) : (
        <div className="px-4 sm:px-0 text-xs" style={{ color: 'rgba(100,116,139,0.9)' }}>
          جاري تحميل التخطيط...
        </div>
      )}

      {/* Page-level WhatsApp Notification Banner */}
      {pageWhatsappNotification && (
        <div
          className="mx-4 sm:mx-0 mt-4 rounded-2xl px-4 py-3 animate-in fade-in slide-in-from-top-2"
          style={{
            background: 'rgba(16,185,129,0.12)',
            border: '1px solid rgba(16,185,129,0.28)',
            color: 'rgba(4,120,87,0.95)',
          }}
          data-testid="page-whatsapp-notification"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex-1">
              <div className="font-bold text-sm flex items-center gap-2 mb-1" style={{ color: 'rgba(4,120,87,0.95)' }}>
                <MessageCircle size={16} />
                إبلاغ العميل بجاهزية المركبة
              </div>
              <p className="text-xs" style={{ color: 'rgba(6,95,70,0.95)' }}>
                {pageWhatsappNotification.customerName} - اضغط لإرسال الإشعار عبر واتساب
              </p>
            </div>

            <div className="flex gap-2">
              <a
                href={pageWhatsappNotification.url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 text-xs font-bold rounded-xl transition-colors flex items-center gap-2"
                style={{
                  background: 'rgba(16,185,129,0.20)',
                  border: '1px solid rgba(16,185,129,0.36)',
                  color: 'rgba(4,120,87,0.95)',
                }}
                data-testid="page-whatsapp-send-button"
              >
                <MessageCircle size={14} /> إرسال واتساب
              </a>
              <button
                onClick={() => setPageWhatsappNotification(null)}
                className="px-2 py-2 rounded-xl transition-colors"
                style={{
                  background: 'rgba(255,255,255,0.8)',
                  border: '1px solid rgba(203,213,225,0.8)',
                  color: 'rgba(100,116,139,0.9)',
                }}
                title="إغلاق"
                data-testid="page-whatsapp-dismiss-button"
              >
                <X size={14} />
              </button>
            </div>
          </div>
        </div>
      )}


      {/* Modals */}
      {financialSourceOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" data-testid="vehicle-financial-source-modal-overlay">
          <div
            className="liquid-surface w-full max-w-3xl max-h-[85vh] overflow-hidden"
            style={{
              background: 'rgba(255,255,255,0.98)',
              border: '1px solid rgba(148,163,184,0.22)',
              borderRadius: 16,
            }}
            data-testid="vehicle-financial-source-modal"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'rgba(203,213,225,0.8)' }}>
              <h3 className="text-sm font-extrabold" style={{ color: 'rgba(15,23,42,0.95)' }} data-testid="vehicle-financial-source-title">
                {financialSourceTitle || 'مصدر الرقم'}
              </h3>
              <button
                onClick={() => setFinancialSourceOpen(false)}
                className="px-3 py-1.5 rounded-xl text-xs"
                style={{
                  background: 'rgba(255,255,255,0.96)',
                  border: '1px solid rgba(203,213,225,0.8)',
                  color: 'rgba(30,41,59,0.95)',
                }}
                data-testid="vehicle-financial-source-close"
              >
                إغلاق
              </button>
            </div>

            <div className="p-4 overflow-auto max-h-[70vh]" data-testid="vehicle-financial-source-content">
              {financialSourceRows.length === 0 ? (
                <div className="text-xs" style={{ color: 'rgba(100,116,139,0.9)' }} data-testid="vehicle-financial-source-empty">
                  لا توجد بيانات مصدر ضمن الفترة الحالية.
                </div>
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
                      {financialSourceRows.map((row, idx) => (
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
      )}

      {scannerOpen && (
        <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4">
          <div
            className="liquid-surface max-w-lg w-full p-4 relative"
            style={{
              background: 'rgba(255,255,255,0.98)',
              border: '1px solid rgba(203,213,225,0.8)',
            }}
            data-testid="scanner-modal"
          >
            <button
              onClick={closeScanner}
              className="absolute top-4 left-4 p-2 rounded-full"
              style={{
                background: 'rgba(255,255,255,0.96)',
                border: '1px solid rgba(203,213,225,0.8)',
                color: 'rgba(30,41,59,0.95)',
              }}
              data-testid="scanner-close-button"
            >
              <X size={20} />
            </button>
            <h3 className="text-lg font-bold mb-4 text-center" style={{ color: 'rgba(15,23,42,0.95)' }} data-testid="scanner-title">
              التقاط صورة
            </h3>
            {!capturedImage ? (
              <div className="relative aspect-video bg-black rounded-lg overflow-hidden mb-4">
                <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover" />
              </div>
            ) : (
              <div className="relative aspect-video bg-black rounded-lg overflow-hidden mb-4">
                <img src={capturedImage} alt="Captured" className="w-full h-full object-contain" data-testid="scanner-captured-image" />
              </div>
            )}
            <div className="flex gap-3">
              {!capturedImage ? (
                <button
                  onClick={captureImage}
                  className="flex-1 py-3 rounded-xl font-bold"
                  style={{
                    background: 'rgba(56,189,248,0.18)',
                    border: '1px solid rgba(56,189,248,0.32)',
                    color: 'rgba(3,105,161,0.95)',
                  }}
                  data-testid="scanner-capture-button"
                >
                  التقاط
                </button>
              ) : (
                <>
                  <button
                    onClick={() => setCapturedImage(null)}
                    className="flex-1 py-3 rounded-xl font-bold"
                    style={{
                      background: 'rgba(255,255,255,0.96)',
                      border: '1px solid rgba(203,213,225,0.8)',
                      color: 'rgba(30,41,59,0.95)',
                    }}
                    data-testid="scanner-retake-button"
                  >
                    إعادة
                  </button>
                  <button
                    onClick={uploadScannedImage}
                    className="flex-1 py-3 rounded-xl font-bold"
                    style={{
                      background: 'rgba(16,185,129,0.2)',
                      border: '1px solid rgba(16,185,129,0.32)',
                      color: 'rgba(4,120,87,0.95)',
                    }}
                    data-testid="scanner-save-button"
                  >
                    حفظ
                  </button>
                </>
              )}
            </div>
            <canvas ref={canvasRef} className="hidden" />
          </div>
        </div>
      )}

      {previewImage && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4"
          onClick={() => setPreviewImage(null)}
          data-testid="preview-overlay"
        >
          <button
            className="absolute top-4 left-4 p-2 rounded-full"
            style={{
              background: 'rgba(255,255,255,0.96)',
              border: '1px solid rgba(203,213,225,0.8)',
              color: 'rgba(15,23,42,0.95)',
            }}
            onClick={() => setPreviewImage(null)}
            data-testid="preview-close-button"
          >
            <X size={32} />
          </button>
          <img src={previewImage} alt="Preview" className="max-w-full max-h-[90vh] object-contain rounded-lg" onClick={e => e.stopPropagation()} />
        </div>
      )}

      {/* Disabled legacy duplicate layout removed */}

      <VisitDeleteConfirmDialog
        open={deleteVisitOpen}
        onOpenChange={(v) => {
          if (deleteVisitLoading) return;
          setDeleteVisitOpen(v);
          if (!v) setDeleteVisitTarget(null);
        }}
        visit={deleteVisitTarget}
        t={t}
        isRTL={isRTL}
        isLoading={deleteVisitLoading}
        onConfirm={confirmDeleteVisit}
      />

      <WhatsAppPreviewDialog
        open={waPreviewOpen}
        onOpenChange={setWaPreviewOpen}
        preview={waPreview}
        t={t}
        isRTL={isRTL}
      />

      <QuickPrintDialog
        open={printDialogOpen}
        title={printDialogConfig?.title || 'خيارات الطباعة'}
        description="معاينة تفاصيل الزيارة قبل الطباعة أو الإرسال"
        payloadBuilder={printDialogConfig?.payloadBuilder}
        initialPhone={printDialogConfig?.phone}
        onClose={() => setPrintDialogOpen(false)}
      />

    </div>
  );
};

export default VehicleDetails;