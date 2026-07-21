import { format } from 'date-fns'

export function formatDateTime(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return format(date, 'dd.MM.yyyy HH:mm')
}

export function formatDateForInput(value: Date): string {
  return format(value, 'yyyy-MM-dd')
}

export function formatDateInputDisplay(value: string): string {
  const [year, month, day] = value.split('-')

  if (!year || !month || !day) {
    return value
  }

  return `${day}.${month}.${year}`
}

export function dateInputToIsoStart(value: string): string | null {
  if (!value) {
    return null
  }

  const date = new Date(`${value}T00:00:00.000Z`)

  if (Number.isNaN(date.getTime())) {
    return null
  }

  return date.toISOString()
}

export function dateInputToIsoNextDay(value: string): string | null {
  if (!value) {
    return null
  }

  const date = new Date(`${value}T00:00:00.000Z`)

  if (Number.isNaN(date.getTime())) {
    return null
  }

  date.setUTCDate(date.getUTCDate() + 1)

  return date.toISOString()
}

export function formatInteger(value: number): string {
  return new Intl.NumberFormat('ru-RU').format(value)
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} Б`
  }

  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} КБ`
  }

  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`
}

export function formatConfidence(value: number | null | undefined): string {
  if (typeof value !== 'number') {
    return 'нет оценки'
  }

  return `${Math.round(value * 100)}%`
}

export function getConfidenceTone(value: number | null | undefined) {
  if (typeof value !== 'number') {
    return 'neutral'
  }

  if (value >= 0.8) {
    return 'success'
  }

  if (value >= 0.5) {
    return 'warning'
  }

  return 'danger'
}

export function formatNullable(value: string | null | undefined): string {
  return value?.trim() || '—'
}

export function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2)
}
