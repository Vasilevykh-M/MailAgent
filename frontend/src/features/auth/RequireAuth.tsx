import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { Card, PageShell, Skeleton } from '../../shared'
import { useAuth } from './useAuth'

type RequireAuthProps = {
  children: ReactNode
}

export function RequireAuth({ children }: RequireAuthProps) {
  const auth = useAuth()
  const location = useLocation()

  if (auth.status === 'checking') {
    return (
      <PageShell title="Mail Agent">
        <Card title="Проверка сессии">
          <Skeleton height={24} />
        </Card>
      </PageShell>
    )
  }

  if (auth.status === 'anonymous') {
    return <Navigate replace state={{ from: location }} to="/login" />
  }

  return children
}
