import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Epic1DataManagement from './pages/Epic1DataManagement'
import Epic2HealthMonitoring from './pages/Epic2HealthMonitoring'
import Epic3PowerPerformance from './pages/Epic3PowerPerformance'
import Epic4FaultAnalysis from './pages/Epic4FaultAnalysis'
import Epic5PredictiveMaintenance from './pages/Epic5PredictiveMaintenance'
import Epic6OperationsDashboard from './pages/Epic6OperationsDashboard'
import Epic7BusinessImpact from './pages/Epic7BusinessImpact'
function App() {
  return (
    <BrowserRouter>
      <div style={{ display: 'flex' }}>
        <Sidebar />
        <div style={{ flex: 1, backgroundColor: '#0B0F17', minHeight: '100vh' }}>
          <Routes>
            <Route path="/" element={<Epic1DataManagement />} />
            <Route path="/health-monitoring" element={<Epic2HealthMonitoring />} />
            <Route path="/power-performance" element={<Epic3PowerPerformance />} />
            <Route path="/fault-analysis" element={<Epic4FaultAnalysis />} />
            <Route path="/predictive-maintenance" element={<Epic5PredictiveMaintenance />} />
            <Route path="/operations" element={<Epic6OperationsDashboard />} />
            <Route path="/business-impact" element={<Epic7BusinessImpact />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  )
}

export default App