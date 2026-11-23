import { type FormEvent, useState } from 'react'

import { useAnalysis, useSubmitAnalysis } from '../../api/queries'

export function AnalysisPage() {
  const [repository, setRepository] = useState('')
  const [jobId, setJobId] = useState<string>()
  const submit = useSubmitAnalysis()
  const job = useAnalysis(jobId)

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    submit.mutate(repository.trim(), { onSuccess: (response) => setJobId(response.id) })
  }

  const result = job.data?.result
  const indicators = (result?.indicators ?? []) as Array<{
    feature_name?: string
    direction?: string
    probability_delta?: number
    feature_value?: number | null
  }>
  return (
    <main className="analysis-page">
      <p className="eyebrow">OSSustain research platform</p>
      <h1>Analyze a public repository</h1>
      <p className="analysis-intro">Get a bounded, on-demand estimate using up to 180 days of public activity and the current validation-selected model.</p>
      <form className="analysis-form" onSubmit={handleSubmit}>
        <label htmlFor="repository-name">GitHub repository</label>
        <div className="analysis-input-row">
          <input id="repository-name" value={repository} onChange={(event) => setRepository(event.target.value)} placeholder="owner/repository" required pattern="[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}" aria-describedby="analysis-help" />
          <button className="primary-button" type="submit" disabled={submit.isPending}>Analyze</button>
        </div>
        <p id="analysis-help">Public repositories only. Each analysis is limited to 300 GitHub requests. Results are an activity risk estimate, not a causal claim.</p>
      </form>
      {submit.isError && <div className="analysis-message error-panel" role="alert">{submit.error.message}</div>}
      {jobId && <section className="analysis-result" aria-live="polite" aria-busy={job.isFetching}>
        {job.isPending && <p>Loading analysis status…</p>}
        {job.isError && <div className="analysis-message error-panel" role="alert"><p>{job.error.message}</p><button className="primary-button" onClick={() => void job.refetch()}>Retry</button></div>}
        {job.data?.status === 'queued' && <p>Analysis is queued. This page will update automatically.</p>}
        {job.data?.status === 'running' && <p>Collecting public activity and calculating the estimate…</p>}
        {job.data?.status === 'failed' && <div className="analysis-message error-panel" role="alert"><h2>Analysis could not be completed</h2><p>{job.data.errorCode === 'request_limit' ? 'The available GitHub request budget was reached before collection was complete. Try again later.' : job.data.errorCode === 'model_unavailable' ? 'The selected trained model artifact is not available to the worker.' : job.data.errorCode === 'repository_unavailable' ? 'The repository was not found or could not be accessed as a public repository.' : job.data.errorCode === 'github_rate_limit' ? 'GitHub is temporarily rate limiting analysis. Try again later.' : job.data.errorCode === 'github_auth_failed' ? 'The worker’s GitHub credentials were rejected. Contact the project administrator.' : 'The repository could not be analyzed. Check that it is public and try again.'}</p><p>Reference: {job.data.id}</p></div>}
        {job.data?.status === 'succeeded' && result && <div className="analysis-card">
          <h2>{job.data.repository}</h2>
          <p><strong>{(result.probability * 100).toFixed(1)}%</strong> estimated risk of significant contribution activity decline in the next 90 days</p>
          <dl><div><dt>Risk category</dt><dd>{result.riskCategory}</dd></div><div><dt>Model</dt><dd>{result.algorithm} · {result.featureSet}</dd></div><div><dt>Prediction date</dt><dd>{result.predictionDate}</dd></div><div><dt>GitHub requests used</dt><dd>{result.requestsUsed} / 300</dd></div></dl>
          <h3>Limitations</h3><ul>{result.limitations.map((limitation: string) => <li key={limitation}>{limitation.replaceAll('_', ' ')}</li>)}</ul>
          <h3>Activity features</h3><div className="analysis-features">{Object.entries(result.features as Record<string, number | null>).map(([name, value]) => <div key={name}><span>{name.replaceAll('_', ' ')}</span><strong>{value === null ? 'Unavailable' : value}</strong></div>)}</div>
          {indicators.length > 0 && <><h3>Model indicators</h3><p>Local feature substitutions show model associations; they do not describe causes.</p><ul>{indicators.map((indicator) => <li key={indicator.feature_name}>{indicator.feature_name?.replaceAll('_', ' ')}: {indicator.direction?.replaceAll('_', ' ')} ({indicator.probability_delta === undefined ? '—' : `${indicator.probability_delta > 0 ? '+' : ''}${(indicator.probability_delta * 100).toFixed(1)} percentage points`})</li>)}</ul></>}
          <p className="analysis-caveat">This submitted-repository estimate is separate from the fixed research cohort.</p>
        </div>}
      </section>}
    </main>
  )
}
