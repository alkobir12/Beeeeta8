import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';

/**
 * Downloads a DOM element as a high-quality A4 PDF.
 * Goal: match on-screen design as closely as possible.
 */
export const downloadPDF = async (
  element,
  fileName = 'document.pdf',
  options = {}
) => {
  if (!element) return;

  const scale = options.scale || 2;
  const format = options.format || 'a4';
  const backgroundColor = options.backgroundColor ?? '#ffffff';

  try {
    // Ensure layout, web fonts, and embedded images are stable before snapshot.
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

    const rect = element.getBoundingClientRect();
    const width = Math.ceil(element.scrollWidth || rect.width || 794);
    const height = Math.ceil(element.scrollHeight || rect.height || 1123);

    const canvas = await html2canvas(element, {
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

    const safeName = String(fileName || 'document.pdf').toLowerCase().endsWith('.pdf') ? fileName : `${fileName}.pdf`;
    pdf.save(safeName);
    return true;
  } catch (error) {
    console.error('PDF Generation Error:', error);
    throw error;
  }
};
