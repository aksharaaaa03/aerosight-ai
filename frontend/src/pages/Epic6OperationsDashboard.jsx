import { useEffect, useState } from 'react'
import axios from 'axios'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import KpiCard from '../components/KpiCard'

const API_BASE = 'http://localhost:8000/operations'

function statusColor(status) {
  if (status === 'Healthy') return '#34D399'
  if (status === 'Warning') return '#FBBF24'
  if (status === 'Critical') return '#F87171'
  return '#9CA3AF'
}

const CATEGORY_SENSORS = {
  'Generator Bearing': ['Gen_Bear_Temp_Avg', 'Gen_Bear2_Temp_Avg'],
  'Generator': ['Gen_Phase1_Temp_Avg', 'Gen_Phase2_Temp_Avg', 'Gen_Phase3_Temp_Avg'],
  'Gearbox': ['Gear_Bear_Temp_Avg', 'Gear_Oil_Temp_Avg'],
  'Hydraulic Group': ['Hyd_Oil_Temp_Avg'],
  'Transformer': ['HVTrafo_Phase1_Temp_Avg', 'HVTrafo_Phase2_Temp_Avg', 'HVTrafo_Phase3_Temp_Avg'],
  'Pitch/Control System': ['Blds_PitchAngle_Avg'],
  'Nacelle (General)': ['Nac_Temp_Avg'],
  'Grid/Electrical': ['Grd_Prod_ReactPwr_Avg'],
  'Drivetrain': ['Gen_RPM_Avg', 'Rtr_RPM_Avg'],
}

const ALL_TURBINES = ['T01', 'T06', 'T07', 'T11']

function Epic6OperationsDashboard() {
  const [fleetOverview, setFleetOverview] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [events, setEvents] = useState([])
  const [predictions, setPredictions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [sensorTurbine, setSensorTurbine] = useState('T01')
  const [sensorCategory, setSensorCategory] = useState('Gearbox')
  const [sensorTrend, setSensorTrend] = useState(null)

  const [filterTurbine, setFilterTurbine] = useState('All')
  const [filterStartDate, setFilterStartDate] = useState('2016-01-01')
  const [filterEndDate, setFilterEndDate] = useState('2017-12-31')

  useEffect(() => {
    async function fetchStatic() {
      try {
        const [overviewRes, alertsRes, predictionsRes] = await Promise.all([
          fetch(`${API_BASE}/fleet-overview`),
          fetch(`${API_BASE}/active-alerts`),
          fetch(`${API_BASE}/prediction-summary`),
        ])
        setFleetOverview(await overviewRes.json())
        setAlerts((await alertsRes.json()).alerts)
        setPredictions((await predictionsRes.json()).predictions)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    fetchStatic()
  }, [])

  useEffect(() => {
    const params = new URLSearchParams({
      start_date: filterStartDate,
      end_date: filterEndDate,
      limit: '50',
    })
    if (filterTurbine !== 'All') params.set('turbine_id', filterTurbine)

    fetch(`${API_BASE}/recent-events?${params.toString()}`)
      .then(res => res.json())
      .then(data => setEvents(data.events))
      .catch(err => setError(err.message))
  }, [filterTurbine, filterStartDate, filterEndDate])

  useEffect(() => {
    const sensors = CATEGORY_SENSORS[sensorCategory].join(',')
    axios.get(`${API_BASE}/sensor-trends/${sensorTurbine}?sensors=${sensors}&start_date=2017-12-01&end_date=2017-12-31&resample=h`)
      .then(res => setSensorTrend(res.data))
  }, [sensorTurbine, sensorCategory])

  if (loading) return <div style={{ color: 'white', padding: '24px' }}>Loading operations dashboard...</div>
  if (error) return <div style={{ color: '#F87171', padding: '24px' }}>Error: {error}</div>

  const criticalCount = fleetOverview.status_breakdown['Critical'] || 0
  const warningCount = fleetOverview.status_breakdown['Warning'] || 0
  const healthyCount = fleetOverview.status_breakdown['Healthy'] || 0

  const filteredAlerts = alerts.filter(a => filterTurbine === 'All' || a.turbine_id === filterTurbine)
  const filteredPredictions = predictions.filter(p => filterTurbine === 'All' || p.turbine_id === filterTurbine)
  const filteredHealthEntries = Object.entries(fleetOverview.per_turbine_health).filter(
    ([id]) => filterTurbine === 'All' || id === filterTurbine
  )

  return (
    <div style={{ padding: '24px' }}>
      <h1 style={{ color: 'white', fontSize: '22px', marginBottom: '4px' }}>
        Operations Dashboard
      </h1>
      <div style={{ color: '#6B7280', fontSize: '13px', marginBottom: '16px' }}>
        As of {fleetOverview.as_of} (dataset's latest available timestamp)
      </div>

      <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap' }}>
        <select
          value={filterTurbine}
          onChange={e => setFilterTurbine(e.target.value)}
          style={{ backgroundColor: '#0F1521', color: 'white', border: '1px solid #1F2937', borderRadius: '6px', padding: '6px 10px', fontSize: '13px' }}
        >
          <option value="All">All Turbines</option>
          {ALL_TURBINES.map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <input
          type="date"
          value={filterStartDate}
          min="2016-01-01"
          max="2017-12-31"
          onChange={e => setFilterStartDate(e.target.value)}
          style={{ backgroundColor: '#0F1521', color: 'white', border: '1px solid #1F2937', borderRadius: '6px', padding: '6px 10px', fontSize: '13px' }}
        />
        <span style={{ color: '#6B7280', fontSize: '13px' }}>to</span>
        <input
          type="date"
          value={filterEndDate}
          min="2016-01-01"
          max="2017-12-31"
          onChange={e => setFilterEndDate(e.target.value)}
          style={{ backgroundColor: '#0F1521', color: 'white', border: '1px solid #1F2937', borderRadius: '6px', padding: '6px 10px', fontSize: '13px' }}
        />
        <span style={{ color: '#6B7280', fontSize: '12px' }}>
          (Time period filter applies to Recent Events; turbine filter applies to Live Health, Active Alerts, Recent Events, and Prediction Summary)
        </span>
      </div>

      <div style={{ display: 'flex', gap: '16px', marginBottom: '32px', flexWrap: 'wrap' }}>
        <KpiCard
          title="Total Turbines"
          value={fleetOverview.total_turbines}
        />
        <KpiCard
          title="Avg Fleet Health"
          value={fleetOverview.avg_fleet_health}
          subtitle="3-day rolling average"
        />
        <KpiCard
          title="Healthy"
          value={healthyCount}
          subtitleColor="#34D399"
          subtitle={`${healthyCount} of ${fleetOverview.total_turbines} turbines`}
        />
        <KpiCard
          title="Warning / Critical"
          value={warningCount + criticalCount}
          subtitleColor={criticalCount > 0 ? '#F87171' : '#FBBF24'}
          subtitle={criticalCount > 0 ? `${criticalCount} critical` : warningCount > 0 ? `${warningCount} warning` : 'None'}
        />
      </div>

      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ color: 'white', fontSize: '16px', marginBottom: '12px' }}>
          Live Health Status
        </h2>
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
          {filteredHealthEntries.map(([turbineId, health]) => {
            const status = fleetOverview.per_turbine_status[turbineId]
            return (
              <div
                key={turbineId}
                style={{
                  backgroundColor: '#0F1521',
                  border: `1px solid ${statusColor(status)}33`,
                  borderRadius: '12px',
                  padding: '16px 20px',
                  minWidth: '160px',
                }}
              >
                <div style={{ color: 'white', fontSize: '16px', fontWeight: 'bold', marginBottom: '4px' }}>
                  {turbineId}
                </div>
                <div style={{ color: statusColor(status), fontSize: '24px', fontWeight: 'bold' }}>
                  {health}
                </div>
                <div style={{ color: statusColor(status), fontSize: '12px', marginTop: '4px' }}>
                  {status}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ color: 'white', fontSize: '16px', marginBottom: '4px' }}>
          Active Alerts
        </h2>
        <div style={{ color: '#6B7280', fontSize: '12px', marginBottom: '12px' }}>
          {filteredAlerts.length} alert{filteredAlerts.length !== 1 ? 's' : ''} in the last 14 days
        </div>

        {filteredAlerts.length > 0 && (
          <div style={{ marginBottom: '16px' }}>
            <ResponsiveContainer width="100%" height={140}>
              <BarChart
                data={ALL_TURBINES
                  .filter(t => filterTurbine === 'All' || t === filterTurbine)
                  .map(t => ({
                    turbine_id: t,
                    count: alerts.filter(a => a.turbine_id === t).length,
                  }))}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
                <XAxis dataKey="turbine_id" stroke="#9CA3AF" tick={{ fontSize: 12 }} />
                <YAxis stroke="#9CA3AF" allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ backgroundColor: '#0F1521', border: '1px solid #1F2937' }} />
                <Bar dataKey="count" name="Alerts" fill="#FB923C" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {filteredAlerts.length === 0 ? (
          <div style={{ color: '#6B7280', fontSize: '14px' }}>No active alerts.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {filteredAlerts.map((alert, i) => {
              const typeLabel = {
                HEALTH_CRITICAL: 'Health Critical',
                FAULT_EVENT: 'Fault Event',
                PERFORMANCE_ALERT: 'Performance',
                HIGH_RISK_FORECAST: 'High Risk Forecast',
              }[alert.type] || alert.type

              const typeColor = {
                HEALTH_CRITICAL: '#F87171',
                FAULT_EVENT: '#FB923C',
                PERFORMANCE_ALERT: '#FBBF24',
                HIGH_RISK_FORECAST: '#A78BFA',
              }[alert.type] || '#9CA3AF'

              return (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    backgroundColor: '#0F1521',
                    border: '1px solid #1F2937',
                    borderRadius: '8px',
                    padding: '12px 16px',
                  }}
                >
                  <span
                    style={{
                      color: typeColor,
                      backgroundColor: `${typeColor}22`,
                      fontSize: '11px',
                      fontWeight: 'bold',
                      padding: '3px 8px',
                      borderRadius: '6px',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {typeLabel}
                  </span>
                  <span style={{ color: 'white', fontSize: '13px', fontWeight: 'bold', minWidth: '32px' }}>
                    {alert.turbine_id}
                  </span>
                  <span style={{ color: '#D1D5DB', fontSize: '13px', flex: 1 }}>
                    {alert.detail}
                  </span>
                  <span style={{ color: '#6B7280', fontSize: '12px' }}>
                    {alert.timestamp}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ color: 'white', fontSize: '16px', marginBottom: '4px' }}>
          Recent Events
        </h2>
        <div style={{ color: '#6B7280', fontSize: '12px', marginBottom: '12px' }}>
          Operational history, most recent first ({filterStartDate} to {filterEndDate}
          {filterTurbine !== 'All' ? `, ${filterTurbine}` : ''})
        </div>
        {events.length === 0 ? (
          <div style={{ color: '#6B7280', fontSize: '14px' }}>No recorded events for this selection.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {events.map((event, i) => {
              const typeColor = event.type === 'FAULT_EVENT' ? '#FB923C' : '#FBBF24'
              const typeLabel = event.type === 'FAULT_EVENT' ? 'Fault' : 'Performance'
              return (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '10px 16px',
                    borderBottom: '1px solid #1F2937',
                  }}
                >
                  <span
                    style={{
                      color: typeColor,
                      fontSize: '11px',
                      fontWeight: 'bold',
                      minWidth: '80px',
                    }}
                  >
                    {typeLabel}
                  </span>
                  <span style={{ color: 'white', fontSize: '13px', fontWeight: 'bold', minWidth: '32px' }}>
                    {event.turbine_id}
                  </span>
                  <span style={{ color: '#D1D5DB', fontSize: '13px', flex: 1 }}>
                    {event.detail}
                  </span>
                  <span style={{ color: '#6B7280', fontSize: '12px' }}>
                    {event.start_time} → {event.end_time}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ color: 'white', fontSize: '16px', marginBottom: '4px' }}>
          Prediction Summary
        </h2>
        <div style={{ color: '#6B7280', fontSize: '12px', marginBottom: '12px' }}>
          Epic 5 forecast, sorted by priority
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #1F2937' }}>
              {['Rank', 'Turbine', 'Risk', 'Likely Component', 'Recommended Action'].map(h => (
                <th key={h} style={{ textAlign: 'left', color: '#6B7280', fontSize: '11px', padding: '8px 12px' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredPredictions.map((p) => {
              const riskColor = p.risk_level === 'High' ? '#F87171' : p.risk_level === 'Medium' ? '#FBBF24' : '#34D399'
              return (
                <tr key={p.turbine_id} style={{ borderBottom: '1px solid #1F2937' }}>
                  <td style={{ color: '#D1D5DB', fontSize: '13px', padding: '10px 12px' }}>{p.priority_rank}</td>
                  <td style={{ color: 'white', fontSize: '13px', fontWeight: 'bold', padding: '10px 12px' }}>{p.turbine_id}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{ color: riskColor, backgroundColor: `${riskColor}22`, fontSize: '11px', fontWeight: 'bold', padding: '3px 8px', borderRadius: '6px' }}>
                      {p.risk_level}
                    </span>
                  </td>
                  <td style={{ color: '#D1D5DB', fontSize: '13px', padding: '10px 12px' }}>{p.likely_component}</td>
                  <td style={{ color: '#D1D5DB', fontSize: '13px', padding: '10px 12px' }}>{p.recommended_action}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px', marginBottom: '32px' }}>
        <h3 style={{ color: 'white', marginTop: 0 }}>Sensor Trends</h3>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
          {ALL_TURBINES.map(t => (
            <button
              key={t}
              onClick={() => setSensorTurbine(t)}
              style={{
                cursor: 'pointer',
                backgroundColor: sensorTurbine === t ? '#111827' : '#0B0F17',
                border: `1px solid ${sensorTurbine === t ? '#22D3EE' : '#1F2937'}`,
                borderRadius: '8px',
                padding: '8px 16px',
                color: sensorTurbine === t ? '#22D3EE' : '#D1D5DB',
                fontSize: '13px',
              }}
            >
              {t}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
          {Object.keys(CATEGORY_SENSORS).map(cat => (
            <button
              key={cat}
              onClick={() => setSensorCategory(cat)}
              style={{
                cursor: 'pointer',
                backgroundColor: sensorCategory === cat ? '#111827' : 'transparent',
                border: `1px solid ${sensorCategory === cat ? '#22D3EE' : '#1F2937'}`,
                borderRadius: '6px',
                padding: '6px 12px',
                color: sensorCategory === cat ? '#22D3EE' : '#9CA3AF',
                fontSize: '12px',
              }}
            >
              {cat}
            </button>
          ))}
        </div>

        {sensorTrend && sensorTrend.row_count > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
              <XAxis
                dataKey="timestamp"
                type="category"
                allowDuplicatedCategory={false}
                stroke="#9CA3AF"
                tick={{ fontSize: 10 }}
              />
              <YAxis stroke="#9CA3AF" />
              <Tooltip contentStyle={{ backgroundColor: '#0F1521', border: '1px solid #1F2937' }} />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
              {Object.entries(sensorTrend.sensors).map(([sensorName, data], i) => {
                const colors = ['#22D3EE', '#F59E0B', '#A78BFA']
                const chartData = data.timestamps.map((ts, idx) => ({ timestamp: ts, value: data.values[idx] }))
                return (
                  <Line
                    key={sensorName}
                    data={chartData}
                    type="monotone"
                    dataKey="value"
                    name={sensorName}
                    stroke={colors[i % colors.length]}
                    strokeWidth={2}
                    dot={false}
                  />
                )
              })}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ color: '#6B7280', fontSize: '13px' }}>No data for this selection.</div>
        )}
      </div>
    </div>
  )
}

export default Epic6OperationsDashboard