import { useEffect, useState } from 'react'
import KpiCard from '../components/KpiCard'

const API_BASE = `${import.meta.env.VITE_API_BASE}/business-impact`

function formatEur(value) {
  return new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(value)
}

function riskColor(level) {
  if (level === 'High') return '#F87171'
  if (level === 'Medium') return '#FBBF24'
  return '#34D399'
}

function Epic7BusinessImpact() {
  const [summary, setSummary] = useState(null)
  const [energyLoss, setEnergyLoss] = useState(null)
  const [repairCost, setRepairCost] = useState(null)
  const [ranking, setRanking] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function fetchAll() {
      try {
        const [summaryRes, energyRes, repairRes, rankingRes] = await Promise.all([
          fetch(`${API_BASE}/fleet-performance-summary`),
          fetch(`${API_BASE}/energy-loss-cost`),
          fetch(`${API_BASE}/fault-repair-cost`),
          fetch(`${API_BASE}/asset-risk-ranking`),
        ])
        setSummary(await summaryRes.json())
        setEnergyLoss(await energyRes.json())
        setRepairCost(await repairRes.json())
        setRanking((await rankingRes.json()).ranking)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    fetchAll()
  }, [])

  if (loading) return <div style={{ color: 'white', padding: '24px' }}>Loading business impact dashboard...</div>
  if (error) return <div style={{ color: '#F87171', padding: '24px' }}>Error: {error}</div>

  return (
    <div style={{ padding: '24px' }}>
      <h1 style={{ color: 'white', fontSize: '22px', marginBottom: '4px' }}>
        Business Impact Dashboard
      </h1>
      <div style={{ color: '#6B7280', fontSize: '13px', marginBottom: '24px' }}>
        Cost figures combine real measured data (energy loss, fault durations) with external
        industry-benchmark assumptions (€0.05/kWh energy price, component repair cost tiers) —
        not directly measured from SCADA data. See notes below for sourcing.
      </div>

      {/* Fleet KPIs */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '32px', flexWrap: 'wrap' }}>
        <KpiCard
          title="Total Business Impact"
          value={formatEur(summary.total_business_impact_eur)}
          subtitle="Repair cost + energy revenue loss"
        />
        <KpiCard
          title="Total Energy Lost"
          value={`${summary.total_energy_loss_kwh.toLocaleString()} kWh`}
          subtitle={formatEur(summary.total_revenue_loss_eur) + ' revenue impact'}
        />
        <KpiCard
          title="Confirmed Failures"
          value={summary.confirmed_failures}
          subtitleColor="#F87171"
          subtitle={`${summary.routine_anomaly_events} routine anomaly events`}
        />
        <KpiCard
          title="Avg Fleet Health"
          value={summary.avg_fleet_health}
          subtitle={`${summary.total_turbines} turbines, ${summary.fleet_status_breakdown['Healthy'] || 0} healthy`}
        />
      </div>

      {/* Asset Risk Ranking */}
      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ color: 'white', fontSize: '16px', marginBottom: '4px' }}>
          Asset Risk Ranking
        </h2>
        <div style={{ color: '#6B7280', fontSize: '12px', marginBottom: '12px' }}>
          Ranked by total historical cost incurred (repair + energy loss); Epic 5's forward-looking
          forecast rank shown alongside for context
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #1F2937' }}>
              {['Rank', 'Turbine', 'Historical Cost', 'Forecast Rank', 'Forecast Risk', 'Likely Component'].map(h => (
                <th key={h} style={{ textAlign: 'left', color: '#6B7280', fontSize: '11px', padding: '8px 12px' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ranking.map((r) => (
              <tr key={r.turbine_id} style={{ borderBottom: '1px solid #1F2937' }}>
                <td style={{ color: '#D1D5DB', fontSize: '13px', padding: '10px 12px' }}>{r.risk_rank}</td>
                <td style={{ color: 'white', fontSize: '13px', fontWeight: 'bold', padding: '10px 12px' }}>{r.turbine_id}</td>
                <td style={{ color: 'white', fontSize: '13px', fontWeight: 'bold', padding: '10px 12px' }}>{formatEur(r.total_historical_cost_eur)}</td>
                <td style={{ color: '#D1D5DB', fontSize: '13px', padding: '10px 12px' }}>#{r.forecast_priority_rank}</td>
                <td style={{ padding: '10px 12px' }}>
                  <span style={{ color: riskColor(r.risk_level), backgroundColor: `${riskColor(r.risk_level)}22`, fontSize: '11px', fontWeight: 'bold', padding: '3px 8px', borderRadius: '6px' }}>
                    {r.risk_level}
                  </span>
                </td>
                <td style={{ color: '#D1D5DB', fontSize: '13px', padding: '10px 12px' }}>{r.likely_component}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Fault Repair Cost Breakdown */}
      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ color: 'white', fontSize: '16px', marginBottom: '4px' }}>
          Maintenance & Failure Cost Breakdown
        </h2>
        <div style={{ color: '#6B7280', fontSize: '12px', marginBottom: '12px' }}>
          Fleet total: {formatEur(repairCost.fleet_total_repair_cost_eur)} —{' '}
          {repairCost.total_confirmed_failures} confirmed failures (matched to real failure logbook),{' '}
          {repairCost.total_routine_events} routine anomaly detections
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #1F2937' }}>
              {['Turbine', 'Total Faults', 'Confirmed Failures', 'Repair Cost'].map(h => (
                <th key={h} style={{ textAlign: 'left', color: '#6B7280', fontSize: '11px', padding: '8px 12px' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {repairCost.per_turbine.map((t) => (
              <tr key={t.turbine_id} style={{ borderBottom: '1px solid #1F2937' }}>
                <td style={{ color: 'white', fontSize: '13px', fontWeight: 'bold', padding: '10px 12px' }}>{t.turbine_id}</td>
                <td style={{ color: '#D1D5DB', fontSize: '13px', padding: '10px 12px' }}>{t.fault_count}</td>
                <td style={{ color: t.confirmed_failure_count > 0 ? '#F87171' : '#6B7280', fontSize: '13px', padding: '10px 12px' }}>
                  {t.confirmed_failure_count}
                </td>
                <td style={{ color: 'white', fontSize: '13px', fontWeight: 'bold', padding: '10px 12px' }}>{formatEur(t.total_repair_cost_eur)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Energy Loss Breakdown */}
      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ color: 'white', fontSize: '16px', marginBottom: '4px' }}>
          Energy Loss Breakdown
        </h2>
        <div style={{ color: '#6B7280', fontSize: '12px', marginBottom: '12px' }}>
          Fleet total: {summary.total_energy_loss_kwh.toLocaleString()} kWh lost ({formatEur(energyLoss.fleet_total_revenue_loss_eur)} at
          €{energyLoss.energy_price_eur_per_kwh}/kWh wholesale reference price) — from sustained underperformance episodes only (Epic 3), not total energy production
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #1F2937' }}>
              {['Turbine', 'Alert Count', 'Energy Lost', 'Revenue Impact'].map(h => (
                <th key={h} style={{ textAlign: 'left', color: '#6B7280', fontSize: '11px', padding: '8px 12px' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {energyLoss.per_turbine.map((t) => (
              <tr key={t.turbine_id} style={{ borderBottom: '1px solid #1F2937' }}>
                <td style={{ color: 'white', fontSize: '13px', fontWeight: 'bold', padding: '10px 12px' }}>{t.turbine_id}</td>
                <td style={{ color: '#D1D5DB', fontSize: '13px', padding: '10px 12px' }}>{t.alert_count}</td>
                <td style={{ color: '#D1D5DB', fontSize: '13px', padding: '10px 12px' }}>{t.total_energy_loss_kwh.toLocaleString()} kWh</td>
                <td style={{ color: 'white', fontSize: '13px', fontWeight: 'bold', padding: '10px 12px' }}>{formatEur(t.estimated_revenue_loss_eur)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Assumptions note */}
      <div style={{ backgroundColor: '#0F1521', border: '1px solid #1F2937', borderRadius: '12px', padding: '16px 20px', marginBottom: '32px' }}>
        <h3 style={{ color: 'white', fontSize: '13px', marginTop: 0, marginBottom: '8px' }}>Cost Assumptions (external reference data)</h3>
        <div style={{ color: '#9CA3AF', fontSize: '12px', lineHeight: '1.6' }}>
          • Energy price: €0.05/kWh — representative European onshore wind wholesale rate, cross-checked against real Portugal day-ahead prices (~€38-88/MWh observed)<br/>
          • Major component repair (Gearbox/Generator/Transformer): €230,000 per confirmed failure — gearbox figure well-sourced from industry benchmarks; applied to other major components as a proxy (weaker assumption)<br/>
          • Routine anomaly investigation: €1,000 per event — based on published electrical inspection cost ranges ($500-$1,500)<br/>
          • Only 11 of 989 detected fault events are matched to real, logged failures; the remaining ~973 are unconfirmed anomaly detections, costed at a much lower rate accordingly
        </div>
      </div>
    </div>
  )
}

export default Epic7BusinessImpact