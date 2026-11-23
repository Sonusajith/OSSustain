import { useState } from 'react'

import type { Evaluation, ModelVersion } from '../../api/client'
import { useDatasetSummary, useResearchEvaluations, useResearchFeatureImportance, useResearchModels } from '../../api/queries'
import { CalibrationChart } from './CalibrationChart'
import { FeatureImportancePanel } from './FeatureImportancePanel'
import { ResearchEmpty, ResearchFailure, ResearchLoading } from './ResearchPageState'
import { asNumber, asRecord, formatCount, formatDecimal, formatInterval, formatRate, humanize, nestedRecord } from './researchFormat'

function evaluationFor(rows: Evaluation[], modelId: number, metric: string, split: string, stratum = 'overall') {
  return rows.find((row) => row.modelVersionId === modelId && row.metric === metric && row.split === split && row.stratum === stratum)
}

function MetricCell({ row }: { row: Evaluation | undefined }) {
  if (!row || row.value === null || row.value === undefined) return <td>—</td>
  return <td><span className="numeric-value">{formatInterval(row.value, row.ciLow, row.ciHigh)}</span></td>
}

function ModelPrAucChart({ models, evaluations }: { models: ModelVersion[]; evaluations: Evaluation[] }) {
  const rows = models.map((model) => ({
    model,
    evaluation: evaluationFor(evaluations, model.id, 'pr_auc', 'test'),
  }))
  const chartRows = rows.filter(({ evaluation }) => asNumber(evaluation?.value) !== undefined)
  if (!chartRows.length) return <ResearchEmpty>No held-out test PR-AUC values are available.</ResearchEmpty>
  const height = chartRows.length * 27 + 26
  const x = (value: number) => 315 + value * 315
  return (
    <section className="research-panel" aria-labelledby="model-pr-title">
      <div className="research-panel-heading"><div><p className="eyebrow">Overall · held-out test</p><h2 id="model-pr-title">Test PR-AUC by model</h2></div><span className="research-tag">95% repository-cluster intervals</span></div>
      <svg className="research-chart model-score-chart" viewBox={`0 0 660 ${height}`} role="img" aria-label="Horizontal comparison of held-out test PR-AUC estimates and 95 percent repository-cluster confidence intervals across stored models.">
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={tick}><line x1={x(tick)} x2={x(tick)} y1="12" y2={height - 8} className="chart-gridline" /><text x={x(tick)} y={height - 1} textAnchor="middle" className="chart-tick">{tick.toFixed(2)}</text></g>
        ))}
        {chartRows.map(({ model, evaluation }, index) => {
          const y = 22 + index * 27
          const estimate = asNumber(evaluation?.value) ?? 0
          const low = asNumber(evaluation?.ciLow) ?? estimate
          const high = asNumber(evaluation?.ciHigh) ?? estimate
          return (
            <g key={model.id}>
              <text x="4" y={y + 3} className="chart-row-label">{model.featureSet.replaceAll('_', ' ')} · {model.algorithm.replaceAll('_', ' ')}{model.selected ? ' · selected' : ''}</text>
              <line x1={x(low)} x2={x(high)} y1={y} y2={y} className={model.selected ? 'score-interval score-selected' : 'score-interval'} />
              <line x1={x(low)} x2={x(low)} y1={y - 4} y2={y + 4} className="score-cap" />
              <line x1={x(high)} x2={x(high)} y1={y - 4} y2={y + 4} className="score-cap" />
              <circle cx={x(estimate)} cy={y} r={model.selected ? 4 : 3} className={model.selected ? 'score-point score-selected' : 'score-point'} />
            </g>
          )
        })}
      </svg>
      <details className="research-table-details">
        <summary>View model score data table</summary>
        <div className="table-scroll-region">
          <table className="research-table">
            <caption>Held-out test PR-AUC and 95% repository-cluster intervals by model</caption>
            <thead><tr><th scope="col">Feature family</th><th scope="col">Algorithm</th><th scope="col">Selected</th><th scope="col">PR-AUC</th><th scope="col">95% interval</th></tr></thead>
            <tbody>{chartRows.map(({ model, evaluation }) => <tr key={model.id}>
              <th scope="row">{humanize(model.featureSet)}</th><td>{humanize(model.algorithm)}</td><td>{model.selected ? 'Yes' : 'No'}</td>
              <td>{formatDecimal(evaluation?.value)}</td><td>{formatDecimal(evaluation?.ciLow)}–{formatDecimal(evaluation?.ciHigh)}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </details>
      <p className="research-footnote">PR-AUC depends on class prevalence; the test prevalence and sample size are shown above. Higher values indicate better ranking for this dataset and split.</p>
    </section>
  )
}

function DatasetOverview({ summary, datasetId, versionHash }: { summary: unknown; datasetId: number; versionHash: string }) {
  const dataset = asRecord(summary)
  const overall = asRecord(dataset.overall)
  const test = nestedRecord(dataset, 'by_split', 'test')
  const testThreshold = nestedRecord(test.thresholds, '0.5')
  const repositories = Array.isArray(dataset.repositories) ? dataset.repositories.length : undefined
  const testSnapshotRow = asNumber(test.snapshots)

  return (
    <section className="research-summary" aria-label="Dataset summary">
      <article><span>Repositories</span><strong>{formatCount(repositories)}</strong><small>Dataset #{datasetId} · {versionHash.slice(0, 12)}…</small></article>
      <article><span>Monthly snapshots</span><strong>{formatCount(overall.snapshots)}</strong><small>{formatCount(overall.labeled)} labeled across the full cohort</small></article>
      <article><span>Held-out test</span><strong>{formatCount(test.labeled)} labeled</strong><small>{formatCount(testSnapshotRow)} snapshots · 50% threshold</small></article>
      <article><span>Test prevalence</span><strong>{formatRate(testThreshold.prevalence)}</strong><small>{formatCount(testThreshold.positive)} positives at θ = 0.50</small></article>
    </section>
  )
}

function PairComparison({ models, evaluations }: { models: ModelVersion[]; evaluations: Evaluation[] }) {
  const extended = models.find((model) => model.selected && model.featureSet === 'extended')
  if (!extended) return <ResearchEmpty>No validation-selected extended model is recorded.</ResearchEmpty>
  const delta = evaluationFor(evaluations, extended.id, 'paired_delta_pr_auc_vs_activity_only', 'test')
  const brierDelta = evaluationFor(evaluations, extended.id, 'paired_delta_brier_score_vs_activity_only', 'test')
  if (!delta) return <ResearchEmpty>No paired test comparison is stored for the selected feature families.</ResearchEmpty>
  const details = asRecord(delta.details)
  const spansZero = asNumber(delta.ciLow) !== undefined && asNumber(delta.ciHigh) !== undefined
    && (delta.ciLow ?? 0) <= 0 && (delta.ciHigh ?? 0) >= 0
  return (
    <section className="paired-result" aria-labelledby="paired-result-title">
      <div><p className="eyebrow">Paired comparison · same test snapshots</p><h2 id="paired-result-title">Extended vs. activity-only</h2>
        <p>Extended minus activity-only, using the stored validation-selected models. Positive PR-AUC favors extended; negative Brier difference favors extended.</p>
      </div>
      <div className="paired-result-values">
        <div><span>PR-AUC difference (95% CI)</span><strong>{formatInterval(delta.value, delta.ciLow, delta.ciHigh)}</strong></div>
        <div><span>Brier difference (95% CI)</span><strong>{brierDelta ? formatInterval(brierDelta.value, brierDelta.ciLow, brierDelta.ciHigh) : '—'}</strong></div>
        <small>{formatCount(asRecord(details).n_snapshots)} snapshots · {formatCount(asRecord(details).n_repositories)} repository clusters</small>
      </div>
      <p className="paired-conclusion">{spansZero ? 'The PR-AUC interval includes zero; this run does not establish a reliable improvement from extended features.' : 'The stored interval does not include zero; interpret it with the small number of independent repository clusters.'}</p>
    </section>
  )
}

function SizeBreakdown({ models, evaluations }: { models: ModelVersion[]; evaluations: Evaluation[] }) {
  const selected = models.filter((model) => model.selected)
  const groups = ['small', 'medium', 'large']
  return (
    <section className="research-panel" aria-labelledby="size-results-title">
      <div className="research-panel-heading"><div><p className="eyebrow">Selected models · held-out test</p><h2 id="size-results-title">Test PR-AUC by repository size</h2></div></div>
      <div className="table-scroll-region">
        <table className="research-table">
          <caption>Selected-model test PR-AUC with repository-cluster confidence intervals by size group</caption>
          <thead><tr><th scope="col">Size group</th><th scope="col">Feature family</th><th scope="col">PR-AUC (95% CI)</th><th scope="col">Snapshots</th><th scope="col">Repositories</th></tr></thead>
          <tbody>{groups.flatMap((group) => selected.map((model) => {
            const row = evaluationFor(evaluations, model.id, 'pr_auc', 'test', group)
            const details = asRecord(row?.details)
            return <tr key={`${group}-${model.id}`}>
              <th scope="row">{humanize(group)}</th><td>{model.featureSet.replaceAll('_', ' ')}</td>
              <td><span className="numeric-value">{row ? formatInterval(row.value, row.ciLow, row.ciHigh) : '—'}</span></td>
              <td>{formatCount(details.n_snapshots)}</td><td>{formatCount(details.n_repositories)}</td>
            </tr>
          }))}</tbody>
        </table>
      </div>
      <p className="research-footnote">These subgroup estimates are descriptive. Several groups contain only two to six independent repositories.</p>
    </section>
  )
}

function RobustnessAnalysis({ models, evaluations }: { models: ModelVersion[]; evaluations: Evaluation[] }) {
  const variants = [
    { key: 'robustness_theta_0.3', label: 'θ = 0.30 · commits' },
    { key: 'robustness_theta_0.7', label: 'θ = 0.70 · commits' },
    { key: 'robustness_commits_plus_merged_prs', label: 'θ = 0.50 · commits + merged PRs' },
  ]
  const selected = models.filter((model) => model.selected)
  const hasResults = selected.some((model) => variants.some((variant) =>
    evaluationFor(evaluations, model.id, `${variant.key}_pr_auc`, 'test')))

  return (
    <section className="research-panel" aria-labelledby="robustness-title">
      <div className="research-panel-heading">
        <div><p className="eyebrow">Fixed selected models · held-out test</p><h2 id="robustness-title">Target definition sensitivity</h2></div>
        <span className="research-tag">Repository-cluster intervals</span>
      </div>
      {!hasResults ? <ResearchEmpty>Robustness results have not been generated for this dataset version. Rerun the offline evaluation pipeline to populate them.</ResearchEmpty> : (
        <div className="table-scroll-region">
          <table className="research-table">
            <caption>Held-out performance under alternate decline thresholds and activity definitions, using fixed validation-selected model predictions</caption>
            <thead><tr><th scope="col">Model</th><th scope="col">Outcome definition</th><th scope="col">PR-AUC (95% CI)</th><th scope="col">F1</th><th scope="col">Brier</th><th scope="col">Snapshots</th><th scope="col">Repositories</th></tr></thead>
            <tbody>{selected.flatMap((model) => variants.map((variant) => {
              const prAuc = evaluationFor(evaluations, model.id, `${variant.key}_pr_auc`, 'test')
              const f1 = evaluationFor(evaluations, model.id, `${variant.key}_f1`, 'test')
              const brier = evaluationFor(evaluations, model.id, `${variant.key}_brier_score`, 'test')
              const details = asRecord(prAuc?.details)
              return <tr key={`${model.id}-${variant.key}`}>
                <th scope="row">{humanize(model.featureSet)} · {humanize(model.algorithm)}</th><td>{variant.label}</td>
                <td>{prAuc ? formatInterval(prAuc.value, prAuc.ciLow, prAuc.ciHigh) : '—'}</td>
                <td>{f1 ? formatDecimal(f1.value) : '—'}</td><td>{brier ? formatDecimal(brier.value) : '—'}</td>
                <td>{formatCount(details.n_snapshots)}</td><td>{formatCount(details.n_repositories)}</td>
              </tr>
            }))}</tbody>
          </table>
        </div>
      )}
      <p className="research-footnote">Each row reuses the model’s fixed test probabilities; no test outcomes select or tune a model. θ changes the decline label. The activity variant adds merged pull requests to non-bot default-branch commits. Intervals resample repositories.</p>
    </section>
  )
}

export function ResearchResultsPage() {
  const summaryQuery = useDatasetSummary()
  const modelsQuery = useResearchModels()
  const evaluationsQuery = useResearchEvaluations()
  const [importanceModelId, setImportanceModelId] = useState(0)
  const models = modelsQuery.data?.content ?? []
  const selectedImportanceModel = models.find((model) => model.id === importanceModelId && model.selected)
    ?? models.find((model) => model.selected && model.featureSet === 'extended')
    ?? models.find((model) => model.selected)
  const importanceModelIdToLoad = selectedImportanceModel?.id ?? 0
  const importanceQuery = useResearchFeatureImportance(importanceModelIdToLoad, importanceModelIdToLoad > 0)

  const baseQueries = [summaryQuery, modelsQuery, evaluationsQuery]
  if (baseQueries.some((query) => query.isLoading)) return <ResearchLoading label="stored evaluation results" />
  const failedQuery = baseQueries.find((query) => query.isError)
  if (failedQuery) {
    return <ResearchFailure message={failedQuery.error.message} onRetry={() => { void Promise.all(baseQueries.map((query) => query.refetch())) }} />
  }
  const summary = summaryQuery.data
  const evaluations = evaluationsQuery.data ?? []
  if (!summary || models.length === 0 || evaluations.length === 0) {
    return <main className="research-page"><header className="research-page-heading"><p className="eyebrow">Research findings</p><h1>Research Results</h1></header><ResearchEmpty>No stored models or evaluation results are available for this dataset.</ResearchEmpty></main>
  }

  const modelContent = modelsQuery.data?.content ?? []
  return (
    <main className="research-page">
      <header className="research-page-heading">
        <div><p className="eyebrow">Empirical evaluation · Dataset #{summary.id}</p><h1>Research Results</h1>
          <p>Held-out temporal evaluation of activity-only and extended feature models across the stored repository cohort.</p></div>
        <span className="research-ethics-tag">Observational results · no causal claims</span>
      </header>
      <DatasetOverview summary={summary.summary} datasetId={summary.id} versionHash={summary.versionHash} />
      <ModelPrAucChart models={modelContent} evaluations={evaluations} />
      <section className="research-panel" aria-labelledby="model-table-title">
        <div className="research-panel-heading"><div><p className="eyebrow">All stored model runs</p><h2 id="model-table-title">Evaluation comparison</h2></div><span className="research-tag">Test results · overall stratum</span></div>
        <div className="table-scroll-region">
          <table className="research-table model-table">
            <caption>Stored model metrics on the held-out test split; validation PR-AUC is displayed only as the selection metric</caption>
            <thead><tr><th scope="col">Model</th><th scope="col">Selection</th><th scope="col">Validation PR-AUC</th><th scope="col">Test PR-AUC</th><th scope="col">Test ROC-AUC</th><th scope="col">Test precision</th><th scope="col">Test recall</th><th scope="col">Test F1</th><th scope="col">Test Brier</th></tr></thead>
            <tbody>{modelContent.map((model) => (
              <tr key={model.id} className={model.selected ? 'selected-model-row' : undefined}>
                <th scope="row">{model.featureSet.replaceAll('_', ' ')} · {model.algorithm.replaceAll('_', ' ')} <small>Model #{model.id}</small></th>
                <td>{model.selected ? 'Selected on validation' : 'Candidate'}</td>
                <MetricCell row={evaluationFor(evaluations, model.id, 'pr_auc', 'validation')} />
                <MetricCell row={evaluationFor(evaluations, model.id, 'pr_auc', 'test')} />
                <MetricCell row={evaluationFor(evaluations, model.id, 'roc_auc', 'test')} />
                <MetricCell row={evaluationFor(evaluations, model.id, 'precision', 'test')} />
                <MetricCell row={evaluationFor(evaluations, model.id, 'recall', 'test')} />
                <MetricCell row={evaluationFor(evaluations, model.id, 'f1', 'test')} />
                <MetricCell row={evaluationFor(evaluations, model.id, 'brier_score', 'test')} />
              </tr>
            ))}</tbody>
          </table>
        </div>
        <p className="research-footnote">Intervals are 95% repository-cluster bootstrap intervals. Lower Brier scores indicate better probability error. The held-out test results are reported once and do not select the stored models.</p>
      </section>
      <PairComparison models={modelContent} evaluations={evaluations} />
      <RobustnessAnalysis models={modelContent} evaluations={evaluations} />
      <SizeBreakdown models={modelContent} evaluations={evaluations} />
      <CalibrationChart models={modelContent} evaluations={evaluations} />
      <FeatureImportancePanel
        models={modelContent}
        model={selectedImportanceModel}
        data={importanceQuery.data}
        isLoading={importanceQuery.isLoading}
        error={importanceQuery.error}
        onModelChange={setImportanceModelId}
        onRetry={() => void importanceQuery.refetch()}
      />
      <p className="research-note">Results are specific to this versioned cohort and experiment. The held-out test set contains repeated snapshots from the same repositories; intervals resample repositories to reflect this clustering.</p>
    </main>
  )
}
