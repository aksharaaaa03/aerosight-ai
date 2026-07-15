import { useEffect, useState } from 'react'
import axios from 'axios'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts'

const API_BASE = `${import.meta.env.VITE_API_BASE}/api/epic4`

function Epic4FaultAnalysis() {
  const [rootCauseSummary, setRootCauseSummary] = useState(null)
  const [selectedTurbine, setSelectedTurbine] = useState('T01')
  const [timeline, setTimeline] = useState(null)
  const [selectedEventIndex, setSelectedEventIndex] = useState(null)
  const [contribution, setContribution] = useState(null)
  const [trendComparison, setTrendComparison] = useState(null)

  useEffect(() => {
    axios.get(`${API_BASE}/root-cause-summary`).then(res => setRootCauseSummary(res.data))
  }, [])

  useEffect(() => {
    axios.get(`${API_BASE}/fault-timeline?turbine_id=${selectedTurbine}`).then(res => {
      setTimeline(res.data)
      if (res.data.timeline.length > 0) {
        setSelectedEventIndex(res.data.timeline[0].event_index)
      }
    })
  }, [selectedTurbine])

  useEffect(() => {
    if (selectedEventIndex === null) return
    axios.get(`${API_BASE}/sensor-contribution/${selectedEventIndex}`).then(res => setContribution(res.data))
    axios.get(`${API_BASE}/sensor-trend-comparison/${selectedEventIndex}`).then(res => setTrendComparison(res.data))
  }, [selectedEventIndex])

  return (
    <div style={{ padding: '32px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: 'white', marginBottom: '4px' }}>SCADA Sentinel</h1>
      <p style={{ color: '#9CA3AF', marginBottom: '24px' }}>Epic 4 — Fault & Root Cause Analysis</p>

      {rootCauseSummary && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>Root Cause Summary — {rootCauseSummary.total_events} Total Fault Events</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={rootCauseSummary.summary} layout="vertical" margin={{ left: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
              <XAxis type="number" stroke="#9CA3AF" />
              <YAxis dataKey="root_cause" type="category" stroke="#9CA3AF" width={160} tick={{ fontSize: 12 }} />
              <Tooltip contentStyle={{ backgroundColor: '#0F1521', border: '1px solid #1F2937' }} />
              <Bar dataKey="event_count" fill="#F59E0B" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        {['T01', 'T06', 'T07', 'T11'].map(t => (
          <button key={t} onClick={() => setSelectedTurbine(t)} style={{
            padding: '8px 16px', borderRadius: '8px', border: '1px solid #1F2937', cursor: 'pointer',
            backgroundColor: selectedTurbine === t ? '#22D3EE' : '#0F1521',
            color: selectedTurbine === t ? '#0B0F17' : '#D1D5DB', fontWeight: 'bold',
          }}>{t}</button>
        ))}
      </div>

      {timeline && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>{selectedTurbine} Fault Timeline ({timeline.timeline.length} events)</h3>
          <div style={{ maxHeight: '260px', overflowY: 'auto' }}>
            <table style={{ width: '100%', color: '#D1D5DB', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ textAlign: 'left', color: '#9CA3AF', borderBottom: '1px solid #1F2937' }}>
                  <th style={{ padding: '6px' }}>Start</th><th>End</th><th>Root Cause</th><th>Min Health</th>
                </tr>
              </thead>
              <tbody>
                {timeline.timeline.map(ev => (
                  <tr key={ev.event_index} onClick={() => setSelectedEventIndex(ev.event_index)} style={{
                    cursor: 'pointer', borderBottom: '1px solid #1F2937',
                    backgroundColor: selectedEventIndex === ev.event_index ? '#111827' : 'transparent',
                  }}>
                    <td style={{ padding: '8px 6px' }}>{ev.start_time}</td>
                    <td>{ev.end_time}</td>
                    <td style={{ color: '#22D3EE' }}>{ev.probable_root_cause}</td>
                    <td style={{ color: ev.min_health_score < 20 ? '#EF4444' : '#F59E0B' }}>{ev.min_health_score.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {contribution && !contribution.error && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>Sensor Contribution — {contribution.probable_root_cause}</h3>
          <p style={{ color: '#9CA3AF', fontSize: '13px', marginTop: '-8px' }}>{contribution.turbine_id} · {contribution.start_time}</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={contribution.contributing_sensors} layout="vertical" margin={{ left: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
              <XAxis type="number" stroke="#9CA3AF" />
              <YAxis dataKey="sensor" type="category" stroke="#9CA3AF" width={180} tick={{ fontSize: 12 }} />
              <Tooltip contentStyle={{ backgroundColor: '#0F1521', border: '1px solid #1F2937' }} />
              <Bar dataKey="deviation" fill="#EF4444" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {trendComparison && !trendComparison.error && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>Sensor Trend — Before vs. During Fault</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trendComparison.trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
              <XAxis dataKey="Timestamp" stroke="#9CA3AF" tick={{ fontSize: 9 }} />
              <YAxis stroke="#9CA3AF" />
              <Tooltip contentStyle={{ backgroundColor: '#0F1521', border: '1px solid #1F2937' }} />
              <Legend />
              <ReferenceLine x={trendComparison.fault_start} stroke="#EF4444" strokeWidth={2} label={{ value: 'Fault Start', fill: '#EF4444', fontSize: 11, position: 'top' }} />
              <ReferenceLine x={trendComparison.fault_end} stroke="#9CA3AF" strokeDasharray="4 4" label={{ value: 'Fault End', fill: '#9CA3AF', fontSize: 11, position: 'top' }} />
              <Line type="monotone" dataKey="Gear_Oil_Temp_Avg" stroke="#22D3EE" dot={false} />
              <Line type="monotone" dataKey="Hyd_Oil_Temp_Avg" stroke="#F59E0B" dot={false} />
              <Line type="monotone" dataKey="Gen_Bear_Temp_Avg" stroke="#EF4444" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {trendComparison && trendComparison.error && (
        <div style={{ backgroundColor: '#1F1315', border: '1px solid #7F1D1D', borderRadius: '12px', padding: '16px', color: '#FCA5A5' }}>
          ⚠️ {trendComparison.error}
        </div>
      )}
    </div>
  )
}

export default Epic4FaultAnalysis