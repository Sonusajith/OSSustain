import type { FeatureImportancePage, ModelVersion } from '../../api/client'
import { ResearchEmpty } from './ResearchPageState'
import { formatDecimal, humanize } from './researchFormat'

export function FeatureImportancePanel({
  models,
  model,
  data,
  isLoading,
  error,
  onModelChange,
  onRetry,
}: {
  models: ModelVersion[]
  model: ModelVersion | undefined
  data: FeatureImportancePage | undefined
  isLoading: boolean
  error: Error | null
  onModelChange: (id: number) => void
  onRetry: () => void
}) {
  const rows = data?.content ?? []
  const maxMagnitude = Math.max(0, ...rows.map((row) => Math.abs(row.value)))
  return (
    <section className="research-panel" aria-labelledby="importance-title">
      <div className="research-panel-heading">
        <div><p className="eyebrow">Model-level diagnostics</p><h2 id="importance-title">Feature importance</h2></div>
        <label className="research-model-select">Selected model
          <select aria-label="Feature importance model" value={model?.id ?? ''} onChange={(event) => onModelChange(Number(event.target.value))}>
            {models.filter((candidate) => candidate.selected).map((candidate) => (
              <option key={candidate.id} value={candidate.id}>{candidate.featureSet.replaceAll('_', ' ')} · {candidate.algorithm.replaceAll('_', ' ')} · #{candidate.id}</option>
            ))}
          </select>
        </label>
      </div>
      {!models.some((candidate) => candidate.selected) ? <ResearchEmpty>No validation-selected model is recorded.</ResearchEmpty>
        : isLoading ? <ResearchEmpty>Loading feature importance…</ResearchEmpty>
          : error ? <div className="research-state research-error" role="alert"><p>{error.message}</p><button className="detail-button" type="button" onClick={onRetry}>Retry importance</button></div>
            : rows.length === 0 ? <ResearchEmpty>No feature-importance records are available for this model.</ResearchEmpty>
              : (
                <>
                  <p className="research-footnote">
                    Method: {humanize(rows[0].method)}. These are model-level predictive associations, not causal effects.
                    {rows[0].method === 'permutation_importance' ? ' Permutation values were computed on validation data.' : ' Coefficients are standardized model weights.'}
                  </p>
                  <div className="table-scroll-region">
                    <table className="research-table importance-table">
                      <caption>Stored feature importance for model {model?.id ?? '—'}</caption>
                      <thead><tr><th scope="col">Rank</th><th scope="col">Feature</th><th scope="col">Magnitude</th><th scope="col">Stored value</th></tr></thead>
                      <tbody>{[...rows].sort((left, right) => left.rank - right.rank).map((row) => (
                        <tr key={`${row.rank}-${row.featureName}`}>
                          <td>{row.rank}</td><th scope="row">{humanize(row.featureName)}</th>
                          <td><span className="importance-track" aria-hidden="true"><span style={{ width: `${maxMagnitude ? (Math.abs(row.value) / maxMagnitude) * 100 : 0}%` }} /></span></td>
                          <td className="numeric-value">{formatDecimal(row.value, 4)}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                </>
              )}
    </section>
  )
}
