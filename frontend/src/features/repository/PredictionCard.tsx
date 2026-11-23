import type { PredictionDetail } from '../../api/client'

function displayCode(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function displayValue(value: number | null | undefined): string {
  return value === null || value === undefined
    ? 'Not available'
    : new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(value)
}

export function PredictionCard({ prediction, isLoading, error, onRetry }: {
  prediction: PredictionDetail | null | undefined
  isLoading: boolean
  error: Error | null
  onRetry: () => void
}) {
  if (isLoading) return <div className="detail-state" role="status">Loading prediction…</div>
  if (error) {
    return <div className="detail-state detail-error" role="alert"><p>Prediction information could not be loaded: {error.message}</p><button className="detail-button" type="button" onClick={onRetry}>Retry prediction</button></div>
  }
  if (!prediction) {
    return (
      <section className="detail-card prediction-card" aria-labelledby="current-prediction-title">
        <p className="eyebrow">Current estimate</p>
        <h2 id="current-prediction-title">No prediction available</h2>
        <p>This repository has no stored prediction in the current dataset.</p>
      </section>
    )
  }

  const result = prediction.prediction
  const limitations = result.limitationFlags ?? []
  const explanationMethod = prediction.indicators[0]?.method
  return (
    <section className="detail-card prediction-card" aria-labelledby="current-prediction-title">
      <div className="prediction-heading">
        <div>
          <p className="eyebrow">Current estimate · 90-day activity decline</p>
          <h2 id="current-prediction-title">Prediction</h2>
        </div>
        <span className={`risk-badge risk-${result.riskCategory}`}>{displayCode(result.riskCategory)} risk</span>
      </div>
      <div className="prediction-facts">
        <div><span>Estimated probability</span><strong>{(result.probability * 100).toFixed(1)}%</strong></div>
        <div><span>Prediction date</span><strong><time dateTime={result.predictionDate}>{result.predictionDate}</time></strong></div>
        <div><span>Model</span><strong>#{result.modelVersionId} · {displayCode(result.algorithm)}</strong></div>
        <div><span>Dataset</span><strong>#{result.datasetVersionId} · {displayCode(result.featureSet)}</strong></div>
      </div>
      <p className="prediction-caveat">
        This estimate concerns contribution-activity decline only. Risk categories are cohort-relative; the estimate
        and indicators describe model associations and do not establish causes or repository abandonment.
      </p>
      {limitations.length > 0 && (
        <div className="limitation-panel" role="note">
          <h3>Limitations for this prediction</h3>
          <ul>{limitations.map((flag) => <li key={flag}>{displayCode(flag)}</li>)}</ul>
        </div>
      )}
      <div className="indicator-section">
        <h3>Model explanations</h3>
        <p className="detail-footnote">{explanationMethod === 'shap'
          ? 'SHAP contributions describe how each feature shifts the model probability from its expected value under validation data. They are not causal effects.'
          : 'One-at-a-time score differences compare observed features with validation reference values. They are not causal effects.'}</p>
        {prediction.indicators.length ? (
          <ol className="indicator-list">
            {prediction.indicators.map((indicator, index) => (
              <li key={`${indicator.rank ?? index}-${indicator.featureName ?? 'indicator'}`}>
                <div className="indicator-heading"><strong>{displayCode(indicator.featureName ?? 'Unspecified feature')}</strong><span>Rank {indicator.rank ?? '—'}</span></div>
                <p>{indicator.description ?? 'This stored indicator is an association and does not establish a causal effect.'}</p>
                <dl>
                  <div><dt>Observed</dt><dd>{displayValue(indicator.featureValue)}</dd></div>
                  <div><dt>{indicator.method === 'shap' ? 'Expected model probability' : 'Validation reference value'}</dt><dd>{displayValue(indicator.referenceValue)}</dd></div>
                  <div><dt>{indicator.method === 'shap' ? 'SHAP probability contribution' : 'Model score difference'}</dt><dd>{indicator.probabilityDelta === undefined ? 'Not available' : `${indicator.probabilityDelta > 0 ? '+' : ''}${(indicator.probabilityDelta * 100).toFixed(1)} percentage points`}</dd></div>
                </dl>
              </li>
            ))}
          </ol>
        ) : <p>No stored indicators are available for this prediction.</p>}
      </div>
    </section>
  )
}
