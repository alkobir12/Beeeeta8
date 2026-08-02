import { assertTemplateComplete } from './documentTemplate';

const standalonePrintCss = `
  <style id="standalone-print-css">
    @page { size: A4 portrait; margin: 10mm; }
    * { box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
    html, body { margin: 0 !important; padding: 0 !important; background: #ffffff !important; direction: rtl; }
    body { width: 100% !important; min-height: auto !important; display: block !important; overflow: visible !important; }
    button, .pbtn, [data-testid="quick-print-output-actions"], [data-testid="document-shell-header"], .doc-shell-header, .doc-editor, .doc-preview-toolbar { display: none !important; }
    .page, [data-testid="document-a4-page"] { width: 210mm !important; min-height: 297mm !important; margin: 0 auto !important; box-shadow: none !important; overflow: visible !important; page-break-after: always; }
    .sheet, [data-testid="document-a4-sheet"] { width: 190mm !important; margin: 0 auto !important; }
    table { page-break-inside: auto; }
    thead { display: table-header-group; }
    tr, .card, .diag, .foot, .strip, .sign, .sbox { break-inside: avoid; page-break-inside: avoid; }
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