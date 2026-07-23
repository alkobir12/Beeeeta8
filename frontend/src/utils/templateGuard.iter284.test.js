jest.mock('html2canvas', () => jest.fn(() => Promise.resolve({})));

jest.mock('jspdf', () => {
  return jest.fn().mockImplementation(() => ({
    internal: { pageSize: { getWidth: () => 210, getHeight: () => 297 } },
    addImage: jest.fn(),
    addPage: jest.fn(),
    output: jest.fn(() => 'data:application/pdf;base64,AAA='),
    save: jest.fn(),
  }));
});

import {
  assertTemplateComplete,
  findUnresolvedTemplateVariables,
} from './documentTemplate';
import { downloadPDF, renderPdfAssets } from './pdfGenerator';

describe('Template completeness guard (Iter284)', () => {
  test('findUnresolvedTemplateVariables extracts mixed placeholder styles', () => {
    const html = `
      <div>{CUSTOMER_NAME}</div>
      <div>[[TOTAL]]</div>
      <div><%= INVOICE_NO %></div>
      <div>{{DATE}}</div>
    `;

    const variables = findUnresolvedTemplateVariables(html);

    expect(variables).toEqual(expect.arrayContaining(['CUSTOMER_NAME', 'TOTAL', 'INVOICE_NO', 'DATE']));
  });

  test('assertTemplateComplete throws template_incomplete with variables list', () => {
    const html = '<p>{CUSTOMER_NAME}</p><p>[[TOTAL]]</p><p><%= INVOICE_NO %></p>';

    try {
      assertTemplateComplete(html);
      throw new Error('Expected assertTemplateComplete to throw');
    } catch (error) {
      expect(error.code).toBe('template_incomplete');
      expect(error.variables).toEqual(expect.arrayContaining(['CUSTOMER_NAME', 'TOTAL', 'INVOICE_NO']));
      expect(error.message).toContain('المتغيرات الناقصة');
    }
  });

  test('downloadPDF rejects unresolved placeholders before rendering canvas', async () => {
    const fakeElement = { innerHTML: '<div>{CUSTOMER_NAME}</div><div>[[TOTAL]]</div><div><%= INVOICE_NO %></div>' };
    await expect(downloadPDF(fakeElement, 'x.pdf')).rejects.toMatchObject({
      code: 'template_incomplete',
    });
  });

  test('renderPdfAssets rejects unresolved placeholders before rendering canvas', async () => {
    const fakeElement = { innerHTML: '<div>{CUSTOMER_NAME}</div><div>[[TOTAL]]</div><div><%= INVOICE_NO %></div>' };
    await expect(renderPdfAssets(fakeElement)).rejects.toMatchObject({
      code: 'template_incomplete',
    });
  });
});
