/* global test, expect */
const fs = require('fs');
const path = require('path');

const controlPath = path.join(__dirname, '..', 'ControlCenterTab.jsx');
const drawerPath = path.join(__dirname, '..', 'UnifiedAssistantDrawer.jsx');

test('katrina control center exposes required provenance fields and no test artifact approval path', () => {
  const src = fs.readFileSync(controlPath, 'utf8');
  [
    'approval-action-type-',
    'approval-amount-',
    'approval-entity-',
    'approval-vehicle-',
    'approval-requested-by-',
    'approval-requested-at-',
    'approval-entry-channel-',
    'approval-payment-method-',
    'approval-source-reference-',
    'approval-description-',
    'approval-expected-impact-',
    'approval-open-source-',
  ].forEach((needle) => expect(src).toContain(needle));
  expect(src).toContain("source === 'TEST_ARTIFACT'");
  expect(src).toContain('disabled={busy || actionDisabled}');
  expect(src).toContain('مسودة جديدة');
  expect(src).toContain('عملية جديدة: لا تتطلب سجلاً سابقاً قبل الاعتماد.');
});

test('assistant drawer has four mobile-first Katrina tabs', () => {
  const src = fs.readFileSync(drawerPath, 'utf8');
  expect(src).toContain("id: 'approvals'");
  expect(src).toContain("label: 'يحتاج قرارك'");
  expect(src).toContain("id: 'findings'");
  expect(src).toContain("label: 'اكتشفته كاترينا'");
  expect(src).toContain("id: 'executions'");
  expect(src).toContain("label: 'تم بواسطة كاترينا'");
  expect(src).toContain("id: 'chat'");
  expect(src).toContain("label: 'المحادثة'");
  expect(src).toContain('max-w-[480px]');
  expect(src).toContain("height: '90dvh'");
});
