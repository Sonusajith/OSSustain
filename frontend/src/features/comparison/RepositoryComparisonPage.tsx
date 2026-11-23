import { Link, useSearchParams } from 'react-router-dom'

import { useRepositoryComparison, useRepositories } from '../../api/queries'
import type { RepositoryComparison } from '../../api/client'

const METRICS = [
  ['commits_30d', 'Commits · 30 days'],
  ['commits_90d', 'Commits · 90 days'],
  ['commits_180d', 'Commits · 180 days'],
  ['active_contributors_90d', 'Active contributors · 90 days'],
  ['new_contributors_90d', 'New contributors · 90 days'],
  ['newcomer_retention_rate_90d', 'Newcomer retention · 90 days'],
  ['pull_requests_merged_90d', 'Pull requests merged · 90 days'],
  ['issues_opened_90d', 'Issues opened · 90 days'],
  ['median_pr_first_response_hours_90d', 'Median PR first response'],
] as const

type ComparisonEntry = RepositoryComparison['repositories'][number]

function parseIds(value: string | null): number[] {
  if (!value) return []
  const ids = value.split(',').map((part) => Number(part))
  if (ids.length > 4 || ids.some((id) => !Number.isSafeInteger(id) || id <= 0) || new Set(ids).size !== ids.length) return []
  return ids
}

function displayDate(value: string | null | undefined): string {
  if (!value) return 'Not available'
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'UTC' }).format(date)
}

function displayMetric(value: unknown, key: string): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Not available'
  if (key.includes('rate')) return `${(value * 100).toFixed(1)}%`
  const formatted = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)
  return key.includes('hours') ? `${formatted} hours` : formatted
}

function metricValue(entry: ComparisonEntry, key: string): unknown {
  const metrics: unknown = entry.latestMetrics?.metrics
  if (typeof metrics !== 'object' || metrics === null || !(key in metrics)) return null
  return (metrics as Record<string, unknown>)[key]
}

function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <section className="comparison-state state-panel error-panel" role="alert">
      <span className="state-icon" aria-hidden="true">!</span>
      <div><h2>Comparison data could not be loaded</h2><p>{message}</p><button className="primary-button" type="button" onClick={onRetry}>Try again</button></div>
    </section>
  )
}

function ComparisonTable({ entries }: { entries: ComparisonEntry[] }) {
  return (
    <div className="comparison-table-scroll" role="region" aria-label="Repository comparison metrics" tabIndex={0}>
      <table className="comparison-table" aria-label="Repository comparison metrics">
        <thead>
          <tr>
            <th scope="col">Measure</th>
            {entries.map(({ repository, latestMetrics }) => (
              <th scope="col" key={repository.id}>
                <Link to={`/repositories/${repository.id}`}>{repository.fullName}</Link>
                <span className="comparison-column-date">Metrics: {displayDate(latestMetrics?.predictionDate)}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr><th scope="row">Size group</th>{entries.map(({ repository }) => <td key={repository.id}>{repository.sizeGroup}</td>)}</tr>
          <tr><th scope="row">Stars at selection</th>{entries.map(({ repository }) => <td key={repository.id}>{new Intl.NumberFormat().format(repository.stars)}</td>)}</tr>
          <tr><th scope="row">Latest risk category</th>{entries.map(({ repository }) => <td key={repository.id}>{repository.latestRiskCategory ?? 'No prediction'}</td>)}</tr>
          <tr><th scope="row">Latest risk probability</th>{entries.map(({ repository }) => <td key={repository.id}>{typeof repository.latestProbability === 'number' ? `${(repository.latestProbability * 100).toFixed(1)}%` : 'Not available'}</td>)}</tr>
          <tr><th scope="row">Prediction date</th>{entries.map(({ repository }) => <td key={repository.id}>{displayDate(repository.predictionDate)}</td>)}</tr>
          {METRICS.map(([key, label]) => (
            <tr key={key}><th scope="row">{label}</th>{entries.map((entry) => <td key={entry.repository.id}>{displayMetric(metricValue(entry, key), key)}</td>)}</tr>
          ))}
          <tr>
            <th scope="row">Data-quality flags</th>
            {entries.map(({ repository }) => {
              const flags = Array.isArray(repository.dataQualityFlags) ? repository.dataQualityFlags : []
              return <td key={repository.id}>{flags.length ? flags.join(', ') : 'No flags'}</td>
            })}
          </tr>
        </tbody>
      </table>
    </div>
  )
}

export function RepositoryComparisonPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const repositoriesQuery = useRepositories()
  const selectedIds = parseIds(searchParams.get('ids'))
  const comparisonQuery = useRepositoryComparison(selectedIds, selectedIds.length >= 2 && selectedIds.length <= 4)
  const filter = searchParams.get('q') ?? ''

  function updateParams(nextIds: number[], nextFilter = filter) {
    const params = new URLSearchParams(searchParams)
    if (nextIds.length) params.set('ids', nextIds.join(','))
    else params.delete('ids')
    if (nextFilter.trim()) params.set('q', nextFilter.trim())
    else params.delete('q')
    setSearchParams(params, { replace: true })
  }

  function toggleRepository(id: number, checked: boolean) {
    const nextIds = checked ? [...selectedIds, id] : selectedIds.filter((selected) => selected !== id)
    updateParams(nextIds)
  }

  if (repositoriesQuery.isPending) {
    return <main className="comparison-page" aria-busy="true" aria-live="polite"><p className="eyebrow">Repository comparison</p><h1>Compare repositories</h1><p className="page-description">Loading the current cohort…</p></main>
  }

  if (repositoriesQuery.isError || !repositoriesQuery.data) {
    return <main className="comparison-page"><p className="eyebrow">Repository comparison</p><h1>Compare repositories</h1><ErrorPanel message={repositoriesQuery.error?.message ?? 'The cohort response was empty.'} onRetry={() => void repositoriesQuery.refetch()} /></main>
  }

  const repositories = repositoriesQuery.data
  const visibleRepositories = repositories.filter((repository) => repository.fullName.toLowerCase().includes(filter.toLowerCase()))
  const canCompare = selectedIds.length >= 2 && selectedIds.length <= 4

  return (
    <main className="comparison-page">
      <header className="comparison-heading">
        <div><p className="eyebrow">Post-MVP analysis · latest cohort</p><h1>Compare repositories</h1><p className="page-description">Select two to four repositories to compare their latest stored risk estimates and contribution metrics.</p></div>
        <Link className="detail-back-link" to="/">← Cohort overview</Link>
      </header>

      <section className="comparison-picker" aria-labelledby="comparison-picker-title">
        <div className="comparison-picker-heading"><div><h2 id="comparison-picker-title">Choose repositories</h2><p>{selectedIds.length} of 4 selected · choose at least 2</p></div></div>
        <label className="comparison-search">Filter cohort
          <input type="search" value={filter} onChange={(event) => updateParams(selectedIds, event.currentTarget.value)} placeholder="Search repository names" />
        </label>
        {repositories.length === 0 ? <p className="comparison-empty">There are no repositories in the current cohort.</p> : (
          <fieldset className="comparison-repository-list">
            <legend className="visually-hidden">Repositories available for comparison</legend>
            {visibleRepositories.map((repository) => {
              const checked = selectedIds.includes(repository.id)
              return (
                <label className="comparison-repository-option" key={repository.id}>
                  <input type="checkbox" checked={checked} disabled={!checked && selectedIds.length >= 4} onChange={(event) => toggleRepository(repository.id, event.currentTarget.checked)} />
                  <span>{repository.fullName}</span><small>{repository.sizeGroup} · {new Intl.NumberFormat().format(repository.stars)} stars</small>
                </label>
              )
            })}
            {visibleRepositories.length === 0 && <p className="comparison-empty">No cohort repositories match this search.</p>}
          </fieldset>
        )}
      </section>

      {!canCompare ? <p className="comparison-hint" role="status">Select at least two repositories to see a comparison.</p> : comparisonQuery.isPending ? (
        <section className="comparison-state" aria-busy="true" aria-live="polite"><h2>Loading comparison…</h2><p>Retrieving the selected repositories’ stored metrics.</p></section>
      ) : comparisonQuery.isError ? (
        <ErrorPanel message={comparisonQuery.error.message} onRetry={() => void comparisonQuery.refetch()} />
      ) : comparisonQuery.data ? (
        <section className="comparison-results" aria-labelledby="comparison-results-title">
          <div className="comparison-results-heading"><div><p className="eyebrow">Stored observations</p><h2 id="comparison-results-title">Side-by-side metrics</h2></div><p>Metrics can have different observation dates; each date is shown in its column heading.</p></div>
          <ComparisonTable entries={comparisonQuery.data.repositories} />
          <p className="comparison-caveat">Risk estimates concern future contribution-activity decline only. Repository metrics are descriptive and do not imply causation.</p>
        </section>
      ) : null}
    </main>
  )
}
