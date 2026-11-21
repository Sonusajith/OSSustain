import type { RepositoryMetrics } from '../../api/client'

interface MetricDefinition {
  key: string
  label: string
  unit: 'count' | 'fraction' | 'coefficient' | 'hours'
}

function valueFor(point: RepositoryMetrics[number], key: string): number | null {
  const value = point.metrics[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function formatValue(value: number | null, unit: MetricDefinition['unit']): string {
  if (value === null) return '—'
  if (unit === 'count') return new Intl.NumberFormat().format(value)
  if (unit === 'fraction') return `${(value * 100).toFixed(1)}%`
  if (unit === 'coefficient') return value.toFixed(3)
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value)} h`
}

function chartCoordinates(values: (number | null)[]): { x: number; y: number }[] {
  const known = values.filter((value): value is number => value !== null)
  if (!known.length) return []
  const min = Math.min(...known)
  const max = Math.max(...known)
  return values.map((value, index) => ({
    x: values.length <= 1 ? 160 : 8 + (index * 304) / (values.length - 1),
    y: value === null ? Number.NaN : max === min ? 25 : 42 - ((value - min) / (max - min)) * 34,
  }))
}

export function MetricHistoryChart({ points, metric }: { points: RepositoryMetrics; metric: MetricDefinition }) {
  const values = points.map((point) => valueFor(point, metric.key))
  const coordinates = chartCoordinates(values)
  const observed = values.filter((value) => value !== null).length
  const knownValues = values.filter((value): value is number => value !== null)
  const min = knownValues.length ? formatValue(Math.min(...knownValues), metric.unit) : 'no measured values'
  const max = knownValues.length ? formatValue(Math.max(...knownValues), metric.unit) : 'no measured values'

  return (
    <article className="metric-row">
      <div className="metric-row-copy">
        <h4>{metric.label}</h4>
        <p>{observed} of {points.length} dates · range {min} to {max}</p>
      </div>
      <svg className="metric-sparkline" viewBox="0 0 320 50" role="img" aria-label={`${metric.label} over ${points.length} prediction dates; ${observed} measured values, range ${min} to ${max}.`}>
        <line x1="8" y1="44" x2="312" y2="44" className="chart-axis" />
        {coordinates.slice(1).map((point, index) => {
          const previous = coordinates[index]
          if (!Number.isFinite(point.y) || !Number.isFinite(previous.y)) return null
          return <line key={`segment-${index}`} x1={previous.x} y1={previous.y} x2={point.x} y2={point.y} className="chart-segment" />
        })}
        {coordinates.map((point, index) => Number.isFinite(point.y)
          ? <circle key={`point-${index}`} cx={point.x} cy={point.y} r="2.2" className="chart-point" />
          : null)}
      </svg>
      <details className="metric-data-details">
        <summary>View data table</summary>
        <div className="table-scroll-region">
          <table className="detail-data-table">
            <caption>{metric.label} by prediction date</caption>
            <thead><tr><th scope="col">Prediction date</th><th scope="col">{metric.label}</th></tr></thead>
            <tbody>{points.map((point, index) => (
              <tr key={`${point.predictionDate}-${index}`}>
                <th scope="row"><time dateTime={point.predictionDate}>{point.predictionDate}</time></th>
                <td>{formatValue(values[index], metric.unit)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </details>
    </article>
  )
}
