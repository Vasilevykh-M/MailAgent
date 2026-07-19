import type { BadgeTone } from '../../../shared'

export function getClassificationStatusLabel(
  status: string | null | undefined,
) {
  switch (status) {
    case 'classified':
      return 'Классифицировано'
    case 'new_project':
      return 'Новый проект'
    case 'manual_review':
      return 'Ручная проверка'
    default:
      return 'Нет классификации'
  }
}

export function getClassificationStatusTone(
  status: string | null | undefined,
): BadgeTone {
  switch (status) {
    case 'classified':
      return 'success'
    case 'new_project':
      return 'info'
    case 'manual_review':
      return 'warning'
    default:
      return 'neutral'
  }
}
