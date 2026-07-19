import { Navigate, Route, Routes } from 'react-router-dom'

import { DashboardPage } from '../features/dashboard/DashboardPage'

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/emails/:recordId" element={<DashboardPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
