import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { LoginPage, RequireAuth } from '../features/auth'
import { DashboardPage } from '../features/dashboard/DashboardPage'
import { Card, PageShell, Skeleton } from '../shared'

const StatisticsPage = lazy(() =>
  import('../features/dashboard/StatisticsPage').then((module) => ({
    default: module.StatisticsPage,
  })),
)

function RouteLoading() {
  return (
    <PageShell title="Mail Agent">
      <Card title="Загрузка страницы">
        <Skeleton height={120} />
      </Card>
    </PageShell>
  )
}

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
            <Suspense fallback={<RouteLoading />}>
              <StatisticsPage />
            </Suspense>
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
