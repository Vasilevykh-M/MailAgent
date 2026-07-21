import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

import type { StatisticsResponse } from '../../../api'
import { Card, EmptyState, Skeleton } from '../../../shared'
import { formatInteger } from '../../../shared'
import {
  buildClassChartData,
  buildStatusChartData,
  type ChartDatum,
} from './chartData'

import styles from './StatisticsCharts.module.css'

type StatisticsChartsProps = {
  data: StatisticsResponse | undefined
  isLoading: boolean
  isError: boolean
}

export function StatisticsCharts({
  data,
  isLoading,
  isError,
}: StatisticsChartsProps) {
  if (isLoading) {
    return (
      <section className={styles.grid} aria-label="Графики статистики">
        <Card className={styles.chartCard} title="По статусам" variant="muted">
          <Skeleton height={340} />
        </Card>
        <Card className={styles.chartCard} title="По классам" variant="muted">
          <Skeleton height={340} />
        </Card>
      </section>
    )
  }

  if (isError) {
    return null
  }

  const statusData = buildStatusChartData(data)
  const classData = buildClassChartData(data)

  if (statusData.length === 0 && classData.length === 0) {
    return (
      <EmptyState
        description="За выбранный период нет данных для построения графиков."
        title="Графики пустые"
      />
    )
  }

  return (
    <section className={styles.grid} aria-label="Графики статистики">
      <Card
        className={styles.chartCard}
        description="Распределение писем по статусам классификации."
        title="По статусам"
        variant="muted"
      >
        <div className={styles.chart}>
          <DonutChart data={statusData} />
        </div>
        <Legend data={statusData} />
      </Card>

      <Card
        className={styles.chartCard}
        description="Топ классов среди классифицированных писем."
        title="По классам"
        variant="muted"
      >
        <div className={styles.chart}>
          {classData.length > 0 ? (
            <DonutChart data={classData} />
          ) : (
            <div className={styles.noClassData}>Нет classified-классов</div>
          )}
        </div>
        {classData.length > 0 && <Legend data={classData} />}
      </Card>
    </section>
  )
}

function DonutChart({ data }: { data: ChartDatum[] }) {
  return (
    <ResponsiveContainer height="100%" width="100%">
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          innerRadius="56%"
          nameKey="name"
          outerRadius="82%"
          paddingAngle={2}
        >
          {data.map((item) => (
            <Cell fill={item.color} key={item.name} />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip />} />
      </PieChart>
    </ResponsiveContainer>
  )
}

function Legend({ data }: { data: ChartDatum[] }) {
  return (
    <ul className={styles.legend}>
      {data.map((item) => (
        <li key={item.name}>
          <span style={{ background: item.color }} />
          {item.name}: {formatInteger(item.value)}
        </li>
      ))}
    </ul>
  )
}

function ChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload?.length) {
    return null
  }

  const item = payload[0]
  const name = String(item.payload?.name ?? label ?? item.name ?? '')
  const value = Number(item.value ?? 0)

  return (
    <div className={styles.tooltip}>
      <p>{name}</p>
      <strong>{formatInteger(value)}</strong>
    </div>
  )
}

type ChartTooltipProps = {
  active?: boolean
  label?: string | number
  payload?: Array<{
    name?: string | number
    value?: string | number
    payload?: {
      name?: string
    }
  }>
}
