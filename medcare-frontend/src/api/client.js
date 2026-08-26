const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL.replace(/\/+$/, '');
  }
  if (typeof window !== 'undefined' && window.location.port !== '5173') {
    return '/api';
  }
  return 'http://localhost:8000/api';
};

const API_BASE_URL = getApiBaseUrl();

/**
 * Serializes params object into a valid query string, automatically 
 * filtering out nil, empty, and wildcard placeholder strings.
 */
function buildQueryString(params = {}) {
  const cleanParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (
      value !== undefined &&
      value !== null &&
      value !== '' &&
      value !== 'undefined' &&
      value !== 'null' &&
      value !== 'All'
    ) {
      cleanParams.append(key, value);
    }
  }
  const str = cleanParams.toString();
  return str ? `?${str}` : '';
}

/**
 * Base HTTP Fetch Wrapper handling headers, auth tokens, error normalization, and signals.
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const token = localStorage.getItem('medcare_auth_token');

  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  if (token) {
    defaultHeaders['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    });

    // Handle Unauthenticated State (Expired/Invalid Token)
    if (response.status === 401) {
      localStorage.removeItem('medcare_auth_token');
      window.dispatchEvent(new Event('auth:unauthorized'));
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Network request failed' }));
      const error = new Error(errorData.detail || `Request failed with status ${response.status}`);
      error.status = response.status;
      error.detail = errorData.detail;
      throw error;
    }

    // Return empty object for 204 No Content responses
    if (response.status === 204) {
      return {};
    }

    return await response.json();
  } catch (err) {
    if (err.name === 'AbortError') {
      throw err; // Allow standard abort error handling in component effects
    }
    throw err;
  }
}

export const api = {
  // Authentication & Session
  login: (identifier, password, options) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ identifier, password }),
      ...options,
    }),
  getMe: (options) => request('/auth/me', options),
  logout: (options) => request('/auth/logout', { method: 'POST', ...options }),
  changePassword: (current_password, new_password, options) =>
    request('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password }),
      ...options,
    }),

  // User Management & RBAC & Audit (Admin Only)
  getUsers: (params = {}, options) => request(`/users${buildQueryString(params)}`, options),
  createUser: (data, options) =>
    request('/users', {
      method: 'POST',
      body: JSON.stringify(data),
      ...options,
    }),
  updateUser: (id, data, options) =>
    request(`/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
      ...options,
    }),
  resetUserPassword: (id, options) =>
    request(`/users/${id}/reset-password`, {
      method: 'POST',
      ...options,
    }),
  toggleUserStatus: (id, options) =>
    request(`/users/${id}/toggle-status`, {
      method: 'POST',
      ...options,
    }),
  getRoles: (options) => request('/users/roles', options),
  getAuditLogs: (params = {}, options) => request(`/audit-logs${buildQueryString(params)}`, options),

  // Dashboard
  getDashboard: (params = {}, options) => request(`/dashboard${buildQueryString(params)}`, options),

  // Inventory & Products
  getInventory: (params = {}, options) => request(`/inventory${buildQueryString(params)}`, options),
  getBatches: (params = {}, options) => request(`/inventory/batches${buildQueryString(params)}`, options),
  getCategories: (options) => request('/inventory/categories', options),
  getProducts: (options) => request('/inventory/products', options),
  addProduct: (data, options) =>
    request('/inventory/products', {
      method: 'POST',
      body: JSON.stringify(data),
      ...options,
    }),
  deleteProduct: (sku, options) =>
    request(`/inventory/products/${sku}`, {
      method: 'DELETE',
      ...options,
    }),
  recordSale: (data, options) =>
    request('/inventory/sales', {
      method: 'POST',
      body: JSON.stringify(data),
      ...options,
    }),

  // Transactions & History
  getTransactions: (params = {}, options) => request(`/transactions${buildQueryString(params)}`, options),
  createTransaction: (data, options) =>
    request('/transactions', {
      method: 'POST',
      body: JSON.stringify(data),
      ...options,
    }),

  // Demand & Forecast & ML
  getForecast: (params = {}, options) => request(`/forecasts${buildQueryString(params)}`, options),
  runForecast: (options) => request('/forecasts/run', { method: 'POST', ...options }),
  trainModel: (options) => request('/forecasts/train', { method: 'POST', ...options }),
  getModelInfo: (options) => request('/forecasts/model-info', options),
  getModelTransparency: (options) => request('/forecasts/model-transparency', options),
  getDemandSignals: (params = {}, options) => request(`/demand/signals${buildQueryString(params)}`, options),
  getDayOfWeekPattern: (params = {}, options) => request(`/demand/day-of-week${buildQueryString(params)}`, options),
  getDemandHeatmap: (params = {}, options) => request(`/demand/heatmap${buildQueryString(params)}`, options),
  getDemandDrivers: (params = {}, options) => request(`/demand/drivers${buildQueryString(params)}`, options),
  getUpcomingEvents: (options) => request('/demand/events', options),

  // Replenishment & Transfers & FEFO
  getReplenishmentOverview: (params = {}, options) => request(`/replenishment${buildQueryString(params)}`, options),
  getFefoBatches: (params = {}, options) => request(`/replenishment/fefo-batches${buildQueryString(params)}`, options),
  approveRecommendation: (id, options) => request(`/replenishment/${id}/approve`, { method: 'POST', ...options }),
  rejectRecommendation: (id, options) => request(`/replenishment/${id}/reject`, { method: 'POST', ...options }),
  acknowledgeDemand: (id, options) => request(`/replenishment/${id}/acknowledge`, { method: 'POST', ...options }),
  completeDemand: (id, options) => request(`/replenishment/${id}/complete`, { method: 'POST', ...options }),
  getTransfers: (params = {}, options) => request(`/transfers${buildQueryString(params)}`, options),
  executeTransfer: (id, options) => request(`/transfers/${id}/execute`, { method: 'POST', ...options }),

  // Alerts & Escalations
  getAlerts: (params = {}, options) => request(`/alerts${buildQueryString(params)}`, options),
  handleAlertAction: (id, action, notes = '', options) =>
    request(`/alerts/${id}/action`, {
      method: 'POST',
      body: JSON.stringify({ action, notes }),
      ...options,
    }),
  getEscalations: (options) => request('/alerts/escalations', options),

  // Warehouses
  getWarehouses: (options) => request('/warehouses', options),
  addWarehouse: (data, options) =>
    request('/warehouses', {
      method: 'POST',
      body: JSON.stringify(data),
      ...options,
    }),
  updateWarehouse: (id, data, options) =>
    request(`/warehouses/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
      ...options,
    }),
  deleteWarehouse: (id, options) =>
    request(`/warehouses/${id}`, {
      method: 'DELETE',
      ...options,
    }),

  // Scenarios
  runScenario: (data, options) =>
    request('/scenarios/run', {
      method: 'POST',
      body: JSON.stringify(data),
      ...options,
    }),
  getScenarioHistory: (options) => request('/scenarios/history', options),

  // Reports
  getReportsSummary: (params = {}, options) => request(`/reports/summary${buildQueryString(params)}`, options),

  // Settings
  getSettings: (options) => request('/settings', options),
  updateSettings: (settings, options) =>
    request('/settings', {
      method: 'PUT',
      body: JSON.stringify({ settings }),
      ...options,
    }),

  // Suppliers
  getSuppliers: (params = {}, options) => request(`/suppliers${buildQueryString(params)}`, options),
  addSupplier: (data, options) =>
    request('/suppliers', {
      method: 'POST',
      body: JSON.stringify(data),
      ...options,
    }),
  updateSupplier: (id, data, options) =>
    request(`/suppliers/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
      ...options,
    }),
  deleteSupplier: (id, options) =>
    request(`/suppliers/${id}`, {
      method: 'DELETE',
      ...options,
    }),

  // Notifications
  getNotifications: (params = {}, options) => request(`/notifications${buildQueryString(params)}`, options),
  triggerLowStockCheck: (params = {}, options) =>
    request(`/notifications/low-stock-check${buildQueryString(params)}`, {
      method: 'POST',
      ...options,
    }),

  // Metrics
  getMetrics: (options) => request('/metrics', options),

  // AI Assistant
  chatWithAssistant: (data, options) =>
    request('/assistant/chat', {
      method: 'POST',
      body: JSON.stringify(data),
      ...options,
    }),
};