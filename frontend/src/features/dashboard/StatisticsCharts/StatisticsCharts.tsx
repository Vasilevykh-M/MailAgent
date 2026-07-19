import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { StatisticsResponse } from '../../../api'
import { Card, EmptyState } from '../../../shared'
import { formatInteger } from '../../../shared'
import {
  buildClassChartData,
  buildStatusChartData,
  type ClassChartDatum,
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
          <div className={styles.skeletonChart} />
        </Card>
        <Card className={styles.chartCard} title="По классам" variant="muted">
          <div className={styles.skeletonChart} />
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
          <ResponsiveContainer height="100%" width="100%">
            <PieChart>
              <Pie
                data={statusData}
                dataKey="value"
                innerRadius={54}
                nameKey="name"
                outerRadius={82}
                paddingAngle={3}
              >
                {statusData.map((item) => (
                  <Cell fill={item.color} key={item.name} />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip />} />
            </PieChart>
          </ResponsiveContainer>
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
            <ResponsiveContainer height="100%" width="100%">
              <BarChart data={classData} layout="vertical" margin={barMargin}>
                <CartesianGrid
                  horizontal={false}
                  stroke="rgba(148, 163, 184, 0.18)"
                />
                <XAxis
                  allowDecimals={false}
                  axisLine={false}
                  tickLine={false}
                  type="number"
                />
                <YAxis
                  axisLine={false}
                  dataKey="name"
                  hide
                  tickLine={false}
                  type="category"
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                  {classData.map((item) => (
                    <Cell fill={item.color} key={item.name} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className={styles.noClassData}>Нет classified-классов</div>
          )}
        </div>
        {classData.length > 0 && <ClassLegend data={classData} />}
      </Card>
    </section>
  )
}

function ClassLegend({ data }: { data: ClassChartDatum[] }) {
  return (
    <ol className={styles.classLegend}>
      {data.map((item) => (
        <li key={item.name}>
          <span style={{ background: item.color }}>{item.shortName}</span>
          <p>{item.name}</p>
          <strong>{formatInteger(item.value)}</strong>
        </li>
      ))}
    </ol>
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

type ChartDatum = ReturnType<typeof buildStatusChartData>[number]

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

const barMargin = {
  top: 4,
  right: 12,
  bottom: 4,
  left: 8,
}
