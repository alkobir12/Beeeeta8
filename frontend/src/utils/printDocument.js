import { assertTemplateComplete } from './documentTemplate';

const standalonePrintCss = `
  <style id="standalone-print-css">
    @page { size: A4 portrait; margin: 10mm; }
    button, .pbtn, [data-testid="quick-print-output-actions"], [data-testid="document-shell-header"], .doc-shell-header, .doc-editor, .doc-preview-toolbar { display: none !important; }
    @media print {
      .crow, .diag-b, .foot, .sign { display: table !important; width: 100% !important; table-layout: fixed !important; }
      .crow > div, .diag-b > div, .foot > div, .sign > div { display: table-cell !important; }
      .sheet { width: auto !important; }
      tbody tr, .diag, .sbox { break-inside: avoid !important; page-break-inside: avoid !important; }
      thead { display: table-header-group !important; }
    }
  </style>
`;

export const toStandalonePrintHtml = (htmlContent = '', title = 'مستند') => {
  const source = String(htmlContent || '');
  assertTemplateComplete(source);
  const parser = new DOMParser();
  const doc = parser.parseFromString(source, 'text/html');
  doc.querySelectorAll('button, script, .pbtn, [data-print-exclude="true"]').forEach((node) => node.remove());
  if (!doc.querySelector('base')) {
    const base = doc.createElement('base');
    base.href = window.location.origin;
    doc.head.prepend(base);
  }
  if (!doc.querySelector('meta[name="viewport"]')) {
    const viewport = doc.createElement('meta');
    viewport.setAttribute('name', 'viewport');
    viewport.setAttribute('content', 'width=device-width, initial-scale=1');
    doc.head.appendChild(viewport);
  }
  const titleNode = doc.querySelector('title') || doc.createElement('title');
  titleNode.textContent = title;
  if (!titleNode.parentNode) doc.head.appendChild(titleNode);
  if (!doc.getElementById('standalone-print-css')) {
    doc.head.insertAdjacentHTML('beforeend', standalonePrintCss);
  }
  doc.documentElement.setAttribute('lang', 'ar');
  doc.documentElement.setAttribute('dir', 'rtl');
  return `<!doctype html>${doc.documentElement.outerHTML}`;
};

export const printHtmlDocument = (htmlContent = '', title = 'مستند') => {
  const standaloneHtml = toStandalonePrintHtml(htmlContent, title);
  const printWindow = window.open('', '_blank');
  if (!printWindow) throw new Error('تعذر فتح نافذة الطباعة. اسمح بالنوافذ المنبثقة ثم حاول مرة أخرى.');
  printWindow.document.open();
  printWindow.document.write(standaloneHtml);
  printWindow.document.close();
  const runPrint = () => {
    try {
      printWindow.focus();
      printWindow.print();
    } catch (error) {
      throw error;
    }
  };
  if (printWindow.document.readyState === 'complete') {
    window.setTimeout(runPrint, 250);
  } else {
    printWindow.addEventListener('load', () => window.setTimeout(runPrint, 250), { once: true });
  }
  return true;
};