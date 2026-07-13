import { NavLink } from 'react-router-dom'

const navItems = [
  { path: '/', label: 'SCADA Data Management', epic: 'EPIC 1' },
  { path: '/health-monitoring', label: 'Turbine Health Monitoring', epic: 'EPIC 2' },
  { path: '/power-performance', label: 'Power Performance', epic: 'EPIC 3' },
  { path: '/fault-analysis', label: 'Fault & Root Cause', epic: 'EPIC 4' },
  { path: '/predictive-maintenance', label: 'Predictive Maintenance', epic: 'EPIC 5' },
  { path: '/operations', label: 'Operations Dashboard', epic: 'EPIC 6' },
  { path: '/business-impact', label: 'Business Impact Dashboard', epic: 'EPIC 7' },
]

function Sidebar() {
  return (
    <div style={{
      width: '260px',
      minHeight: '100vh',
      backgroundColor: '#0B0F17',
      borderRight: '1px solid #1F2937',
      padding: '24px 16px',
    }}>
      <div style={{ marginBottom: '32px', paddingLeft: '8px' }}>
        <div style={{ color: 'white', fontSize: '18px', fontWeight: 'bold' }}>SCADA Sentinel</div>
        <div style={{ color: '#9CA3AF', fontSize: '12px' }}>SCADA ANALYTICS</div>
      </div>

      {navItems.map(item => (
        <NavLink
          key={item.path}
          to={item.path}
          style={({ isActive }) => ({
            display: 'block',
            padding: '12px',
            borderRadius: '8px',
            marginBottom: '6px',
            textDecoration: 'none',
            color: isActive ? '#22D3EE' : '#D1D5DB',
            backgroundColor: isActive ? '#111827' : 'transparent',
            fontSize: '14px',
          })}
        >
          <div style={{ fontSize: '11px', color: '#6B7280', marginBottom: '2px' }}>{item.epic}</div>
          {item.label}
        </NavLink>
      ))}
    </div>
  )
}

export default Sidebar