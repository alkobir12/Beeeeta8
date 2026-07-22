import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';

const waitForStableLayout = async (element) => {
  if (document?.fonts?.ready) {
    await document.fonts.ready.catch(() => null);
  }
  const images = Array.from(element.querySelectorAll('img'));
  await Promise.all(images.map((img) => {
    if (img.complete) return Promise.resolve();
    return new Promise((resolve) => {
      img.onload = resolve;
      img.onerror = resolve;
    });
  }));
  await new Promise((r) => setTimeout(r, 60));
};

const elementToCanvas = async (element, options = {}) => {
  const scale = options.scale || 2;
  const backgroundColor = options.backgroundColor ?? '#ffffff';
  await waitForStableLayout(element);

  const rect = element.getBoundingClientRect();
  const width = Math.ceil(element.scrollWidth || rect.width || 794);
  const height = Math.ceil(element.scrollHeight || rect.height || 1123);

  return html2canvas(element, {
    scale,
    useCORS: true,
    allowTaint: true,
    logging: false,
    backgroundColor,
    width,
    height,
    windowWidth: Math.max(width, 794),
    windowHeight: Math.max(height, 1123),
    scrollX: 0,
    scrollY: 0,
    onclone: (clonedDocument) => {
      const style = clonedDocument.createElement('style');
      style.textContent = `
        * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        body { margin: 0 !important; background: ${backgroundColor} !important; }
        img { max-width: 100%; }
      `;
      clonedDocument.head.appendChild(style);
    },
  });
};

const canvasToPdf = (canvas, format = 'a4') => {
  const pdf = new jsPDF('p', 'mm', format);
  const pdfWidth = pdf.internal.pageSize.getWidth();
  const pdfHeight = pdf.internal.pageSize.getHeight();

  const imgWidth = pdfWidth;
  const imgHeight = (canvas.height * imgWidth) / canvas.width;

  // PNG preserves colors/fonts better than JPEG.
  const imgData = canvas.toDataURL('image/png');

  let heightLeft = imgHeight;
  let position = 0;

  pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
  heightLeft -= pdfHeight;

  while (heightLeft > 0) {
    position = heightLeft - imgHeight;
    pdf.addPage();
    pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
    heightLeft -= pdfHeight;
  }
  return pdf;
};

const canvasToPreviewCanvas = (canvas, maxWidth = 900) => {
  if (canvas.width <= maxWidth) return canvas;
  const ratio = maxWidth / canvas.width;
  const preview = document.createElement('canvas');
  preview.width = maxWidth;
  preview.height = Math.round(canvas.height * ratio);
  const ctx = preview.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, preview.width, preview.height);
  ctx.drawImage(canvas, 0, 0, preview.width, preview.height);
  return preview;
};

/**
 * Downloads a DOM element as a high-quality A4 PDF.
 */
export const downloadPDF = async (
  element,
  fileName = 'document.pdf',
  options = {}
) => {
  if (!element) return;
  try {
    const canvas = await elementToCanvas(element, options);
    const pdf = canvasToPdf(canvas, options.format || 'a4');
    const safeName = String(fileName || 'document.pdf').toLowerCase().endsWith('.pdf') ? fileName : `${fileName}.pdf`;
    pdf.save(safeName);
    return true;
  } catch (error) {
    console.error('PDF Generation Error:', error);
    throw error;
  }
};

/**
 * Renders PDF + preview image assets (blobs & base64) without downloading.
 * Used by the unified "PDF وواتساب" share flow.
 */
export const renderPdfAssets = async (element, options = {}) => {
  if (!element) throw new Error('missing-element');
  const canvas = await elementToCanvas(element, options);
  const pdf = canvasToPdf(canvas, options.format || 'a4');
  const pdfBlob = pdf.output('blob');
  const pdfBase64 = pdf.output('datauristring').split(',')[1];

  const previewCanvas = canvasToPreviewCanvas(canvas, options.previewMaxWidth || 900);
  const imageDataUrl = previewCanvas.toDataURL('image/jpeg', 0.82);
  const imageBase64 = imageDataUrl.split(',')[1];
  const imageBlob = await new Promise((resolve) => previewCanvas.toBlob(resolve, 'image/jpeg', 0.82));

  return { pdfBlob, pdfBase64, imageBlob, imageBase64, imageDataUrl };
};
