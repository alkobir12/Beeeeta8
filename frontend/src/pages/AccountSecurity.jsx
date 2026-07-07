import React from 'react';
import SecuritySettings from '../components/SecuritySettings';

export default function AccountSecurity() {
  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4" data-testid="account-security-page">
      <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
        🔐 أمان الحساب
      </h1>
      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
        عيّن كلمة مرور لحسابك وفعّل الدخول السريع بـ PIN على هذا الجهاز — متاح لجميع المستخدمين.
      </p>
      <SecuritySettings />
    </div>
  );
}
