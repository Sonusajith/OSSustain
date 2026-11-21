import type { DatasetSummary, Repository } from '../../api/client'

interface CohortSummaryProps {
  dataset: DatasetSummary
  repositories: readonly Repository[]
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function asNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined
}

function formatNumber(value: number | undefined): string {
  return value === undefined ? '—' : new Intl.NumberFormat().format(value)
}

export function CohortSummary({ dataset, repositories }: CohortSummaryProps) {
  const summary = asRecord(dataset.summary)
  const overall = asRecord(summary.overall)
  const byPeriod = asRecord(summary.by_period)
  const dates = Object.keys(byPeriod).filter((date) => /^\d{4}-\d{2}-\d{2}$/.test(date)).sort()
  const highRiskCount = repositories.filter((repository) => repository.latestRiskCategory === 'high').length
  const highRiskPercent = repositories.length
    ? `${((highRiskCount / repositories.length) * 100).toFixed(1)}% of cohort`
    : 'No predictions available'
  const sizeCounts = repositories.reduce<Record<string, number>>((counts, repository) => {
    const group = repository.sizeGroup ?? 'unknown'
    counts[group] = (counts[group] ?? 0) + 1
    return counts
  }, {})
  const versionHash = dataset.versionHash ?? ''
  const periodLabel = dates.length ? `${dates[0]} – ${dates.at(-1)}` : 'Not available'

  return (
    <section className="summary-grid" aria-label="Cohort summary">
      <article className="summary-card">
        <div className="summary-card-heading">
          <span>Repositories analyzed</span>
          <span className="summary-symbol" aria-hidden="true">▤</span>
        </div>
        <strong className="summary-value">{formatNumber(repositories.length)}</strong>
        <div className="size-counts" aria-label="Repository counts by size group">
          {(['small', 'medium', 'large'] as const).map((group) => (
            <span key={group}>{group[0].toUpperCase()} <b>{formatNumber(sizeCounts[group] ?? 0)}</b></span>
          ))}
        </div>
      </article>

      <article className="summary-card">
        <div className="summary-card-heading">
          <span>Observation window</span>
          <span className="summary-symbol" aria-hidden="true">◷</span>
        </div>
        <strong className="summary-date-value">{periodLabel}</strong>
        <p className="summary-footnote">
          {formatNumber(asNumber(overall.snapshots))} monthly snapshots in this dataset
        </p>
      </article>

      <article className="summary-card risk-summary-card">
        <div className="summary-card-heading">
          <span>High risk category</span>
          <span className="risk-dot" aria-hidden="true" />
        </div>
        <strong className="summary-value risk-value">{formatNumber(highRiskCount)}</strong>
        <p className="summary-footnote">{highRiskPercent}; cohort-relative category</p>
      </article>

      <article className="summary-card dataset-card">
        <div className="summary-card-heading">
          <span>Current dataset</span>
          <span className="summary-symbol" aria-hidden="true">⌘</span>
        </div>
        <strong className="summary-value">{dataset.id === undefined ? '—' : `#${dataset.id}`}</strong>
        <p className="summary-footnote" title={versionHash}>
          {asString(dataset.cohortName) ?? 'Cohort'} · {versionHash ? `${versionHash.slice(0, 12)}…` : 'Version hash unavailable'}
        </p>
      </article>
    </section>
  )
}
