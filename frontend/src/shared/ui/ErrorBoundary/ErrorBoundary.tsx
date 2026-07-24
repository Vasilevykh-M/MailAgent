import { Component, type ReactNode } from 'react'

import { ErrorState } from '../ErrorState'

type ErrorBoundaryProps = {
  children: ReactNode
}

type ErrorBoundaryState = {
  hasError: boolean
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = {
    hasError: false,
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  private reset = () => {
    this.setState({ hasError: false })
  }

  render() {
    if (this.state.hasError) {
      return (
        <ErrorState
          description="Обновите состояние приложения. Если ошибка повторится, перезагрузите страницу."
          onRetry={this.reset}
          title="Интерфейс временно недоступен"
        />
      )
    }

    return this.props.children
  }
}
