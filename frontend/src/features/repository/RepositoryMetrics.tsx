import type { RepositoryMetrics as MetricPoint } from '../../api/client'
import { MetricHistoryChart } from './MetricHistoryChart'

interface MetricDefinition {
  key: string
  label: string
  unit: 'count' | 'fraction' | 'coefficient' | 'hours'
}

const metricGroups: { title: string; description: string; metrics: MetricDefinition[] }[] = [
  {
    title: 'Activity',
    description: 'Recorded activity in the rolling windows before each prediction date.',
    metrics: [
      { key: 'commits_30d', label: 'Commits · 30 days', unit: 'count' },
      { key: 'commits_90d', label: 'Commits · 90 days', unit: 'count' },
      { key: 'pull_requests_merged_90d', label: 'Merged pull requests · 90 days', unit: 'count' },
      { key: 'pull_requests_opened_90d', label: 'Opened pull requests · 90 days', unit: 'count' },
      { key: 'issues_opened_90d', label: 'Issues opened · 90 days', unit: 'count' },
    ],
  },
  {
    title: 'Community',
    description: 'Contributor participation and newcomer measures.',
    metrics: [
      { key: 'active_contributors_90d', label: 'Active contributors · 90 days', unit: 'count' },
      { key: 'contributor_gini_90d', label: 'Contributor concentration (Gini)', unit: 'coefficient' },
      { key: 'new_contributors_90d', label: 'New contributors · 90 days', unit: 'count' },
      { key: 'newcomer_retention_rate_90d', label: 'Newcomer retention · 90 days', unit: 'fraction' },
    ],
  },
  {
    title: 'Responsiveness',
    description: 'Median time to a first response for recorded pull requests and issues.',
    metrics: [
      { key: 'median_pr_first_response_hours_90d', label: 'Pull request first response', unit: 'hours' },
      { key: 'median_issue_first_response_hours_90d', label: 'Issue first response', unit: 'hours' },
    ],
  },
]

export function RepositoryMetrics({ data, isLoading, error, onRetry }: {
  data: MetricPoint | undefined
  isLoading: boolean
  error: Error | null
  onRetry: () => void
}) {
  if (isLoading) {
    return <div className="detail-state" role="status" aria-live="polite">Loading monthly repository metrics…</div>
  }
  if (error) {
    return (
      <div className="detail-state detail-error" role="alert">
        <p>Monthly metrics could not be loaded: {error.message}</p>
        <button className="detail-button" type="button" onClick={onRetry}>Retry metrics</button>
      </div>
    )
  }
  if (!data?.length) {
    return <div className="detail-state">No monthly metrics are available for this repository in the current dataset.</div>
  }

  const dates = data.map((point) => point.predictionDate).filter(Boolean)
  return (
    <section className="detail-section" aria-labelledby="metrics-title">
      <div className="detail-section-heading">
        <div>
          <p className="eyebrow">Longitudinal record</p>
          <h2 id="metrics-title">Monthly metrics</h2>
          <p>{dates[0]} through {dates.at(-1)} · {data.length} recorded prediction dates</p>
        </div>
      </div>
      <div className="metric-groups">
        {metricGroups.map((group) => (
          <section className="metric-group" key={group.title} aria-labelledby={`metric-group-${group.title}`}>
            <div className="metric-group-heading">
              <h3 id={`metric-group-${group.title}`}>{group.title}</h3>
              <p>{group.description}</p>
            </div>
            <div className="metric-list">
              {group.metrics.map((metric) => (
                <MetricHistoryChart key={metric.key} points={data} metric={metric} />
              ))}
            </div>
          </section>
        ))}
      </div>
      <p className="detail-footnote">
        Metrics are computed from data before each prediction date. The stored series includes first-response times;
        a separate review-duration measure is not available in this API dataset. Missing values remain blank.
      </p>
    </section>
  )
}
