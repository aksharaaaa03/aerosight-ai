function KpiCard({ title, value, subtitle, subtitleColor = '#9CA3AF' }) {
  return (
    <div style={{
      backgroundColor: '#0F1521',
      border: '1px solid #1F2937',
      borderRadius: '12px',
      padding: '20px',
      flex: 1,
      minWidth: '200px',
    }}>
      <div style={{ color: '#9CA3AF', fontSize: '14px', marginBottom: '8px' }}>
        {title}
      </div>
      <div style={{ color: 'white', fontSize: '32px', fontWeight: 'bold' }}>
        {value}
      </div>
      {subtitle && (
        <div style={{ color: subtitleColor, fontSize: '13px', marginTop: '6px' }}>
          {subtitle}
        </div>
      )}
    </div>
  )
}

export default KpiCard