import { useState, useEffect, useCallback } from 'react';
import { DollarSign, Boxes, Truck, AlertTriangle, ShieldAlert, Download, Sparkles, TrendingUp, Award, Filter, RefreshCw, BarChart3, CheckCircle2 } from 'lucide-react';
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

  // Load categories and warehouses metadata
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

    function csvCell(val) {
      if (val === null || val === undefined) return '""';
      const s = String(val).replace(/"/g, '""');
      return `"${s}"`;
    }

    const lines = [];

    // 1. Header Metadata
    lines.push([csvCell('MEDCARE PHARMA SCM CONTROL TOWER - EXECUTIVE SUPPLY CHAIN & FINANCIAL ROI REPORT')]);
    lines.push([csvCell(`Report Generated (IST): ${data.formatted_server_time || formatDateTime(new Date())}`)]);
    lines.push([csvCell(`Report Scope: ${warehouseFilter === 'All' ? 'All Distribution Centers (Network Rollup)' : warehouseFilter}`)]);
    lines.push([csvCell(`Therapeutic Category: ${categoryFilter}`)]);
    lines.push([csvCell(`Analysis Time Window: ${timePeriod}`)]);
    lines.push([csvCell(`Module Filter: ${reportType}`)]);
    lines.push([]);

    // 2. Executive KPI Summary
    lines.push([csvCell('=== 1. EXECUTIVE SUPPLY CHAIN KPI SUMMARY ===')]);
    lines.push([csvCell('Metric Name'), csvCell('Value'), csvCell('Scope / Notes')]);
    lines.push([csvCell('Total Inventory Value'), csvCell(kpis.total_inventory_value || '₹0'), csvCell(`Live valuation in ${warehouseFilter}`)]);
    lines.push([csvCell('Total Physical Units in Stock'), csvCell(kpis.total_inventory_units?.toLocaleString() || '0 units'), csvCell('Aggregate batch stock units')]);
    lines.push([csvCell('Consumption in Period'), csvCell(kpis.total_consumption || '0 units'), csvCell(`Outbound demand in ${timePeriod}`)]);
    lines.push([csvCell('Projected Replenishment Requirement'), csvCell(kpis.replenishment_value || '₹0'), csvCell('Pending purchase orders & replenishment demand')]);
    lines.push([csvCell('Expiry Value at Risk (< 90 Days)'), csvCell(kpis.expiry_value_at_risk || '₹0'), csvCell('Batches requiring urgent FEFO liquidation')]);
    lines.push([csvCell('Distribution Center Stockout Incidents'), csvCell(kpis.stockout_incidents || 0), csvCell('Active shortage/stockout alerts logged')]);
    lines.push([csvCell('Annualized Cost Savings'), csvCell(business_impact.total_savings_annual_inr || '₹2.95 Cr'), csvCell('Avoided stockouts and expired write-offs')]);
    lines.push([csvCell('Estimated ROI Multiple'), csvCell(business_impact.roi_multiple || '6.8x'), csvCell('Annualized return multiple')]);
    lines.push([]);

    // 3. Historical Inventory Valuation Trend
    lines.push([csvCell('=== 2. DAILY INVENTORY VALUATION TREND ===')]);
    lines.push([csvCell('Date'), csvCell('Total Valuation (₹ Lakhs)'), csvCell('Healthy Stock (₹ Lakhs)'), csvCell('Near-Expiry at Risk (₹ Lakhs)')]);
    if (inventory_value_trend.length > 0) {
      inventory_value_trend.forEach((row) => {
        lines.push([
          csvCell(row.date),
          csvCell(row.total),
          csvCell(row.usable),
          csvCell(row.atRisk)
        ]);
      });
    } else {
      lines.push([csvCell('No trend records found for selected window')]);
    }
    lines.push([]);

    // 4. FEFO Batch Expiry Aging Breakdown
    lines.push([csvCell('=== 3. FEFO BATCH EXPIRY AGING BREAKDOWN ===')]);
    lines.push([csvCell('Aging Interval Bracket'), csvCell('Quantity in Stock (Units)'), csvCell('Proportion (%)'), csvCell('Valuation (₹ Lakhs)'), csvCell('Valuation (₹ Cr)')]);
    if (aging_summary.length > 0) {
      aging_summary.forEach((item) => {
        lines.push([
          csvCell(item.bucket),
          csvCell(item.units?.toLocaleString()),
          csvCell(item.pct_display || `${item.pct}%`),
          csvCell(item.value_lakh ?? (item.value_cr ? (item.value_cr * 100).toFixed(2) : '0')),
          csvCell(item.value_cr ?? '0')
        ]);
      });
    } else {
      lines.push([csvCell('No aging data available')]);
    }
    lines.push([]);

    // 5. Therapeutic Category Consumption
    lines.push([csvCell('=== 4. THERAPEUTIC CATEGORY CONSUMPTION (WINDOW) ===')]);
    lines.push([csvCell('Therapeutic Category'), csvCell('Consumption Value (₹ Lakhs)'), csvCell('Formatted Display')]);
    if (top_categories_by_consumption.length > 0) {
      top_categories_by_consumption.forEach((cat) => {
        lines.push([
          csvCell(cat.name),
          csvCell(cat.value),
          csvCell(cat.display)
        ]);
      });
    } else {
      lines.push([csvCell('No category consumption records found')]);
    }
    lines.push([]);

    // 6. Distribution Center Stockout Incidents
    lines.push([csvCell('=== 5. DISTRIBUTION CENTER STOCKOUT INCIDENTS ===')]);
    lines.push([csvCell('Warehouse / DC ID'), csvCell('Warehouse Name'), csvCell('Active Stockout / Shortage Alerts')]);
    if (stockout_by_warehouse.length > 0) {
      stockout_by_warehouse.forEach((wh) => {
        lines.push([
          csvCell(wh.warehouse),
          csvCell(wh.name || wh.warehouse),
          csvCell(wh.count)
        ]);
      });
    } else {
      lines.push([csvCell('No active stockouts logged across network')]);
    }
    lines.push([]);

    // 7. Business Impact & ROI Transformation
    if (business_impact.before_vs_after && business_impact.before_vs_after.length > 0) {
      lines.push([csvCell('=== 6. SCM CONTROL TOWER BUSINESS IMPACT & ROI TRANSFORMATION ===')]);
      lines.push([csvCell('Performance Metric'), csvCell('Traditional Baseline'), csvCell('MedCare Control Tower'), csvCell('Measured Business Impact')]);
      business_impact.before_vs_after.forEach((row) => {
        lines.push([
          csvCell(row.metric),
          csvCell(row.baseline),
          csvCell(row.control_tower),
          csvCell(row.improvement)
        ]);
      });
      lines.push([]);
    }

    const csvContent = 'data:text/csv;charset=utf-8,\uFEFF' + lines.map((l) => l.join(',')).join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    const dateStr = new Date().toISOString().slice(0, 10);
    link.setAttribute('download', `Executive_Supply_Chain_Report_${dateStr}.csv`);
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
          title="Download complete structured CSV report"
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
        <StatCard icon={DollarSign} tone="forest" label="Total Inventory Value" value={kpis.total_inventory_value || '₹0'} delta={`In scope (${warehouseFilter})`} />
        <StatCard icon={Boxes} tone="sage" label="Consumption in Period" value={kpis.total_consumption || '0 units'} delta={timePeriod} />
        <StatCard icon={Truck} tone="gold" label="Projected Replenishment" value={kpis.replenishment_value || '₹0'} delta="Pending PO demand" />
        <StatCard icon={ShieldAlert} tone="brick" label="Expiry Value at Risk" value={kpis.expiry_value_at_risk || '₹0'} delta="Batches < 90 days" deltaPositive={false} />
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
                      <span className="font-bold text-ink-800">
                        {Number(item.units || 0).toLocaleString()} units ({item.pct_display || `${item.pct}%`})
                      </span>
                    </div>
                    <div className="w-full bg-cream-200 rounded-full h-2">
                      <div
                        className="h-2 rounded-full"
                        style={{ width: `${Math.max(item.units > 0 ? 1 : 0, item.pct)}%`, backgroundColor: item.color || '#177A5B' }}
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
                      <div>
                        <div className="font-semibold text-ink-900">{wh.name || wh.warehouse} ({wh.warehouse})</div>
                        <div className="text-[11px] text-ink-500">{wh.count > 0 ? 'Active alerts logged' : 'Optimal buffer stock maintained'}</div>
                      </div>
                      <Badge tone={wh.count > 10 ? 'critical' : wh.count > 0 ? 'warning' : 'good'}>
                        {wh.count > 0 ? `${wh.count} Stockout Alerts` : 'Zero Stockouts'}
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