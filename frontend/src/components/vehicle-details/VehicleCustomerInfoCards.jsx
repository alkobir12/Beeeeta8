import React from 'react';
import { Car, Edit2, User, X } from 'lucide-react';

const cardStyle = {
  borderRadius: 20,
  padding: 14,
  background: 'radial-gradient(circle at 12% 18%, rgba(248,250,252,0.98), rgba(241,245,249,0.96))',
  border: '1px solid rgba(203,213,225,0.8)',
};

const inputStyle = {
  background: 'rgba(255,255,255,0.8)',
  border: '1px solid rgba(203,213,225,0.8)',
  color: 'rgba(15,23,42,0.92)',
};

const buttonStyle = {
  background: 'rgba(255,255,255,0.8)',
  border: '1px solid rgba(203,213,225,0.8)',
  color: 'rgba(71,85,105,0.9)',
};

const InfoRow = ({ label, children, last = false }) => (
  <div className="flex flex-col py-2" style={last ? {} : { borderBottom: '1px solid rgba(203,213,225,0.8)' }}>
    <span className="text-[11px] mb-1" style={{ color: 'rgba(100,116,139,0.9)' }}>{label}</span>
    {children}
  </div>
);

const ValueText = ({ children, testId, className = '', ...props }) => (
  <span className={`text-sm font-semibold ${className}`} style={{ color: 'rgba(15,23,42,0.92)' }} data-testid={testId} {...props}>
    {children}
  </span>
);

const TextInput = ({ value, onChange, testId, placeholder = '', className = 'w-full' }) => (
  <input
    className={`${className} text-sm rounded-xl px-3 py-2`}
    style={inputStyle}
    value={value || ''}
    onChange={(event) => onChange(event.target.value)}
    placeholder={placeholder}
    data-testid={testId}
  />
);

export const VehicleInfoCard = ({
  t,
  vehicle,
  vehicleForm,
  setVehicleForm,
  isEditingVehicle,
  setIsEditingVehicle,
  isVehicleInfoCollapsed,
  setIsVehicleInfoCollapsed,
  onSave,
}) => (
  <div className="liquid-surface relative" data-testid="vehicle-info-card" style={cardStyle}>
    <div className="flex items-center justify-between gap-2 mb-3">
      <div className="flex items-center gap-2 min-w-0" style={{ color: 'rgba(3,105,161,0.95)' }}>
        <Car size={18} />
        <h3 className="text-sm font-extrabold whitespace-nowrap" style={{ color: 'rgba(15,23,42,0.95)' }}>
          {t('vehicle_details.vehicle_info')}
        </h3>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          onClick={() => setIsVehicleInfoCollapsed((value) => !value)}
          className="px-3 py-1.5 rounded-xl text-xs"
          style={buttonStyle}
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
          style={buttonStyle}
          data-testid="vehicle-edit-toggle"
        >
          {isEditingVehicle ? <X size={16} /> : <Edit2 size={16} />}
        </button>
      </div>
    </div>

    {(!isVehicleInfoCollapsed || isEditingVehicle) ? (
      <div className="space-y-3" data-testid="vehicle-info-content">
        <InfoRow label={t('vehicles.plate_number')}>
          {isEditingVehicle ? (
            <TextInput value={vehicleForm.plateNumber} onChange={(value) => setVehicleForm({ ...vehicleForm, plateNumber: value })} testId="vehicle-plate-input" />
          ) : <ValueText testId="vehicle-plate-value">{vehicle.plateNumber}</ValueText>}
        </InfoRow>

        <InfoRow label={t('vehicle_details.brand_model')}>
          {isEditingVehicle ? (
            <div className="flex gap-2">
              <TextInput value={vehicleForm.brand} onChange={(value) => setVehicleForm({ ...vehicleForm, brand: value })} testId="vehicle-brand-input" placeholder="الماركة" className="w-1/2" />
              <TextInput value={vehicleForm.model} onChange={(value) => setVehicleForm({ ...vehicleForm, model: value })} testId="vehicle-model-input" placeholder="الموديل" className="w-1/2" />
            </div>
          ) : <ValueText testId="vehicle-brand-model-value">{vehicle.brand} {vehicle.model}</ValueText>}
        </InfoRow>

        <InfoRow label={t('vehicle_details.vin_number')}>
          {isEditingVehicle ? (
            <TextInput value={vehicleForm.vin} onChange={(value) => setVehicleForm({ ...vehicleForm, vin: value })} testId="vehicle-vin-input" />
          ) : <ValueText testId="vehicle-vin-value" className="font-mono">{vehicle.vin || '-'}</ValueText>}
        </InfoRow>

        <InfoRow label="رقم ملف المركبة">
          {isEditingVehicle ? (
            <TextInput value={vehicleForm.fileNumber} onChange={(value) => setVehicleForm({ ...vehicleForm, fileNumber: value })} testId="vehicle-file-number-input" />
          ) : <span className="text-sm font-semibold" style={{ color: 'rgba(3,105,161,0.95)' }} data-testid="vehicle-file-number-value">{vehicle.fileNumber || '-'}</span>}
        </InfoRow>

        <InfoRow label={t('vehicle_details.color')} last>
          {isEditingVehicle ? (
            <TextInput value={vehicleForm.color} onChange={(value) => setVehicleForm({ ...vehicleForm, color: value })} testId="vehicle-color-input" />
          ) : <ValueText testId="vehicle-color-value">{vehicle.color || '-'}</ValueText>}
        </InfoRow>

        {isEditingVehicle && (
          <button
            onClick={onSave}
            className="w-full rounded-2xl px-4 py-3 text-sm font-extrabold mt-2"
            style={{ background: 'rgba(56,189,248,0.14)', border: '1px solid rgba(56,189,248,0.28)', color: 'rgba(3,105,161,0.95)' }}
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
);

export const CustomerInfoCard = ({
  t,
  vehicle,
  customerForm,
  setCustomerForm,
  isEditingCustomer,
  setIsEditingCustomer,
  isCustomerInfoCollapsed,
  setIsCustomerInfoCollapsed,
  onSave,
}) => (
  <div className="liquid-surface relative" data-testid="customer-info-card" style={cardStyle}>
    <div className="flex items-center justify-between gap-2 mb-3">
      <div className="flex items-center gap-2 min-w-0" style={{ color: 'rgba(4,120,87,0.95)' }}>
        <User size={18} />
        <h3 className="text-sm font-extrabold whitespace-nowrap" style={{ color: 'rgba(15,23,42,0.95)' }}>
          {t('vehicle_details.customer_info')}
        </h3>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          onClick={() => setIsCustomerInfoCollapsed((value) => !value)}
          className="px-3 py-1.5 rounded-xl text-xs"
          style={buttonStyle}
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
          style={buttonStyle}
          data-testid="customer-edit-toggle"
        >
          {isEditingCustomer ? <X size={16} /> : <Edit2 size={16} />}
        </button>
      </div>
    </div>

    {(!isCustomerInfoCollapsed || isEditingCustomer) ? (
      <div className="space-y-3" data-testid="customer-info-content">
        <InfoRow label={t('vehicles_page.customer_name')}>
          {isEditingCustomer ? (
            <TextInput value={customerForm.name} onChange={(value) => setCustomerForm({ ...customerForm, name: value })} testId="customer-name-input" />
          ) : <ValueText testId="customer-name-value">{vehicle.customerName}</ValueText>}
        </InfoRow>

        <InfoRow label="رقم الجوال">
          {isEditingCustomer ? (
            <TextInput value={customerForm.phone} onChange={(value) => setCustomerForm({ ...customerForm, phone: value })} testId="customer-phone-input" />
          ) : <ValueText testId="customer-phone-value" className="" dir="ltr">{vehicle.customerPhone}</ValueText>}
        </InfoRow>

        <InfoRow label="رقم ملف المركبة">
          <span className="text-sm font-semibold" style={{ color: 'rgba(3,105,161,0.95)' }} data-testid="customer-file-number-value">
            {vehicle.fileNumber || '-'}
          </span>
        </InfoRow>

        <InfoRow label="رقم ملف العميل المرتبط">
          {isEditingCustomer ? (
            <TextInput value={customerForm.fileNumber} onChange={(value) => setCustomerForm({ ...customerForm, fileNumber: value })} testId="customer-file-number-input" />
          ) : <span className="text-sm font-semibold" style={{ color: 'rgba(4,120,87,0.95)' }} data-testid="customer-linked-file-number-value">{vehicle.customerFileNumber || '-'}</span>}
        </InfoRow>

        <InfoRow label="البريد الإلكتروني" last>
          {isEditingCustomer ? (
            <TextInput value={customerForm.email} onChange={(value) => setCustomerForm({ ...customerForm, email: value })} testId="customer-email-input" />
          ) : <ValueText testId="customer-email-value">{vehicle.customerEmail || '-'}</ValueText>}
        </InfoRow>

        {isEditingCustomer && (
          <button
            onClick={onSave}
            className="w-full rounded-2xl px-4 py-3 text-sm font-extrabold mt-2"
            style={{ background: 'rgba(16,185,129,0.14)', border: '1px solid rgba(16,185,129,0.28)', color: 'rgba(4,120,87,0.95)' }}
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
);

export const VehicleCustomerInfoCards = ({ onSaveVehicle, onSaveCustomer, ...props }) => (
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3" data-testid="vehicle-info-block">
    <VehicleInfoCard {...props} onSave={onSaveVehicle} />
    <CustomerInfoCard {...props} onSave={onSaveCustomer} />
  </div>
);