import axios from 'axios';
import { API_BASE, resolveBackendBase } from '../utils/backendBase';

export { API_BASE, resolveBackendBase };

const api = axios.create({
  baseURL: API_BASE,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token && !config.headers?.Authorization) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});



const authAPI = {
  requestOtp: (phone) => axios.post(`${API_BASE}/auth/request-otp`, { phone }),
  verifyOtp: (payload) => axios.post(`${API_BASE}/auth/verify-otp`, payload),
};

const userAPI = {
  list: () => axios.get(`${API_BASE}/users`),
  create: (data) => axios.post(`${API_BASE}/users`, data),
  update: (id, data) => axios.put(`${API_BASE}/users/${id}`, data),
  remove: (id) => axios.delete(`${API_BASE}/users/${id}`)
};

const vehicleAPI = {
  getAll: () => axios.get(`${API_BASE}/vehicles`),
  getById: (id) => axios.get(`${API_BASE}/vehicles/${id}`),
  create: (data) => axios.post(`${API_BASE}/vehicles`, data),
  update: (id, data) => axios.put(`${API_BASE}/vehicles/${id}`, data),
  delete: (id) => axios.delete(`${API_BASE}/vehicles/${id}`),
  track: (trackingId) => axios.get(`${API_BASE}/vehicles/track/${trackingId}`),
  archiveSearch: (query, limit = 5) => api.get('/vehicles/archive-search', { params: { query, limit } }),
};

const vehicleFinanceAPI = {
  summary: (vehicleId) => axios.get(`${API_BASE}/vehicles/${vehicleId}/financial-summary`),
  confirmVisitPayment: (visitId, data) => api.post(`/finance-engine/visits/${visitId}/payments/confirm`, data),
};


export const visitAPI = {
  delete: (visitId) => api.delete(`/visits/${visitId}`),
};


const customerAPI = {
  getAll: (params = {}) => axios.get(`${API_BASE}/customers`, { params }),
  getById: (id) => axios.get(`${API_BASE}/customers/${id}`),
  create: (data) => axios.post(`${API_BASE}/customers`, data),
  update: (id, data) => axios.put(`${API_BASE}/customers/${id}`, data),
  delete: (id) => axios.delete(`${API_BASE}/customers/${id}`),
  getHistory: (id) => axios.get(`${API_BASE}/customers/${id}/history`),
  getApprovals: (id) => axios.get(`${API_BASE}/customers/${id}/approvals`),

};

const technicianAPI = {
  getAll: () => axios.get(`${API_BASE}/technicians`),
  getById: (id) => axios.get(`${API_BASE}/technicians/${id}`),
  create: (data) => axios.post(`${API_BASE}/technicians`, data),
  update: (id, data) => axios.put(`${API_BASE}/technicians/${id}`, data),
  delete: (id) => axios.delete(`${API_BASE}/technicians/${id}`)
};

const serviceAPI = {
  getAll: () => axios.get(`${API_BASE}/services`),
  getById: (id) => axios.get(`${API_BASE}/services/${id}`),
  create: (data) => axios.post(`${API_BASE}/services`, data),
  update: (id, data) => axios.put(`${API_BASE}/services/${id}`, data),
  delete: (id) => axios.delete(`${API_BASE}/services/${id}`)
};

const aiAPI = {
  // مساعد الذكاء الشامل (RAG + Claude)
  chat: (data) => axios.post(`${API_BASE}/ai/enhanced-chat`, data),
  searchSolutions: (query) => axios.get(`${API_BASE}/ai/search-solutions`, { params: { query } }),

  // مساعد الورشة المتخصص (CarWorkshopAI + Genspark)
  workshopInfo: () => axios.get(`${API_BASE}/ai/workshop/info`),
  workshopDiagnose: (payload) => axios.post(`${API_BASE}/ai/workshop/diagnose`, payload),
  workshopSearchTechnical: (payload) => axios.post(`${API_BASE}/ai/workshop/search-technical`, payload),
  workshopAppointment: (payload) => axios.post(`${API_BASE}/ai/workshop/appointment`, payload),
  workshopServiceReport: (payload) => axios.post(`${API_BASE}/ai/workshop/service-report`, payload),

  // التحليل المالي بالذكاء الاصطناعي (قديم - يعتمد على خدمة منفصلة)
  financialAnalysis: (payload) => api.post('/ai/financial-analysis', payload),

  // البوت المالي الجديد (GPT-5.1 عبر EMERGENT_LLM_KEY)
  financeBotChat: (payload) => api.post('/finance-bot/chat', payload),

  // AlKabeer Bot (Abu Fahad - Customer Service)
  alkabeerChat: (payload) => api.post('/alkabeer-bot/chat', payload),
};

const partAPI = {
  getAll: () => axios.get(`${API_BASE}/parts`),
  getById: (id) => axios.get(`${API_BASE}/parts/${id}`),
  create: (data) => axios.post(`${API_BASE}/parts`, data),
  update: (id, data) => axios.put(`${API_BASE}/parts/${id}`, data),
  delete: (id) => axios.delete(`${API_BASE}/parts/${id}`)
};

const supplierAPI = {
  getAll: (params = {}) => axios.get(`${API_BASE}/suppliers`, { params }),
  create: (data) => axios.post(`${API_BASE}/suppliers`, data),
  update: (id, data) => axios.put(`${API_BASE}/suppliers/${id}`, data),
  delete: (id) => axios.delete(`${API_BASE}/suppliers/${id}`),
};

const fileAPI = {
  upload: (formData) => axios.post(`${API_BASE}/files/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
};

const statsAPI = {
  getStats: () => axios.get(`${API_BASE}/stats`),
};

const transactionAPI = {
  getAll: () => axios.get(`${API_BASE}/transactions`),
  create: (data) => axios.post(`${API_BASE}/transactions`, data)
};

const operationsAPI = {
  list: (params) => axios.get(`${API_BASE}/operations`, { params }),
  create: (data) => axios.post(`${API_BASE}/operations`, data),
};

const financeAPI = {
  getIncomeStatement: (params) => api.get('/finance/reports/income-statement', { params }),
  getBalanceSheet: (params) => api.get('/finance/reports/balance-sheet', { params }),
  getCashFlow: (params) => api.get('/finance/reports/cash-flow', { params }),
  getTrialBalance: (params) => api.get('/finance/reports/trial-balance', { params }),
  getReconciliation: (params) => api.get('/finance/reports/reconciliation', { params }),
  getOperationTrace: (params) => api.get('/finance/reports/operation-trace', { params }),
  getAccountTreeDetails: (params) => api.get('/finance/reports/account-tree-details', { params }),
  reclassifyPaymentAccounts: (params) => api.post('/finance/reports/reclassify-payment-accounts', null, { params }),
  getBudgets: (params) => api.get('/finance/budgets', { params }),
  createBudget: (data) => api.post('/finance/budgets', data),
  updateBudget: (id, data) => api.put(`/finance/budgets/${id}`, data),
  deleteBudget: (id, params) => api.delete(`/finance/budgets/${id}`, { params }),

  // AR (Receivables)
  getARCustomers: (params) => api.get('/finance/ar/customers', { params }),
  getARLedger: (params) => api.get('/finance/ar/ledger', { params }),
  exportARLedgerExcel: (params) => api.get('/finance/ar/ledger/export', { params, responseType: 'blob' }),
  getARCustomerStatement: (params) => api.get('/finance/ar/customer-statement', { params }),
  getARAging: (params) => api.get('/finance/ar/aging', { params }),
  getARTurnover: (params) => api.get('/finance/ar/turnover', { params }),
  getBulkDeleteAuditLogs: (params) => api.get('/finance/audit-logs', { params }),

  getInvoices: (params) => api.get('/invoices', { params }),
  createInvoice: (data) => api.post('/invoices', data),
  updateInvoice: (id, data) => api.put(`/invoices/${id}`, data),
  getJournalEntries: (params) => api.get('/finance/journal-entries', { params }),
  createJournalEntry: (data) =>
    api.post('/finance/journal-entries', data, {
      params: { workshop_id: process.env.REACT_APP_WORKSHOP_ID },
    }),
  getChartOfAccounts: () =>
    api.get('/finance/chart-of-accounts', {
      params: { workshop_id: process.env.REACT_APP_WORKSHOP_ID },
    }),
  getOperations: (params) => api.get('/finance/operations', { params }),
  getAlerts: (params) => api.get('/finance/alerts', { params }),
  closePeriod: (workshop_id, data) => api.post('/finance/period-close', data, { params: { workshop_id } }),
  getLastClose: (workshop_id) => api.get('/finance/period-close/last', { params: { workshop_id } }),

};

export { 
  authAPI, 
  userAPI, 
  vehicleAPI, 
  customerAPI, 
  technicianAPI, 
  serviceAPI, 
  aiAPI, 
  partAPI, 
  supplierAPI,
  fileAPI, 
  statsAPI, 
  transactionAPI,
  operationsAPI,
  financeAPI,
  vehicleFinanceAPI,
  api,
};

export default { 
  auth: authAPI, 
  user: userAPI, 
  vehicle: vehicleAPI, 
  customer: customerAPI, 
  technician: technicianAPI, 
  service: serviceAPI, 
  ai: aiAPI, 
  part: partAPI, 
  supplier: supplierAPI,
  file: fileAPI, 
  stats: statsAPI, 
  transaction: transactionAPI 
};
