/* global test, expect */
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '..', 'JournalEntryCard.jsx'), 'utf8');

test('journal card shows creator tag on card face', () => {
  expect(src).toContain('journal-card-creator-tag-');
  expect(src).toContain('CREATOR_PILL_STYLES');
  expect(src).toContain('origin.creator_label');
});

test('journal card expanded details include full origin block (من فعل هذا؟)', () => {
  [
    'journal-card-origin-',
    'journal-card-origin-creator-',
    'journal-card-origin-approver-',
    'journal-card-origin-poster-',
    'journal-card-origin-channel-',
  ].forEach((needle) => expect(src).toContain(needle));
  expect(src).toContain('من فعل هذا؟');
  expect(src).toContain('المنشئ');
  expect(src).toContain('المعتمِد');
  expect(src).toContain('مُرحِّل القيد');
  expect(src).toContain('قناة الإدخال');
});

test('journal card hides origin block when resolve failed (no raw errors in UI)', () => {
  expect(src).toContain('!entry.origin.error');
});
