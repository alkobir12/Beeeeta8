/**
 * 🛠️ Operation Card Helpers
 * Reusable utilities extracted from OperationCard.jsx to reduce file size and aid testing.
 */

/**
 * Clean up operation notes by removing internal markers.
 * Strips: [TAGS], PARTY_TYPE:, SOURCE:, VEHICLE_REF:, ACCOUNT_CODE:, ACCOUNTING_TARGET:
 */
export const cleanNotes = (notes) => {
  if (!notes) return '';
  return String(notes)
    .replace(/\[.*?\]/g, '')
    .replace(/PARTY_TYPE:\s*\S+/g, '')
    .replace(/SOURCE:\s*\S+/g, '')
    .replace(/VEHICLE_REF:\s*\S+/g, '')
    .replace(/ACCOUNT_CODE:\s*\S+/g, '')
    .replace(/ACCOUNTING_TARGET:\s*[^\n]+/g, '')
    .replace(/\s+/g, ' ')
    .trim();
};

/** Stop click propagation safely (used to keep card-wide expand toggle from firing on buttons). */
export const stopEvent = (e) => {
  if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
};

/** Map an operation type code to its Arabic display label (fallback to the code). */
export const getOperationTypeLabel = (type, labels = {}) => {
  return labels[type] || type || '-';
};

/** Round-2 helper for currency display. */
export const round2 = (v) => {
  const n = Number(v || 0);
  if (!isFinite(n)) return 0;
  return Math.round(n * 100) / 100;
};
