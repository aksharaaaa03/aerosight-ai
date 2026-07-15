import { useEffect, useState } from 'react'
import axios from 'axios'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

const API_BASE = `${import.meta.env.VITE_API_BASE}/api/epic5`

const riskColor = { High: '#EF4444', Medium: '#F59E0B', Low: '#22C55E' }

function Epic5PredictiveMaintenance() {
  const [prioritized, setPrioritized] = useState(null)
  const [selectedTurbine, setSelectedTurbine] = useState('T01')
  const [history, setHistory] = useState(null)
  const [showRealEvent, setShowRealEvent] = useState(true)

  useEffect(() => {
    axios.get(`${API_BASE}/prioritized-maintenance`).then(res => setPrioritized(res.data))
  }, [])

  useEffect(() => {
    const url = showRealEvent
      ? `${API_BASE}/turbine-forecast-history/${selectedTurbine}?start_date=2016-06-15&end_date=2016-07-18`
      : `${API_BASE}/turbine-forecast-history/${selectedTurbine}?days=60`
    axios.get(url).then(res => setHistory(res.data))
  }, [selectedTurbine, showRealEvent])

  return (
    <div style={{ padding: '32px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: 'white', marginBottom: '4px' }}>SCADA Sentinel</h1>
      <p style={{ color: '#9CA3AF', marginBottom: '24px' }}>Epic 5 — Predictive Maintenance</p>

      {prioritized && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>Maintenance Priority Ranking</h3>
          <table style={{ width: '100%', color: '#D1D5DB', borderCollapse: 'collapse', fontSize: '14px' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: '#9CA3AF', borderBottom: '1px solid #1F2937' }}>
                <th style={{ padding: '8px' }}>Rank</th><th>Turbine</th><th>Risk Level</th>
                <th>Est. Failure Likelihood (14d critical-time)</th><th>RUL Estimate</th>
                <th>Likely Component</th><th>Recommended Action</th>
              </tr>
            </thead>
            <tbody>
              {prioritized.prioritized_list.map(t => (
                <tr key={t.turbine_id} onClick={() => setSelectedTurbine(t.turbine_id)} style={{
                  cursor: 'pointer', borderBottom: '1px solid #1F2937',
                  backgroundColor: selectedTurbine === t.turbine_id ? '#111827' : 'transparent',
                }}>
                  <td style={{ padding: '10px 8px', fontWeight: 'bold' }}>#{t.priority_rank}</td>
                  <td style={{ color: '#22D3EE', fontWeight: 'bold' }}>{t.turbine_id}</td>
                  <td style={{ color: riskColor[t.risk_level], fontWeight: 'bold' }}>{t.risk_level}</td>
                  <td>{t.pct_time_critical_14d}%</td>
                  <td style={{ fontSize: '12px' }}>{t.rul_estimate}</td>
                  <td>{t.likely_component}</td>
                  <td style={{ fontSize: '12px' }}>{t.recommended_action}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ color: '#6B7280', fontSize: '12px', marginTop: '12px' }}>
            "Failure likelihood" is expressed as % of recent time spent in Critical health status, calibrated against 12 real historical failures — not a black-box probability score.
          </p>
        </div>
      )}

      <div style={{ marginBottom: '16px' }}>
        <button onClick={() => setShowRealEvent(true)} style={{
          padding: '8px 16px', marginRight: '8px', borderRadius: '8px', border: '1px solid #1F2937', cursor: 'pointer',
          backgroundColor: showRealEvent ? '#22D3EE' : '#0F1521', color: showRealEvent ? '#0B0F17' : '#D1D5DB', fontWeight: 'bold',
        }}>Real Example: T01 Pre-Failure (Jul 2016)</button>
        <button onClick={() => setShowRealEvent(false)} style={{
          padding: '8px 16px', borderRadius: '8px', border: '1px solid #1F2937', cursor: 'pointer',
          backgroundColor: !showRealEvent ? '#22D3EE' : '#0F1521', color: !showRealEvent ? '#0B0F17' : '#D1D5DB', fontWeight: 'bold',
        }}>Current State (Last 60 Days)</button>
      </div>

      {history && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>{history.turbine_id} Degradation Forecast Trend</h3>
          <p style={{ color: '#9CA3AF', fontSize: '13px', marginTop: '-8px' }}>{history.start_date} to {history.end_date}</p>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={history.history}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
              <XAxis dataKey="date" stroke="#9CA3AF" tick={{ fontSize: 10 }} />
              <YAxis stroke="#9CA3AF" domain={[0, 100]} />
              <Tooltip contentStyle={{ backgroundColor: '#0F1521', border: '1px solid #1F2937' }} />
              <ReferenceLine y={63.78} stroke="#22C55E" strokeDasharray="4 4" label={{ value: 'Healthy', fill: '#22C55E', fontSize: 10 }} />
              <ReferenceLine y={50.89} stroke="#EF4444" strokeDasharray="4 4" label={{ value: 'Critical', fill: '#EF4444', fontSize: 10 }} />
              <Line
                type="monotone" dataKey="recent_avg_health" stroke="#22D3EE" strokeWidth={2}
                dot={(props) => {
                  const { cx, cy, payload } = props
                  return <circle key={payload.date} cx={cx} cy={cy} r={4} fill={riskColor[payload.risk_level]} stroke={riskColor[payload.risk_level]} />
                }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

export default Epic5PredictiveMaintenance