const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

function buildQueryString(params = {}) {
  const cleanParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '' && value !== 'undefined' && value !== 'null' && value !== 'All') {
      cleanParams.append(key, value);
    }
  }
  const str = cleanParams.toString();
  return str ? `?${str}` : '';
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Network request failed' }));
    throw new Error(errorData.detail || `Request failed with status ${response.status}`);
  }

  return response.json();
}

export const api = {
  // Dashboard
  getDashboard: (params = {}) => request(`/dashboard${buildQueryString(params)}`),

  // Inventory & Products
  getInventory: (params = {}) => request(`/inventory${buildQueryString(params)}`),
  getBatches: (params = {}) => request(`/inventory/batches${buildQueryString(params)}`),
  getCategories: () => request('/inventory/categories'),
  getProducts: () => request('/inventory/products'),
  addProduct: (data) => request('/inventory/products', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  deleteProduct: (sku) => request(`/inventory/products/${sku}`, {
    method: 'DELETE',
  }),
  recordSale: (data) => request('/inventory/sales', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Transactions
  getTransactions: (params = {}) => request(`/transactions${buildQueryString(params)}`),
  createTransaction: (data) => request('/transactions', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Demand & Forecast & ML
  getForecast: (params = {}) => request(`/forecasts${buildQueryString(params)}`),
  runForecast: () => request('/forecasts/run', { method: 'POST' }),
  trainModel: () => request('/forecasts/train', { method: 'POST' }),
  getModelInfo: () => request('/forecasts/model-info'),
  getModelTransparency: () => request('/forecasts/model-transparency'),
  getDemandSignals: (params = {}) => request(`/demand/signals${buildQueryString(params)}`),
  getDayOfWeekPattern: (params = {}) => request(`/demand/day-of-week${buildQueryString(params)}`),
  getDemandHeatmap: (params = {}) => request(`/demand/heatmap${buildQueryString(params)}`),
  getDemandDrivers: (params = {}) => request(`/demand/drivers${buildQueryString(params)}`),
  getUpcomingEvents: () => request('/demand/events'),

  // Replenishment & Transfers & FEFO
  getReplenishmentOverview: (params = {}) => request(`/replenishment${buildQueryString(params)}`),
  getFefoBatches: (params = {}) => request(`/replenishment/fefo-batches${buildQueryString(params)}`),
  approveRecommendation: (id) => request(`/replenishment/${id}/approve`, { method: 'POST' }),
  rejectRecommendation: (id) => request(`/replenishment/${id}/reject`, { method: 'POST' }),
  getTransfers: (params = {}) => request(`/transfers${buildQueryString(params)}`),
  executeTransfer: (id) => request(`/transfers/${id}/execute`, { method: 'POST' }),

  // Alerts & Escalations
  getAlerts: (params = {}) => request(`/alerts${buildQueryString(params)}`),
  handleAlertAction: (id, action, notes = '') => request(`/alerts/${id}/action`, {
    method: 'POST',
    body: JSON.stringify({ action, notes }),
  }),
  getEscalations: () => request('/alerts/escalations'),

  // Warehouses
  getWarehouses: () => request('/warehouses'),
  addWarehouse: (data) => request('/warehouses', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateWarehouse: (id, data) => request(`/warehouses/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteWarehouse: (id) => request(`/warehouses/${id}`, {
    method: 'DELETE',
  }),

  // Scenarios
  runScenario: (data) => request('/scenarios/run', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  getScenarioHistory: () => request('/scenarios/history'),

  // Reports
  getReportsSummary: (params = {}) => request(`/reports/summary${buildQueryString(params)}`),

  // Settings
  getSettings: () => request('/settings'),
  updateSettings: (settings) => request('/settings', {
    method: 'PUT',
    body: JSON.stringify({ settings }),
  }),

  // Notifications
  getNotifications: (params = {}) => request(`/notifications${buildQueryString(params)}`),

  // Metrics
  getMetrics: () => request('/metrics'),

  // AI Assistant
  askAssistant: (data) => request('/assistant/chat', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
};
