/**
 * Generate a unique, stable idempotency key for a payment/financial operation.
 *
 * Use this on the frontend BEFORE sending a financial POST request, so:
 * - Double-click submissions get deduped on the backend
 * - Retries after network errors don't create duplicate entries
 *
 * The key is short, URL-safe, and includes a per-operation prefix for traceability.
 *
 * Usage:
 *   const key = generateIdempotencyKey('confirm-payment', op.id);
 *   axios.post(url, payload, { headers: { 'Idempotency-Key': key } });
 *
 * After a successful response, the key is "spent" — subsequent identical calls
 * with the same key return the cached response (within 24h).
 */
export function generateIdempotencyKey(prefix = 'op', refId = '') {
  // crypto.randomUUID where available
  let uuid = '';
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      uuid = crypto.randomUUID();
    }
  } catch (e) {
    console.warn('crypto.randomUUID unavailable:', e);
  }
  if (!uuid) {
    uuid = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  }
  const safeRef = String(refId).replace(/[^A-Za-z0-9-]/g, '').slice(0, 16);
  return safeRef ? `${prefix}:${safeRef}:${uuid}` : `${prefix}:${uuid}`;
}
