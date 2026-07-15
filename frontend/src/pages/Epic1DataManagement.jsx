import { useEffect, useState } from 'react'
import axios from 'axios'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import KpiCard from '../components/KpiCard'

const API_BASE = `${import.meta.env.VITE_API_BASE}/api/epic1`

function Epic1DataManagement() {
  const [summary, setSummary] = useState(null)
  const [missingData, setMissingData] = useState(null)
  const [sensorDist, setSensorDist] = useState(null)
  const [processedSummary, setProcessedSummary] = useState(null)

  useEffect(() => {
    axios.get(`${API_BASE}/summary`).then(res => setSummary(res.data))
    axios.get(`${API_BASE}/missing-data-analysis`).then(res => setMissingData(res.data))
    axios.get(`${API_BASE}/sensor-distribution`).then(res => setSensorDist(res.data))
    axios.get(`${API_BASE}/processed-summary`).then(res => setProcessedSummary(res.data))
  }, [])


  const chartData = sensorDist
    ? sensorDist.bins.map((bin, i) => ({ bin, count: sensorDist.counts[i] }))
    : []

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0B0F17', padding: '32px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: 'white', marginBottom: '4px' }}>SCADA Sentinel</h1>
      <p style={{ color: '#9CA3AF', marginBottom: '24px' }}>Epic 1 — SCADA Data Management</p>

      {summary && (
        <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', flexWrap: 'wrap' }}>
          <KpiCard title="Total Records" value={summary.total_records.toLocaleString()} />
          <KpiCard
            title="Data Completeness"
            value={`${summary.data_completeness_pct}%`}
            subtitle={`${summary.imputed_values} values corrected`}
            subtitleColor="#F59E0B"
          />
          <KpiCard
            title="Non-Operational Records"
            value={summary.non_operational_records.toLocaleString()}
            subtitle={`${summary.non_operational_pct}% of data`}
          />
          <KpiCard title="Imputed Values" value={summary.imputed_values} />
        </div>
      )}

      {sensorDist && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>Wind Speed Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
              <XAxis dataKey="bin" stroke="#9CA3AF" />
              <YAxis stroke="#9CA3AF" />
              <Tooltip contentStyle={{ backgroundColor: '#0F1521', border: '1px solid #1F2937' }} />
              <Bar dataKey="count" fill="#22D3EE" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {missingData && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px', marginTop: '24px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>Data Quality Issues Found & Fixed</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={missingData.breakdown} layout="vertical" margin={{ left: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
              <XAxis type="number" stroke="#9CA3AF" />
              <YAxis dataKey="issue" type="category" stroke="#9CA3AF" width={220} tick={{ fontSize: 12 }} />
              <Tooltip contentStyle={{ backgroundColor: '#0F1521', border: '1px solid #1F2937' }} />
              <Bar dataKey="count" fill="#F59E0B" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {processedSummary && (
        <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px', marginTop: '24px' }}>
          <h3 style={{ color: 'white', marginTop: 0 }}>Processed Data Summary</h3>
          <div style={{ display: 'flex', gap: '32px', color: '#D1D5DB', flexWrap: 'wrap' }}>
            <div>
              <div style={{ color: '#9CA3AF', fontSize: '13px' }}>Full Dataset</div>
              <div>{processedSummary.full_dataset.rows.toLocaleString()} rows × {processedSummary.full_dataset.columns} columns</div>
            </div>
            <div>
              <div style={{ color: '#9CA3AF', fontSize: '13px' }}>Training-Ready Dataset</div>
              <div>{processedSummary.training_ready_dataset.rows.toLocaleString()} rows × {processedSummary.training_ready_dataset.columns} columns</div>
            </div>
            <div>
              <div style={{ color: '#9CA3AF', fontSize: '13px' }}>Date Range</div>
              <div>{processedSummary.full_dataset.date_range_start.split(' ')[0]} to {processedSummary.full_dataset.date_range_end.split(' ')[0]}</div>
            </div>
          </div>

          <h4 style={{ color: 'white', marginTop: '20px', marginBottom: '8px' }}>Records Per Turbine</h4>
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
            {Object.entries(processedSummary.records_per_turbine).map(([turbine, count]) => (
              <div key={turbine} style={{ backgroundColor: '#111827', padding: '10px 16px', borderRadius: '8px' }}>
                <span style={{ color: '#22D3EE', fontWeight: 'bold' }}>{turbine}</span>
                <span style={{ color: '#9CA3AF', marginLeft: '8px' }}>{count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default Epic1DataManagement