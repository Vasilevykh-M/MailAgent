import type { StatisticsResponse } from '../../../api'

export type ChartDatum = {
  name: string
  value: number
  color: string
}

export type ClassChartDatum = ChartDatum & {
  shortName: string
}

const statusLabels = new Map<string, string>([
  ['classified', 'Классифицировано'],
  ['new_project', 'Новые проекты'],
  ['manual_review', 'Ручная проверка'],
])

const statusColors = new Map<string, string>([
  ['classified', '#34d399'],
  ['new_project', '#60a5fa'],
  ['manual_review', '#fbbf24'],
])

const classColors = [
  '#22d3ee',
  '#60a5fa',
  '#a78bfa',
  '#34d399',
  '#fbbf24',
  '#fb7185',
  '#f472b6',
  '#38bdf8',
  '#c084fc',
]

export function buildStatusChartData(
  data: StatisticsResponse | undefined,
): ChartDatum[] {
  const grouped = new Map<string, number>()

  for (const item of data?.classifications ?? []) {
    const status = item.status ?? 'unknown'
    grouped.set(status, (grouped.get(status) ?? 0) + item.count)
  }

  return [...grouped.entries()]
    .map(([status, value]) => ({
      name: statusLabels.get(status) ?? 'Без статуса',
      value,
      color: statusColors.get(status) ?? '#94a3b8',
    }))
    .sort((left, right) => right.value - left.value)
}

export function buildClassChartData(
  data: StatisticsResponse | undefined,
): ClassChartDatum[] {
  return (data?.classifications ?? [])
    .filter((item) => item.class_name_ru)
    .map((item, index) => ({
      name: item.class_name_ru ?? 'Без класса',
      shortName: String(index + 1),
      value: item.count,
      color: classColors[index % classColors.length],
    }))
    .sort((left, right) => right.value - left.value)
}
