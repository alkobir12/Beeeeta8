/* global describe, test, expect */
import { findUnresolvedTemplateVariables, renderDocumentTemplate } from './documentTemplate';

describe('Iter285 CUSTOMER_NAME no-silent-fallback regression', () => {
  test('renderDocumentTemplate keeps {CUSTOMER_NAME} unresolved when customer.name is missing', () => {
    const template = '<p>العميل: {CUSTOMER_NAME}</p><p>التاريخ: {DATE}</p>';
    const payload = {
      customer: { name: '' },
      settings: { date: '2026-02-01' },
      items: [{ description: 'خدمة', quantity: 1, unit_price: 100 }],
    };
    const workshop = { name: 'ورشة اختبار' };

    const rendered = renderDocumentTemplate(template, payload, workshop);
    const unresolved = findUnresolvedTemplateVariables(rendered);

    expect(rendered).toContain('{CUSTOMER_NAME}');
    expect(unresolved).toEqual(expect.arrayContaining(['CUSTOMER_NAME']));
  });
});
