import { useEffect, useState } from 'react'
import axios from 'axios'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import KpiCard from '../components/KpiCard'

const API_BASE = 'http://localhost:8000/api/epic2'

function Epic2HealthMonitoring() {
  const [fleetSummary, setFleetSummary] = useState(null)
  const [selectedTurbine, setSelectedTurbine] = useState('T01')
  const [trend, setTrend] = useState(null)

  useEffect(() => {
    axios.get(`${API_BASE}/fleet-summary`).then(res => setFleetSummary(res.data))
  }, [])

  useEffect(() => {
    // Defaults to T01's real documented gearbox failure window — our strongest evidence
    axios.get(`${API_BASE}/trend/${selectedTurbine}?start_date=2016-07-01&end_date=2016-07-25`)
      .then(res => setTrend(res.data))
  }, [selectedTurbine])

  const statusColor = { Healthy: '#22C55E', Warning: '#F59E0B', Critical: '#EF4444' }

  return (
    <div style={{ padding: '32px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: 'white', marginBottom: '4px' }}>SCADA Sentinel</h1>
      <p style={{ color: '#9CA3AF', marginBottom: '24px' }}>Epic 2 — Turbine Health Monitoring</p>

      {fleetSummary && (
        <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', flexWrap: 'wrap' }}>
          <KpiCard title="Healthy Turbines" value={fleetSummary.healthy_count} subtitleColor="#22C55E" />
          <KpiCard title="Warning Turbines" value={fleetSummary.warning_count} subtitleColor="#F59E0B" />
          <KpiCard title="Critical Turbines" value={fleetSummary.critical_count} subtitleColor="#EF4444" />
        </div>
      )}

      {fleetSummary && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>Fleet Health Overview</h3>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {fleetSummary.turbines.map(t => (
              <div key={t.Turbine_ID} onClick={() => setSelectedTurbine(t.Turbine_ID)} style={{
                cursor: 'pointer',
                backgroundColor: selectedTurbine === t.Turbine_ID ? '#111827' : '#0B0F17',
                border: `1px solid ${selectedTurbine === t.Turbine_ID ? '#22D3EE' : '#1F2937'}`,
                borderRadius: '8px', padding: '14px 20px', minWidth: '140px',
              }}>
                <div style={{ color: '#22D3EE', fontWeight: 'bold' }}>{t.Turbine_ID}</div>
                <div style={{ color: 'white', fontSize: '20px', fontWeight: 'bold' }}>{t.health_score.toFixed(1)}</div>
                <div style={{ color: statusColor[t.health_status], fontSize: '12px' }}>{t.health_status}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {trend && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>
            {selectedTurbine} Health Trend — {trend.start_date} to {trend.end_date}
          </h3>
          <p style={{ color: '#9CA3AF', fontSize: '13px', marginTop: '-8px' }}>
            Click a turbine above to explore its trend. Default view shows T01's real documented gearbox failure (July 18, 2016).
          </p>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trend.trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
              <XAxis dataKey="date" stroke="#9CA3AF" tick={{ fontSize: 11 }} />
              <YAxis stroke="#9CA3AF" domain={[0, 100]} />
              <Tooltip contentStyle={{ backgroundColor: '#0F1521', border: '1px solid #1F2937' }} />
              <ReferenceLine y={63.78} stroke="#F59E0B" strokeDasharray="4 4" label={{ value: 'Healthy threshold', fill: '#F59E0B', fontSize: 11 }} />
              <ReferenceLine y={50.89} stroke="#EF4444" strokeDasharray="4 4" label={{ value: 'Critical threshold', fill: '#EF4444', fontSize: 11 }} />
              <Line
                type="monotone"
                dataKey="health_score"
                stroke="#22D3EE"
                strokeWidth={2}
                dot={(props) => {
                    const { cx, cy, payload } = props
                    const color = statusColor[payload.health_status] || '#22D3EE'
                    return <circle key={payload.date} cx={cx} cy={cy} r={4} fill={color} stroke={color} />
  }}
  />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

export default Epic2HealthMonitoring