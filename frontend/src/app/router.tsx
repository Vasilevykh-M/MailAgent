import { Navigate, Route, Routes } from 'react-router-dom'

import { DashboardPage, StatisticsPage } from '../features'

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/emails/:recordId" element={<DashboardPage />} />
      <Route path="/statistics" element={<StatisticsPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
