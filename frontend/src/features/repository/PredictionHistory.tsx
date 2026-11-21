import type { PredictionHistory } from '../../api/client'

function displayCode(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function PredictionHistory({ predictions, isLoading, error, onRetry }: {
  predictions: PredictionHistory | undefined
  isLoading: boolean
  error: Error | null
  onRetry: () => void
}) {
  if (isLoading) return <div className="detail-state" role="status">Loading prediction history…</div>
  if (error) {
    return <div className="detail-state detail-error" role="alert"><p>Prediction history could not be loaded: {error.message}</p><button className="detail-button" type="button" onClick={onRetry}>Retry history</button></div>
  }
  if (!predictions?.length) return <div className="detail-state">No prediction history is available for this repository.</div>

  return (
    <section className="detail-section" aria-labelledby="prediction-history-title">
      <div className="detail-section-heading"><div><p className="eyebrow">Stored estimates</p><h2 id="prediction-history-title">Prediction history</h2></div></div>
      <div className="table-scroll-region">
        <table className="detail-data-table history-table">
          <caption>Stored prediction records for this repository</caption>
          <thead><tr><th scope="col">Prediction date</th><th scope="col">Risk category</th><th scope="col">Probability</th><th scope="col">Model</th><th scope="col">Dataset</th><th scope="col">Limitations</th></tr></thead>
          <tbody>{predictions.map((prediction) => (
            <tr key={prediction.id}>
              <th scope="row"><time dateTime={prediction.predictionDate}>{prediction.predictionDate}</time></th>
              <td><span className={`risk-badge risk-${prediction.riskCategory}`}>{displayCode(prediction.riskCategory)} risk</span></td>
              <td>{(prediction.probability * 100).toFixed(1)}%</td>
              <td>#{prediction.modelVersionId} {displayCode(prediction.algorithm)}</td>
              <td>#{prediction.datasetVersionId}</td>
              <td>{prediction.limitationFlags.length ? prediction.limitationFlags.map(displayCode).join(', ') : 'None recorded'}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  )
}
