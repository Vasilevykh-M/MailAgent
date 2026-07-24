import { ErrorBoundary } from '../shared'
import { AppProviders } from './providers'
import { AppRouter } from './router'

export function App() {
  return (
    <ErrorBoundary>
      <AppProviders>
        <AppRouter />
      </AppProviders>
    </ErrorBoundary>
  )
}
