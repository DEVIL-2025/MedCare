import { useState, useEffect, useCallback } from 'react';
import { RotateCcw, HelpCircle } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import { api } from '../api/client';
import { useControlTower } from '../context/ControlTowerContext';

export default function ScenarioSimulator() {
  const { selectedWarehouse, refreshKey } = useControlTower();
  const [name, setName] = useState('Flu Epidemic Spike (+60%) + Port Delay (+3d)');
  const [demandChange, setDemandChange] = useState(60);
  const [leadTimeChange, setLeadTimeChange] = useState(3);
  const [categoryFilter, setCategoryFilter] = useState('All Categories');
  const [warehouseFilter, setWarehouseFilter] = useState(selectedWarehouse || 'All Warehouses');

  const [categories, setCategories] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [simulationResult, setSimulationResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Sync with global warehouse selection
  useEffect(() => {
    if (selectedWarehouse !== 'All') {
      setWarehouseFilter(selectedWarehouse);
    }
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
        console.warn('Failed to load simulator metadata:', err);
      }
    }
    loadMeta();
  }, []);

  const runSimulation = useCallback(async () => {
    setError(null);
    try {
      const res = await api.runScenario({
        name,
        demand_change_pct: Number(demandChange),
        lead_time_change_days: Number(leadTimeChange),
        category_filter: categoryFilter,
        warehouse_filter: warehouseFilter !== 'All' && warehouseFilter !== 'All Warehouses' ? warehouseFilter : 'All Warehouses'
      });
      setSimulationResult(res);
    } catch (err) {
      console.error('Scenario simulation failed:', err);
      setError(err.message || 'Unable to execute scenario simulation on database.');
    } finally {
      setLoading(false);
    }
  }, [name, demandChange, leadTimeChange, categoryFilter, warehouseFilter]);

  useEffect(() => {
    runSimulation();
  }, [runSimulation, refreshKey]);

  function handleReset() {
    setName('Flu Epidemic Spike (+60%) + Port Delay (+3d)');
    setDemandChange(60);
    setLeadTimeChange(3);
    setCategoryFilter('All Categories');
    setWarehouseFilter('All Warehouses');
  }

  if (loading && !simulationResult) {
    return <LoadingState message="Initializing Database What-If stress test engine..." />;
  }

  if (error && !simulationResult) {
    return <ErrorState message={error} onRetry={runSimulation} />;
  }

  const summary = simulationResult?.impact_summary || {};
  const impactTrend = simulationResult?.impact_trend || [];
  const comparison = simulationResult?.comparison || [];

  return (
    <div className="space-y-5">
      {/* Top Header */}
      <div className="bg-white p-3.5 rounded-lg border border-ink-100 shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-[16px] font-bold text-ink-900">What-If Scenario Simulator & Stress Testing</h2>
          <p className="text-[12px] text-ink-500">Simulate epidemic surges, lead time delays, and supplier disruptions directly against Database inventory records.</p>
        </div>
        <button
          onClick={handleReset}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-ink-200 rounded-md text-[12px] text-ink-700 hover:bg-cream-200 cursor-pointer"
        >
          <RotateCcw size={13} /> Reset Parameters
        </button>
      </div>

      {/* Dynamic Impact Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white p-3 rounded-lg border border-ink-100 shadow-card">
          <span className="text-[11px] text-ink-500 font-medium">Projected Stockouts</span>
          <div className="text-[18px] font-bold text-brick-600 mt-0.5">{summary.projected_stockout_skus || 0} SKUs</div>
          <span className="text-[10px] text-brick-600 font-semibold">{summary.stockout_delta || '+0'}</span>
        </div>
        <div className="bg-white p-3 rounded-lg border border-ink-100 shadow-card">
          <span className="text-[11px] text-ink-500 font-medium">Stockout Loss Valuation</span>
          <div className="text-[18px] font-bold text-brick-600 mt-0.5">{summary.stockout_value || '₹0 Cr'}</div>
          <span className="text-[10px] text-ink-500 font-medium">Unmet patient orders</span>
        </div>
        <div className="bg-white p-3 rounded-lg border border-ink-100 shadow-card">
          <span className="text-[11px] text-ink-500 font-medium">Service Level (OTIF)</span>
          <div className="text-[18px] font-bold text-amber-600 mt-0.5">{summary.service_level || '95%'}</div>
          <span className="text-[10px] text-brick-600 font-semibold">{summary.service_level_delta || '0%'}</span>
        </div>
        <div className="bg-white p-3 rounded-lg border border-ink-100 shadow-card">
          <span className="text-[11px] text-ink-500 font-medium">Replenishment Needed</span>
          <div className="text-[18px] font-bold text-forest-800 mt-0.5">{summary.replenishment_need || '₹0 Cr'}</div>
          <span className="text-[10px] text-forest-700 font-semibold">{summary.replenishment_delta || '+₹0 Cr'}</span>
        </div>
      </div>

      {/* Simulator Grid: Parameter Controls & Real-Time Impact */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
        {/* Left Column: Parameter Inputs */}
        <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4 space-y-4 self-start h-fit">
          <div className="flex items-center justify-between border-b border-ink-100 pb-2">
            <h3 className="text-[14.5px] font-bold text-ink-900">Simulation Stress Parameters</h3>
          </div>

          <div className="space-y-4 text-[12.5px]">
            <div>
              <label className="block text-ink-700 font-semibold mb-1">Scenario Title</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-1.5 rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-cream-100/50"
              />
            </div>

            {/* Demand Change Slider */}
            <div>
              <div className="flex justify-between font-semibold text-ink-700 mb-1">
                <span className="flex items-center gap-1">
                  Demand Surge / Drop
                  <span title="Simulates percentage increase or decrease in prescription run-rate velocity." className="text-ink-400 cursor-help">
                    <HelpCircle size={12} />
                  </span>
                </span>
                <span className="text-forest-800 font-bold">{demandChange > 0 ? `+${demandChange}%` : `${demandChange}%`}</span>
              </div>
              <input
                type="range"
                min="-50"
                max="100"
                step="5"
                value={demandChange}
                onChange={(e) => setDemandChange(e.target.value)}
                className="w-full accent-forest-700 cursor-pointer"
              />
              <div className="flex justify-between text-[10.5px] text-ink-400">
                <span>-50% Drop</span>
                <span>Baseline (0%)</span>
                <span>+100% Surge</span>
              </div>
            </div>

            {/* Lead Time Change Slider */}
            <div>
              <div className="flex justify-between font-semibold text-ink-700 mb-1">
                <span className="flex items-center gap-1">
                  Supplier Lead Time Delay
                  <span title="Simulates delays in raw material procurement or transit customs backlogs." className="text-ink-400 cursor-help">
                    <HelpCircle size={12} />
                  </span>
                </span>
                <span className="text-amber-800 font-bold">+{leadTimeChange} Days</span>
              </div>
              <input
                type="range"
                min="0"
                max="14"
                step="1"
                value={leadTimeChange}
                onChange={(e) => setLeadTimeChange(e.target.value)}
                className="w-full accent-forest-700 cursor-pointer"
              />
              <div className="flex justify-between text-[10.5px] text-ink-400">
                <span>0 Days</span>
                <span>+7 Days</span>
                <span>+14 Days</span>
              </div>
            </div>

            {/* Category Filter */}
            <div>
              <label className="block text-ink-700 font-semibold mb-1">Impacted Therapeutic Category</label>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded border border-ink-200 bg-white text-ink-800 focus:outline-none focus:border-forest-600"
              >
                <option value="All Categories">All Categories</option>
                {categories.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* Warehouse Filter */}
            <div>
              <label className="block text-ink-700 font-semibold mb-1">Distribution Center Scope</label>
              <select
                value={warehouseFilter}
                onChange={(e) => setWarehouseFilter(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded border border-ink-200 bg-white text-ink-800 focus:outline-none focus:border-forest-600"
              >
                <option value="All Warehouses">🌐 All Warehouses (Network)</option>
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>{w.name} ({w.id})</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Right Column (2 cols): Impact Summary & Comparison */}
        <div className="lg:col-span-2 space-y-5">
          {/* Side-by-Side Baseline vs Simulated Scenario Impact */}
          <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h4 className="text-[14.5px] font-bold text-ink-900">Before vs After: Baseline vs Stress Test Outcome</h4>
                <p className="text-[11.5px] text-ink-500">Direct comparison against live database baseline metrics with detailed variance explanation.</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[12px]">
                <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
                  <tr>
                    <th className="py-2.5 px-3">Performance Dimension</th>
                    <th className="py-2.5 px-3">Current DB Baseline</th>
                    <th className="py-2.5 px-3 font-semibold text-forest-900">Simulated Outcome</th>
                    <th className="py-2.5 px-3 text-right">Variance Impact</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {comparison.map((c, i) => (
                    <tr key={i} className="hover:bg-cream-100/60 transition-colors">
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-ink-900">{c.metric}</div>
                        <div className="text-[10.5px] text-ink-400">{c.tooltip}</div>
                      </td>
                      <td className="py-2.5 px-3 text-ink-600 font-medium">{c.baseline || c.current}</td>
                      <td className="py-2.5 px-3 font-bold text-ink-900">{c.simulated || c.scenario}</td>
                      <td className="py-2.5 px-3 text-right">
                        <span className={`px-2 py-0.5 rounded font-bold text-[11.5px] ${c.isAdverse ? 'bg-brick-100 text-brick-700' : 'bg-forest-100 text-forest-800'}`}>
                          {c.delta || c.change}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Time Series Projection Chart */}
          <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
            <h4 className="text-[14px] font-bold text-ink-900 mb-2">16-Week Projected Stockout vs Replenishment Trajectory (₹ Lakhs)</h4>
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={impactTrend} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E5E1" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 10.5, fill: '#68716D' }} axisLine={{ stroke: '#E2E5E1' }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#68716D' }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 6, border: '1px solid #E2E5E1', fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12, color: '#68716D' }} />
                  <Line type="monotone" dataKey="currentStockout" stroke="#68716D" strokeWidth={1.5} strokeDasharray="3 3" name="Baseline Stockout (₹ L)" dot={false} />
                  <Line type="monotone" dataKey="scenarioStockout" stroke="#D64545" strokeWidth={2.5} name="Simulated Stockout (₹ L)" dot={{ r: 2 }} />
                  <Line type="monotone" dataKey="currentReplenish" stroke="#D5A72C" strokeWidth={1.5} strokeDasharray="3 3" name="Baseline Replenish (₹ L)" dot={false} />
                  <Line type="monotone" dataKey="scenarioReplenish" stroke="#177A5B" strokeWidth={2} name="Simulated Replenish (₹ L)" dot={{ r: 2 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}