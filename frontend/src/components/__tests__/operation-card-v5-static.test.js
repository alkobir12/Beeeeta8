/* global test, expect */
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '..', 'OperationCard.jsx'), 'utf8');

test('operation card uses V5 mobile reference structure', () => {
  [
    'operation-card-v5-main',
    'operation-card-payment-summary-',
    'operation-card-finance-split-',
    'operation-card-quick-section-',
    'operation-card-full-details-toggle-',
    'operation-card-customer-items-table-',
    'operation-card-supplier-items-',
    'operation-card-payment-history-',
    'operation-card-journal-entry-box-',
    'operation-card-more-actions-',
    'operation-card-more-menu-',
  ].forEach((needle) => expect(src).toContain(needle));
  expect(src).toContain('مشتريات الموردين مستقلة عن ذمة العميل');
  expect(src).toContain('لا يدخل في ذمة العميل');
});

test('operation card keeps only primary collection action always visible and moves other actions to more menu', () => {
  expect(src).toContain('operation-card-confirm-credit-payment-');
  expect(src).toContain('operation-card-edit-');
  expect(src).toContain('operation-card-print-');
  expect(src).toContain('operation-card-delete-');
  expect(src).toContain('operation-card-view-vehicle-');
  expect(src).toContain('min-h-[48px]');
});
