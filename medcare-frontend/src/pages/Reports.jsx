import { useState, useEffect, useCallback } from 'react';
import { DollarSign, Boxes, Truck, AlertTriangle, ShieldAlert, Download, Sparkles, TrendingUp, Award, Filter, RefreshCw } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, BarChart, Bar, ResponsiveContainer } from 'recharts';
import StatCard from '../components/ui/StatCard';
import Badge from '../components/ui/Badge';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import EmptyState from '../components/ui/EmptyState';
import { api } from '../api/client';
import { useControlTower } from '../context/ControlTowerContext';
import { formatDateTime, formatDate } from '../utils/dateUtils';

const REPORT_TYPES = [
  'All Reports',
  'Executive Valuation Audit',
  'FEFO Expiry Risk Report',
  'DC Stockout Analysis',
  'Therapeutic Category Consumption'
];

const TIME_PERIODS = [
  'Last 7 Days',
  'Last 14 Days',
  'Last 30 Days',
  'Last 90 Days'
];

export default function Reports() {
  const { selectedWarehouse, setSelectedWarehouse, refreshKey } = useControlTower();
  const [reportType, setReportType] = useState('All Reports');
  const [warehouseFilter, setWarehouseFilter] = useState(selectedWarehouse || 'All');
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [timePeriod, setTimePeriod] = useState('Last 14 Days');
  
  const [data, setData] = useState(null);
  const [metricsData, setMetricsData] = useState(null);
  const [categories, setCategories] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Sync with global warehouse selection
  useEffect(() => {
    setWarehouseFilter(selectedWarehouse);
  }, [selectedWarehouse]);

  // Load categories and warehouses
  useEffect(() => {
    async function loadMeta() {
      try {
        const [cats, whs] = await Promise.all([
          api.getCategories(),
          api.getWarehouses()
        ]);
        setCategories(Array.isArray(cats) ? cats : []);
        setWarehouses(Array.isArray(whs) ? whs : (whs?.overview || []));
      } catch (err) {
        console.warn('Failed to load filter metadata:', err);
      }
    }
    loadMeta();
  }, []);

  const loadReports = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rep, met] = await Promise.all([
        api.getReportsSummary({
          report_type: reportType,
          warehouse: warehouseFilter,
          category: categoryFilter,
          time_period: timePeriod
        }),
        api.getMetrics()
      ]);
      setData(rep);
      setMetricsData(met);
    } catch (err) {
      console.error('Reports load error:', err);
      setError(err.message || 'Unable to connect to reports service.');
    } finally {
      setLoading(false);
    }
  }, [reportType, warehouseFilter, categoryFilter, timePeriod]);

  useEffect(() => {
    loadReports();
  }, [loadReports, refreshKey]);

  function exportReportCSV() {
    if (!data) return;
    const rows = [
      ['Report Parameter', 'Applied Setting'],
      ['Report Type', reportType],
      ['Warehouse Scope', warehouseFilter],
      ['Category Filter', categoryFilter],
      ['Time Period Window', timePeriod],
      ['Generation Timestamp (IST)', formatDateTime(data?.server_time || new Date())],
      [''],
      ['Metric', 'Value'],
      ['Total Inventory Value', data.kpis?.total_inventory_value || '₹0 Cr'],
      ['Consumption in Period', data.kpis?.total_consumption || '0 units'],
      ['Pending Replenishment Value', data.kpis?.replenishment_value || '₹0 Cr'],
      ['Expiry Value at Risk', data.kpis?.expiry_value_at_risk || '₹0 Cr'],
      ['Stockout Incidents Logged', data.kpis?.stockout_incidents || 0],
      ['Annualized Cost Savings', metricsData?.business_impact?.total_savings_annual_inr || '₹2.95 Cr'],
      ['Estimated ROI Multiple', metricsData?.business_impact?.roi_multiple || '6.8x'],
    ];
    const csvContent = 'data:text/csv;charset=utf-8,' + rows.map(e => e.join(',')).join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `medcare_scm_report_${warehouseFilter}_${timePeriod.replace(/\s+/g, '_')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  if (loading && !data) {
    return <LoadingState message="Aggregating PostgreSQL supply chain financial ROI and inventory aging analytics..." />;
  }

  if (error && !data) {
    return <ErrorState message={error} onRetry={loadReports} />;
  }

  const kpis = data?.kpis || {};
  const inventory_value_trend = data?.inventory_value_trend || [];
  const aging_summary = data?.aging_summary || [];
  const top_categories_by_consumption = data?.top_categories_by_consumption || [];
  const stockout_by_warehouse = data?.stockout_by_warehouse || [];
  const business_impact = metricsData?.business_impact || {};

  const showValuation = reportType === 'All Reports' || reportType === 'Executive Valuation Audit';
  const showAging = reportType === 'All Reports' || reportType === 'FEFO Expiry Risk Report';
  const showStockouts = reportType === 'All Reports' || reportType === 'DC Stockout Analysis';
  const showCategories = reportType === 'All Reports' || reportType === 'Therapeutic Category Consumption';

  return (
    <div className="space-y-5">
      {/* Top Header & Export Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3.5 rounded-lg border border-ink-100 shadow-card">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-[16px] font-bold text-ink-900">Supply Chain Analytics & Financial ROI Audit</h2>
            {data?.formatted_server_time && (
              <span className="text-[10.5px] px-2 py-0.5 rounded bg-cream-200 text-ink-600 font-mono">
                {data.formatted_server_time}
              </span>
            )}
          </div>
          <p className="text-[12px] text-ink-500">Live PostgreSQL valuation trends, FEFO batch aging distributions, and before-vs-after ROI metrics.</p>
        </div>
        <button
          onClick={exportReportCSV}
          className="flex items-center gap-1.5 px-3.5 py-1.5 bg-forest-700 hover:bg-forest-600 text-white rounded-md text-[12px] font-semibold transition-colors shadow-sm cursor-pointer"
        >
          <Download size={14} /> Download Executive Report (CSV)
        </button>
      </div>

      {/* Applied Filters Bar */}
      <div className="bg-white p-3.5 rounded-lg border border-ink-100 shadow-card space-y-2">
        <div className="flex items-center gap-1.5 text-[12px] font-bold text-ink-800">
          <Filter size={14} className="text-forest-700" /> Filter Query Scope:
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
          {/* Report Type */}
          <div>
            <label className="text-[10.5px] font-semibold text-ink-500 block mb-1">Report Module</label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
              className="w-full text-[12px] px-2.5 py-1.5 rounded border border-ink-200 bg-white text-ink-800 focus:outline-none focus:border-forest-600"
            >
              {REPORT_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          {/* Warehouse */}
          <div>
            <label className="text-[10.5px] font-semibold text-ink-500 block mb-1">Distribution Center</label>
            <select
              value={warehouseFilter}
              onChange={(e) => {
                setWarehouseFilter(e.target.value);
                setSelectedWarehouse(e.target.value);
              }}
              className="w-full text-[12px] px-2.5 py-1.5 rounded border border-ink-200 bg-white text-ink-800 focus:outline-none focus:border-forest-600"
            >
              <option value="All">🌐 All Warehouses (Aggregated)</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>{w.name} ({w.id})</option>
              ))}
            </select>
          </div>

          {/* Category */}
          <div>
            <label className="text-[10.5px] font-semibold text-ink-500 block mb-1">Therapeutic Category</label>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="w-full text-[12px] px-2.5 py-1.5 rounded border border-ink-200 bg-white text-ink-800 focus:outline-none focus:border-forest-600"
            >
              <option value="All">All Categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* Time Period */}
          <div>
            <label className="text-[10.5px] font-semibold text-ink-500 block mb-1">Analysis Time Window</label>
            <select
              value={timePeriod}
              onChange={(e) => setTimePeriod(e.target.value)}
              className="w-full text-[12px] px-2.5 py-1.5 rounded border border-ink-200 bg-white text-ink-800 focus:outline-none focus:border-forest-600"
            >
              {TIME_PERIODS.map((tp) => (
                <option key={tp} value={tp}>{tp}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={DollarSign} tone="forest" label="Total Inventory Value" value={kpis.total_inventory_value || '₹0 Cr'} delta={`In scope (${warehouseFilter})`} />
        <StatCard icon={Boxes} tone="sage" label="Consumption in Period" value={kpis.total_consumption || '0 units'} delta={timePeriod} />
        <StatCard icon={Truck} tone="gold" label="Projected Replenishment" value={kpis.replenishment_value || '₹0 Cr'} delta="Pending PO demand" />
        <StatCard icon={ShieldAlert} tone="brick" label="Expiry Value at Risk" value={kpis.expiry_value_at_risk || '₹0 Cr'} delta="Batches < 90 days" deltaPositive={false} />
      </div>

      {/* Business Impact ROI Comparison Table */}
      {(reportType === 'All Reports' || reportType === 'Executive Valuation Audit') && (
        <div className="bg-white rounded-lg border-2 border-forest-600/30 shadow-card p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-[15px] font-bold text-ink-900 flex items-center gap-1.5">
                <Sparkles size={16} className="text-forest-700" /> SCM Control Tower Business Impact & Transformation
              </h3>
              <p className="text-[12px] text-ink-500">Measurable improvements comparing traditional siloed operations vs the MedCare Control Tower.</p>
            </div>
            <Badge tone="forest">Annual ROI: {business_impact.roi_multiple || '6.8x'}</Badge>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12.5px]">
              <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
                <tr>
                  <th className="py-2.5 px-3">Performance Metric</th>
                  <th className="py-2.5 px-3">Traditional Baseline</th>
                  <th className="py-2.5 px-3 font-semibold text-forest-900">MedCare Control Tower</th>
                  <th className="py-2.5 px-3 font-semibold text-forest-800 text-right">Business Impact</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {business_impact.before_vs_after && business_impact.before_vs_after.map((row, i) => (
                  <tr key={i} className="hover:bg-cream-100/60 transition-colors">
                    <td className="py-2.5 px-3 font-medium text-ink-900">{row.metric}</td>
                    <td className="py-2.5 px-3 text-ink-500 line-through">{row.baseline}</td>
                    <td className="py-2.5 px-3 font-bold text-forest-800">{row.control_tower}</td>
                    <td className="py-2.5 px-3 text-right">
                      <span className="font-semibold text-forest-700 bg-forest-100 px-2 py-0.5 rounded text-[11.5px]">
                        {row.improvement}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Valuation Trend & Aging Charts */}
      {(showValuation || showAging) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Inventory Value Trend */}
          {showValuation && (
            <div className={`bg-white rounded-lg border border-ink-100 shadow-card p-4 ${!showAging ? 'lg:col-span-2' : ''}`}>
              <h3 className="text-[14.5px] font-bold text-ink-900 mb-3">Live Inventory Valuation Trend (₹ Lakhs)</h3>
              <div className="h-64">
                {inventory_value_trend.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={inventory_value_trend} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#E2E5E1" vertical={false} />
                      <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#68716D' }} axisLine={{ stroke: '#E2E5E1' }} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: '#68716D' }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={{ borderRadius: 6, border: '1px solid #E2E5E1', fontSize: 12 }} />
                      <Legend wrapperStyle={{ fontSize: 12, color: '#68716D' }} />
                      <Line type="monotone" dataKey="total" stroke="#177A5B" strokeWidth={2.5} name="Total Valuation (₹ L)" dot={false} />
                      <Line type="monotone" dataKey="usable" stroke="#2E8B68" strokeWidth={2} strokeDasharray="4 3" name="Healthy Stock (₹ L)" dot={false} />
                      <Line type="monotone" dataKey="atRisk" stroke="#D64545" strokeWidth={2} name="Near-Expiry Risk (₹ L)" dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState title="No Trend Data" description="No demand history records in selected time window." />
                )}
              </div>
            </div>
          )}

          {/* Batch Aging Distribution */}
          {showAging && (
            <div className={`bg-white rounded-lg border border-ink-100 shadow-card p-4 ${!showValuation ? 'lg:col-span-2' : ''}`}>
              <h3 className="text-[14.5px] font-bold text-ink-900 mb-3">FEFO Batch Expiry Aging Breakdown</h3>
              <div className="space-y-3 pt-2 text-[12px]">
                {aging_summary.map((item, i) => (
                  <div key={i} className="space-y-1">
                    <div className="flex justify-between text-ink-700">
                      <span className="font-semibold text-ink-900">{item.bucket}</span>
                      <span className="font-bold text-ink-800">{Number(item.units || 0).toLocaleString()} units ({item.pct}%)</span>
                    </div>
                    <div className="w-full bg-cream-200 rounded-full h-2">
                      <div
                        className="h-2 rounded-full"
                        style={{ width: `${item.pct}%`, backgroundColor: item.color || '#177A5B' }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Category Consumption & DC Stockout Breakdown */}
      {(showCategories || showStockouts) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Category Consumption */}
          {showCategories && (
            <div className={`bg-white rounded-lg border border-ink-100 shadow-card p-4 ${!showStockouts ? 'lg:col-span-2' : ''}`}>
              <h3 className="text-[14.5px] font-bold text-ink-900 mb-3">Therapeutic Category Consumption (Value In Window)</h3>
              <div className="space-y-3 pt-2 text-[12px]">
                {top_categories_by_consumption.length > 0 ? (
                  top_categories_by_consumption.map((item, i) => (
                    <div key={i} className="space-y-1">
                      <div className="flex justify-between text-ink-700">
                        <span className="font-semibold text-ink-900">{item.name}</span>
                        <span className="font-bold text-forest-800">{item.display}</span>
                      </div>
                      <div className="w-full bg-cream-200 rounded-full h-2">
                        <div
                          className="h-2 rounded-full"
                          style={{
                            width: `${Math.min(100, Math.max(5, (item.value / (top_categories_by_consumption[0]?.value || 1)) * 100))}%`,
                            backgroundColor: item.color || '#177A5B'
                          }}
                        />
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-ink-400 text-[12px]">No category consumption recorded in this timeframe.</p>
                )}
              </div>
            </div>
          )}

          {/* DC Stockout Incidents */}
          {showStockouts && (
            <div className={`bg-white rounded-lg border border-ink-100 shadow-card p-4 ${!showCategories ? 'lg:col-span-2' : ''}`}>
              <h3 className="text-[14.5px] font-bold text-ink-900 mb-3">Distribution Center Stockout Incidents</h3>
              <div className="space-y-2.5 pt-2 text-[12px]">
                {stockout_by_warehouse.length > 0 ? (
                  stockout_by_warehouse.map((wh, i) => (
                    <div key={i} className="flex items-center justify-between p-2.5 rounded bg-cream-100/60 border border-ink-100">
                      <div className="font-semibold text-ink-900">{wh.warehouse}</div>
                      <Badge tone={wh.count > 10 ? 'critical' : wh.count > 0 ? 'warning' : 'good'}>
                        {wh.count} Stockout Alerts
                      </Badge>
                    </div>
                  ))
                ) : (
                  <p className="text-ink-400 text-[12px]">No active stockout incidents logged across active DCs.</p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}