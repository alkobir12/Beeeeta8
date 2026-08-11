/* global test, expect */
import { renderDocumentTemplate } from './documentTemplate';
import { getApprovedVisitFinancialContext } from './visitQuickPrint';

const TEMPLATE = `<!doctype html><html><body>
  <span data-field="total-sar"></span>
  <span data-field="payment-method"></span>
  <table><tbody id="items-body"></tbody></table>
  <template id="row-template"><tr><td data-field="row-desc"></td><td data-field="row-sum"></td></tr></template>
</body></html>`;

const visit = (id, finalTotal, paid) => ({
  id,
  notes: JSON.stringify({
    financial_finalization: {
      final_customer_total: finalTotal,
      finalized_at: '2026-08-11T00:00:00Z',
      accounting_identity: `visitfinal:${id}`,
    },
    payments: [{ id: `payment-${id}`, amount: paid, confirmed: true, status: 'confirmed' }],
  }),
});

test('selected visits keep independent approved totals and payments in QuickPrint', () => {
  const visitA = getApprovedVisitFinancialContext(visit('visit-a', 1200, 300));
  const visitB = getApprovedVisitFinancialContext(visit('visit-b', 800, 200));

  expect(visitA.final_customer_total).toBe(1200);
  expect(visitA.confirmed_paid).toBe(300);
  expect(visitB.final_customer_total).toBe(800);
  expect(visitB.confirmed_paid).toBe(200);

  const htmlA = renderDocumentTemplate(TEMPLATE, {
    doc_type: 'invoice',
    visit_id: visitA.visit_id,
    final_customer_total: visitA.final_customer_total,
    settings: { final_customer_total: visitA.final_customer_total, totals: { paid: visitA.confirmed_paid } },
    items: [
      { description: 'خدمة A', quantity: 1, price: 1000, total: 1000, itemType: 'service' },
      { description: 'مورد A', quantity: 1, price: 500, total: 500, itemType: 'supplier' },
    ],
  });
  const htmlB = renderDocumentTemplate(TEMPLATE, {
    doc_type: 'invoice',
    visit_id: visitB.visit_id,
    final_customer_total: visitB.final_customer_total,
    settings: { final_customer_total: visitB.final_customer_total, totals: { paid: visitB.confirmed_paid } },
    items: [{ description: 'خدمة B', quantity: 1, price: 700, total: 700, itemType: 'service' }],
  });

  expect(htmlA).toContain('1,200.00');
  expect(htmlA).not.toContain('مورد A');
  expect(htmlB).toContain('800.00');
  expect(htmlA).not.toContain('1,000.00</span>');
  expect(htmlB).not.toContain('700.00</span>');
});