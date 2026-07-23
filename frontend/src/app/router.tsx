import { Navigate, Route, Routes } from 'react-router-dom'

import { DashboardPage, StatisticsPage } from '../features'
import { LoginPage, RequireAuth } from '../features/auth'

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <DashboardPage />
          </RequireAuth>
        }
      />
      <Route
        path="/emails/:recordId"
        element={
          <RequireAuth>
            <DashboardPage />
          </RequireAuth>
        }
      />
      <Route
        path="/statistics"
        element={
          <RequireAuth>
            <StatisticsPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
