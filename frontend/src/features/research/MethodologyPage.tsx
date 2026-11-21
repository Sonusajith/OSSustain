import { useMemo, useState } from 'react'

import type { LabelDefinition } from '../../api/client'
import { useDatasetSummary, useLabelDefinition } from '../../api/queries'
import { ResearchEmpty, ResearchFailure, ResearchLoading } from './ResearchPageState'
import { asArray, asNumber, asRecord, formatCount, formatRate, humanize, nestedRecord } from './researchFormat'

function Field({ label, value }: { label: string; value: unknown }) {
  const shown = typeof value === 'boolean' ? (value ? 'Yes' : 'No') : typeof value === 'string' || typeof value === 'number' ? String(value) : '—'
  return <div className="method-field"><dt>{label}</dt><dd>{shown}</dd></div>
}

function SplitDesign({ splits }: { splits: unknown }) {
  const entries = Object.entries(asRecord(splits))
  if (!entries.length) return <ResearchEmpty>No chronological split definition is recorded.</ResearchEmpty>
  return (
    <div className="table-scroll-region">
      <table className="research-table">
        <caption>Prediction date ranges for each chronological split</caption>
        <thead><tr><th scope="col">Split</th><th scope="col">Start</th><th scope="col">End</th><th scope="col">Purpose</th></tr></thead>
        <tbody>{entries.map(([name, raw]) => {
          const split = asRecord(raw)
          return <tr key={name}><th scope="row">{humanize(name)}</th><td>{String(split.start ?? '—')}</td><td>{String(split.end ?? '—')}</td><td>{name === 'test' ? 'Final held-out evaluation' : name === 'validation' ? 'Model selection and threshold setting' : 'Model fitting'}</td></tr>
        })}</tbody>
      </table>
    </div>
  )
}

function SensitivityTable({ summary }: { summary: unknown }) {
  const overall = nestedRecord(summary, 'overall', 'thresholds')
  const test = nestedRecord(summary, 'by_split', 'test', 'thresholds')
  const thresholds = ['0.3', '0.5', '0.7'].filter((threshold) => overall[threshold] !== undefined || test[threshold] !== undefined)
  if (!thresholds.length) return <ResearchEmpty>No threshold sensitivity counts are available in this dataset summary.</ResearchEmpty>
  return (
    <div className="table-scroll-region">
      <table className="research-table">
        <caption>Observed label prevalence under the configured decline thresholds</caption>
        <thead><tr><th scope="col">θ</th><th scope="col">Overall positive</th><th scope="col">Overall prevalence</th><th scope="col">Test positive</th><th scope="col">Test prevalence</th></tr></thead>
        <tbody>{thresholds.map((threshold) => {
          const all = asRecord(overall[threshold])
          const heldOut = asRecord(test[threshold])
          return <tr key={threshold}><th scope="row">{threshold}</th><td>{formatCount(all.positive)}</td><td>{formatRate(all.prevalence)}</td><td>{formatCount(heldOut.positive)}</td><td>{formatRate(heldOut.prevalence)}</td></tr>
        })}</tbody>
      </table>
    </div>
  )
}

function QualityFlags({ summary }: { summary: unknown }) {
  const rawFlags = asArray(asRecord(summary).quality_flags).map(asRecord)
  const grouped = new Map<string, string[]>()
  for (const entry of rawFlags) {
    const names = asArray(entry.flags).filter((value): value is string => typeof value === 'string')
    for (const name of names) grouped.set(name, [...(grouped.get(name) ?? []), String(entry.full_name ?? 'Repository')])
  }
  if (!grouped.size) return <ResearchEmpty>No dataset quality flags are recorded.</ResearchEmpty>
  return (
    <ul className="quality-flag-list">
      {[...grouped.entries()].map(([name, repositories]) => <li key={name}>
        <strong>{humanize(name)} · {repositories.length} {repositories.length === 1 ? 'repository' : 'repositories'}</strong>
        <span>{repositories.join(', ')}</span>
      </li>)}
    </ul>
  )
}

function FeatureDictionary({ definition }: { definition: LabelDefinition }) {
  const [search, setSearch] = useState('')
  const features = definition.featureDictionary
  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase()
    return features.filter((feature) => !query || [feature.featureName, feature.featureGroup, feature.description, feature.timeWindow, feature.missingPolicy].some((value) => value.toLocaleLowerCase().includes(query)))
  }, [features, search])
  if (!features.length) return <ResearchEmpty>No feature definitions are recorded for this dataset.</ResearchEmpty>
  return (
    <>
      <label className="feature-search">Filter features
        <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Name, group, or description" />
      </label>
      {!filtered.length ? <ResearchEmpty>No features match this filter.</ResearchEmpty> : (
        <div className="table-scroll-region">
          <table className="research-table feature-dictionary-table">
            <caption>Feature definitions in the stored versioned experiment</caption>
            <thead><tr><th scope="col">Feature</th><th scope="col">Group</th><th scope="col">Description</th><th scope="col">Time window</th><th scope="col">Missing data policy</th></tr></thead>
            <tbody>{filtered.map((feature) => <tr key={feature.featureName}>
              <th scope="row">{humanize(feature.featureName)}</th><td>{humanize(feature.featureGroup)}</td><td>{feature.description}</td><td>{feature.timeWindow}</td><td>{feature.missingPolicy}</td>
            </tr>)}</tbody>
          </table>
        </div>
      )}
      <p className="research-footnote">Showing {filtered.length} of {features.length} documented features.</p>
    </>
  )
}

function MethodologyContent({ definition, summary }: { definition: LabelDefinition; summary: unknown }) {
  const label = asRecord(definition.label)
  const protocol = asRecord(definition.protocol)
  const sensitivity = asArray(label.sensitivity_theta).map((value) => asNumber(value)).filter((value): value is number => value !== undefined)
  const splitValues = Object.values(asRecord(definition.splits))
  const observationStart = protocol.observation_start
  const observationEnd = protocol.observation_end
  const snapshotInterval = protocol.snapshot_interval_days
  return (
    <>
      <section className="method-overview">
        <div><p className="eyebrow">Outcome definition · Dataset #{definition.datasetVersionId}</p><h2>What counts as a decline?</h2>
          <p>A positive label means non-bot commits to the default branch in the next 90 days are at most θ times the commits in the preceding 90 days. It measures contribution activity; it does not mean a repository is abandoned.</p>
        </div>
        <dl className="method-fields">
          <Field label="Primary threshold (θ)" value={label.theta} />
          <Field label="Reference activity window" value={typeof label.reference_window_days === 'number' ? `${label.reference_window_days} days` : undefined} />
          <Field label="Future outcome window" value={typeof label.future_window_days === 'number' ? `${label.future_window_days} days` : undefined} />
          <Field label="Minimum reference commits" value={label.min_reference_commits} />
          <Field label="Activity definition" value={humanize(label.activity_definition)} />
          <Field label="Sensitivity thresholds" value={sensitivity.length ? sensitivity.join(', ') : '—'} />
        </dl>
      </section>

      <section className="research-panel" aria-labelledby="split-title">
        <div className="research-panel-heading"><div><p className="eyebrow">Time-ordered evaluation</p><h2 id="split-title">Study period and split design</h2></div><span className="research-tag">Protocol {String(protocol.protocol_version ?? '—')}</span></div>
        <dl className="method-inline-facts"><Field label="Observation period" value={observationStart && observationEnd ? `${observationStart} to ${observationEnd}` : undefined} /><Field label="Snapshot interval" value={typeof snapshotInterval === 'number' ? `${snapshotInterval} days` : undefined} /><Field label="Purge gap" value={typeof protocol.purge_gap_days === 'number' ? `${protocol.purge_gap_days} days` : undefined} /><Field label="Random seed" value={protocol.random_seed} /></dl>
        <SplitDesign splits={definition.splits} />
        <p className="research-footnote">There are {splitValues.length} chronological windows. Test outcomes are reserved for final reporting; the validation split is used for model selection.</p>
      </section>

      <section className="research-panel" aria-labelledby="sensitivity-title">
        <div className="research-panel-heading"><div><p className="eyebrow">Label prevalence</p><h2 id="sensitivity-title">Threshold sensitivity</h2></div><span className="research-tag">Dataset summary</span></div>
        <p className="research-footnote">Changing θ changes which snapshots are positive. Counts below come from the versioned dataset summary.</p>
        <SensitivityTable summary={summary} />
      </section>

      <section className="research-panel" aria-labelledby="features-title">
        <div className="research-panel-heading"><div><p className="eyebrow">Model inputs</p><h2 id="features-title">Feature dictionary</h2></div><span className="research-tag">{definition.featureDictionary.length} features</span></div>
        <FeatureDictionary definition={definition} />
      </section>

      <section className="research-panel" aria-labelledby="quality-title">
        <div className="research-panel-heading"><div><p className="eyebrow">Transparent data handling</p><h2 id="quality-title">Known data-quality flags</h2></div></div>
        <p className="research-footnote">Flags are retained in the dataset and predictions; they are disclosed rather than silently treated as complete observations.</p>
        <QualityFlags summary={summary} />
      </section>

      <section className="research-panel limitation-panel" aria-labelledby="limits-title">
        <div className="research-panel-heading"><div><p className="eyebrow">Interpretation</p><h2 id="limits-title">Limitations</h2></div></div>
        <ul>
          <li>The cohort contains 50 screened public repositories and is not representative of all GitHub projects.</li>
          <li>Monthly snapshots from the same repository are related. The held-out test set has only 12 repository clusters, so uncertainty remains broad.</li>
          <li>The activity label does not establish project health, abandonment, or the cause of any change.</li>
          <li>Results are observational and predictive; feature importance does not estimate causal effects.</li>
          <li>Any comparison between feature families is specific to this cohort, protocol, and stored experiment version.</li>
        </ul>
      </section>
    </>
  )
}

export function MethodologyPage() {
  const definitionQuery = useLabelDefinition()
  const summaryQuery = useDatasetSummary()
  const queries = [definitionQuery, summaryQuery]
  if (queries.some((query) => query.isLoading)) return <ResearchLoading label="study methodology and dataset records" />
  const failed = queries.find((query) => query.isError)
  if (failed) return <ResearchFailure message={failed.error.message} onRetry={() => { void Promise.all(queries.map((query) => query.refetch())) }} />
  const definition = definitionQuery.data
  const summary = summaryQuery.data?.summary
  if (!definition || !summary || definition.featureDictionary.length === 0 || Object.keys(asRecord(definition.splits)).length === 0) {
    return <main className="research-page"><header className="research-page-heading"><div><p className="eyebrow">Study protocol</p><h1>Methodology &amp; Limitations</h1></div></header><ResearchEmpty>The current dataset does not include its label, split, and feature dictionary records.</ResearchEmpty></main>
  }
  return (
    <main className="research-page methodology-page">
      <header className="research-page-heading"><div><p className="eyebrow">Versioned protocol · Dataset #{definition.datasetVersionId}</p><h1>Methodology &amp; Limitations</h1><p>Definitions, evaluation design, feature inputs, and known constraints for interpreting the results.</p></div><span className="research-ethics-tag">Version {String(asRecord(definition.protocol).protocol_version ?? '—')}</span></header>
      <MethodologyContent definition={definition} summary={summary} />
    </main>
  )
}
