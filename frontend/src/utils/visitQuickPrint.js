export const parseVisitNotes = (visit = {}) => {
  if (visit?.notes && typeof visit.notes === 'object') return visit.notes;
  if (typeof visit?.notes === 'string' && visit.notes.trim().startsWith('{')) {
    try { return JSON.parse(visit.notes); } catch (error) { return {}; }
  }
  return {};
};

export const getApprovedVisitFinancialContext = (visit = {}) => {
  const parsed = parseVisitNotes(visit);
  const finalization = parsed?.financial_finalization && typeof parsed.financial_finalization === 'object'
    ? parsed.financial_finalization
    : {};
  const rawTotal = finalization.final_customer_total ?? visit?.final_customer_total ?? visit?.finalCustomerTotal;
  const finalTotal = Number(rawTotal);
  const payments = Array.isArray(parsed?.payments) ? parsed.payments : [];
  const confirmedPaid = payments
    .filter((payment) => payment?.confirmed !== false && !['pending', 'pending_confirmation', 'unconfirmed'].includes(String(payment?.status || '').toLowerCase()))
    .reduce((sum, payment) => sum + Number(payment?.amount || 0), 0);
  return {
    ...finalization,
    visit_id: visit?.id,
    final_customer_total: Number.isFinite(finalTotal) ? finalTotal : null,
    confirmed_paid: confirmedPaid,
    payments,
  };
};