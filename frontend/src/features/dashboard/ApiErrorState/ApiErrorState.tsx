import { ApiError } from '../../../api'
import { ErrorState } from '../../../shared'

type ApiErrorStateProps = {
  title: string
  description: string
  error: unknown
  onRetry?: () => void
  retryLabel?: string
}

export function ApiErrorState({
  title,
  description,
  error,
  onRetry,
  retryLabel,
}: ApiErrorStateProps) {
  const requestId =
    error instanceof ApiError ? error.response?.request_id : null

  return (
    <ErrorState
      description={description}
      details={requestId ? `request_id: ${requestId}` : undefined}
      onRetry={onRetry}
      retryLabel={retryLabel}
      title={title}
    />
  )
}
