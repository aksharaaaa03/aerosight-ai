import { useEffect, useState } from 'react'
import axios from 'axios'
import { ScatterChart, Scatter, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import KpiCard from '../components/KpiCard'

const API_BASE = 'http://localhost:8000/api/epic3'

function Epic3PowerPerformance() {
  const [summary, setSummary] = useState(null)
  const [underperforming, setUnderperforming] = useState(null)
  const [selectedTurbine, setSelectedTurbine] = useState('T07')
  const [powerCurve, setPowerCurve] = useState(null)
  const [lossTrend, setLossTrend] = useState(null)

  useEffect(() => {
    axios.get(`${API_BASE}/summary`).then(res => setSummary(res.data))
    axios.get(`${API_BASE}/underperforming-turbines`).then(res => setUnderperforming(res.data))
  }, [])

  useEffect(() => {
    axios.get(`${API_BASE}/power-curve/${selectedTurbine}`).then(res => setPowerCurve(res.data))
    axios.get(`${API_BASE}/loss-trend?turbine_id=${selectedTurbine}`).then(res => setLossTrend(res.data))
  }, [selectedTurbine])

  const normalPoints = powerCurve?.scatter_points.filter(p => p.performance_category === 'Normal') || []
  const underperfPoints = powerCurve?.scatter_points.filter(p => p.performance_category === 'Underperforming') || []

  return (
    <div style={{ padding: '32px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: 'white', marginBottom: '4px' }}>SCADA Sentinel</h1>
      <p style={{ color: '#9CA3AF', marginBottom: '24px' }}>Epic 3 — Power Performance Analysis</p>

      {summary && (
        <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', flexWrap: 'wrap' }}>
          <KpiCard title="Actual Generation" value={`${(summary.total_actual_generation_kwh / 1000).toFixed(0)} MWh`} />
          <KpiCard title="Expected Generation" value={`${(summary.total_expected_generation_kwh / 1000).toFixed(0)} MWh`} />
          <KpiCard title="Energy Loss (Sustained)" value={`${summary.total_energy_loss_from_sustained_underperformance_kwh.toLocaleString()} kWh`} subtitleColor="#F59E0B" />
          <KpiCard title="Total Alerts" value={summary.total_alerts} subtitle={`Across ${summary.underperforming_turbines_count} turbines`} />
        </div>
      )}

      {underperforming && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>Underperforming Turbines</h3>
          <table style={{ width: '100%', color: '#D1D5DB', borderCollapse: 'collapse', fontSize: '14px' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: '#9CA3AF', borderBottom: '1px solid #1F2937' }}>
                <th style={{ padding: '8px' }}>Turbine</th>
                <th>Alerts</th>
                <th>Energy Loss (kWh)</th>
                <th>Avg Ratio During Alerts</th>
                <th>Worst Ratio</th>
                <th>Downtime (min)</th>
              </tr>
            </thead>
            <tbody>
              {underperforming.turbines.map(t => (
                <tr key={t.turbine_id} onClick={() => setSelectedTurbine(t.turbine_id)} style={{
                  cursor: 'pointer', borderBottom: '1px solid #1F2937',
                  backgroundColor: selectedTurbine === t.turbine_id ? '#111827' : 'transparent',
                }}>
                  <td style={{ padding: '10px 8px', color: '#22D3EE', fontWeight: 'bold' }}>{t.turbine_id}</td>
                  <td>{t.total_alerts}</td>
                  <td>{t.total_energy_loss_kwh.toLocaleString()}</td>
                  <td>{t.avg_power_ratio_during_alerts}</td>
                  <td style={{ color: '#EF4444' }}>{t.worst_power_ratio}</td>
                  <td>{t.total_downtime_minutes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {powerCurve && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>{selectedTurbine} Power Curve</h3>
          <p style={{ color: '#9CA3AF', fontSize: '13px', marginTop: '-8px' }}>Click a turbine in the table above to switch.</p>
          <ResponsiveContainer width="100%" height={350}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
             <XAxis type="number" dataKey="Amb_WindSpeed_Avg" name="Wind Speed" unit=" m/s" stroke="#9CA3AF" domain={[0, 25]} />
<YAxis type="number" dataKey="Grd_Prod_Pwr_Avg" name="Power" unit=" kW" stroke="#9CA3AF" domain={[0, 2100]} />
              <Tooltip contentStyle={{ backgroundColor: '#0F1521', border: '1px solid #1F2937' }} cursor={{ strokeDasharray: '3 3' }} />
              <Legend />
              <Scatter name="Normal" data={normalPoints} fill="#22D3EE" opacity={0.5} />
              <Scatter name="Underperforming" data={underperfPoints} fill="#EF4444" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )}

      {lossTrend && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>{selectedTurbine} Power Loss Trend (Monthly)</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={lossTrend.trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
              <XAxis dataKey="month" stroke="#9CA3AF" tick={{ fontSize: 11 }} />
              <YAxis stroke="#9CA3AF" />
              <Tooltip contentStyle={{ backgroundColor: '#0F1521', border: '1px solid #1F2937' }} />
              <Line type="monotone" dataKey="energy_loss_kwh" stroke="#F59E0B" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

export default Epic3PowerPerformance