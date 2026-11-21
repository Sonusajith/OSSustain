import { Link, useParams } from 'react-router-dom'

import { useLatestPrediction, usePredictionHistory, useRepositoryDetail, useRepositoryMetrics } from '../../api/queries'
import { PredictionCard } from './PredictionCard'
import { PredictionHistory } from './PredictionHistory'
import { RepositoryMetrics } from './RepositoryMetrics'

function displayCode(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <main className="detail-page">
      <section className="state-panel" role="alert">
        <span className="state-icon" aria-hidden="true">!</span>
        <div><h1>We couldn’t load this repository</h1><p>{message}</p>{onRetry && <button className="detail-button" type="button" onClick={onRetry}>Try again</button>}</div>
      </section>
      <Link className="detail-back-link" to="/">← Back to cohort overview</Link>
    </main>
  )
}

export function RepositoryDetailPage() {
  const { repositoryId = '' } = useParams()
  const id = /^\d+$/.test(repositoryId) ? Number(repositoryId) : Number.NaN
  const validId = Number.isSafeInteger(id) && id > 0
  const repositoryQuery = useRepositoryDetail(id, validId)
  const metricsQuery = useRepositoryMetrics(id, validId && repositoryQuery.isSuccess)
  const predictionQuery = useLatestPrediction(id, validId && repositoryQuery.isSuccess)
  const historyQuery = usePredictionHistory(id, validId && repositoryQuery.isSuccess)

  if (!validId) return <ErrorState message="The repository ID in this address is invalid." />
  if (repositoryQuery.isLoading) {
    return <main className="detail-page" aria-busy="true" aria-live="polite"><div className="detail-state">Loading repository details…</div></main>
  }
  if (repositoryQuery.isError) {
    const missing = repositoryQuery.error.message.toLowerCase().includes('not found')
    return <ErrorState
      message={missing ? 'This repository does not exist in the current dataset.' : repositoryQuery.error.message}
      onRetry={() => void repositoryQuery.refetch()}
    />
  }
  if (!repositoryQuery.data) {
    return <ErrorState message="Repository details are not available in the current response." onRetry={() => void repositoryQuery.refetch()} />
  }

  const repository = repositoryQuery.data
  const flags = repository.dataQualityFlags ?? []
  const createdAt = new Date(repository.createdAt)
  const createdDate = Number.isNaN(createdAt.valueOf()) ? repository.createdAt : createdAt.toLocaleDateString()

  return (
    <main className="detail-page">
      <Link className="detail-back-link" to="/">← Back to cohort overview</Link>
      <header className="repository-hero">
        <div>
          <p className="eyebrow">Repository detail · {repository.sizeGroup} cohort</p>
          <h1>{repository.fullName}</h1>
          <p className="repository-description">Longitudinal contribution activity and the latest stored 90-day estimate.</p>
          <a className="detail-external-link" href={`https://github.com/${encodeURIComponent(repository.owner)}/${encodeURIComponent(repository.name)}`} target="_blank" rel="noreferrer">
            View public GitHub repository <span aria-hidden="true">↗</span>
          </a>
        </div>
        <dl className="repository-facts">
          <div><dt>Stars at collection</dt><dd>{new Intl.NumberFormat().format(repository.stars)}</dd></div>
          <div><dt>Primary language</dt><dd>{repository.primaryLanguage ?? 'Not recorded'}</dd></div>
          <div><dt>Created</dt><dd><time dateTime={repository.createdAt}>{createdDate}</time></dd></div>
          <div><dt>Default branch</dt><dd>{repository.defaultBranch ?? 'Not recorded'}</dd></div>
          <div><dt>Status</dt><dd>{repository.archived ? 'Archived' : 'Active'}{repository.fork ? ' · Fork' : ''}</dd></div>
        </dl>
      </header>

      {flags.length > 0 && (
        <section className="limitation-panel repository-quality" aria-labelledby="quality-title">
          <h2 id="quality-title">Data-quality notes</h2>
          <p>Interpret this repository’s historical measures with these recorded collection flags:</p>
          <ul>{flags.map((flag) => <li key={flag}>{displayCode(flag)}</li>)}</ul>
        </section>
      )}

      <PredictionCard
        prediction={predictionQuery.data}
        isLoading={predictionQuery.isLoading}
        error={predictionQuery.error}
        onRetry={() => void predictionQuery.refetch()}
      />
      <RepositoryMetrics
        data={metricsQuery.data}
        isLoading={metricsQuery.isLoading}
        error={metricsQuery.error}
        onRetry={() => void metricsQuery.refetch()}
      />
      <PredictionHistory
        predictions={historyQuery.data}
        isLoading={historyQuery.isLoading}
        error={historyQuery.error}
        onRetry={() => void historyQuery.refetch()}
      />
    </main>
  )
}
