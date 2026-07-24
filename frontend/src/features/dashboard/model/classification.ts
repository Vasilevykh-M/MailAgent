import type { BadgeTone } from '../../../shared'

export const classificationClasses = [
  { label: '3D-принтеры', value: '3D_PRINTERS' },
  { label: 'Химия', value: 'CHEMISTRY' },
  { label: 'Литьё', value: 'FOUNDRY' },
  { label: 'Печать форм', value: 'MOLD_PRINTING' },
  { label: 'Роботизированные ячейки', value: 'ROBOTIC_CELLS' },
  { label: 'Производственные линии', value: 'PRODUCTION_LINES' },
  { label: 'Станки', value: 'MACHINES' },
  { label: 'Техническое зрение', value: 'TECHNICAL_VISION' },
  { label: 'Другое оборудование', value: 'OTHER_EQUIPMENT' },
] as const

export type ClassificationClassCode =
  (typeof classificationClasses)[number]['value']

const classificationClassLabels = new Map<string, string>(
  classificationClasses.map(({ label, value }) => [value, label]),
)
const classificationClassCodes = new Set<string>(
  classificationClasses.map(({ value }) => value),
)

const classificationStatuses = [
  {
    label: 'Классифицировано',
    tone: 'success',
    value: 'classified',
  },
  {
    label: 'Новый проект',
    tone: 'info',
    value: 'new_project',
  },
  {
    label: 'Ручная проверка',
    tone: 'warning',
    value: 'manual_review',
  },
] as const satisfies ReadonlyArray<{
  label: string
  tone: BadgeTone
  value: string
}>

export type ClassificationStatus =
  (typeof classificationStatuses)[number]['value']

const classificationStatusesByValue = new Map<
  string,
  (typeof classificationStatuses)[number]
>(classificationStatuses.map((status) => [status.value, status]))

export function getClassificationClassLabel(
  classCode: string | null | undefined,
  className: string | null | undefined,
): string {
  return (
    className ||
    (classCode ? classificationClassLabels.get(classCode) : null) ||
    classCode ||
    'Без класса'
  )
}

export function isClassificationClassCode(
  value: string,
): value is ClassificationClassCode {
  return classificationClassCodes.has(value)
}

export function getClassificationStatusLabel(
  status: string | null | undefined,
): string {
  return (
    (status ? classificationStatusesByValue.get(status)?.label : null) ??
    'Нет классификации'
  )
}

export function getClassificationStatusTone(
  status: string | null | undefined,
): BadgeTone {
  return (
    (status ? classificationStatusesByValue.get(status)?.tone : null) ??
    'neutral'
  )
}

export const classFilterOptions = [
  ...classificationClasses,
  { label: 'Без класса', value: 'none' },
] as const

export const statusFilterOptions = [
  ...classificationStatuses.map(({ label, value }) => ({ label, value })),
  { label: 'Без данных статуса', value: 'uncached' },
] as const
