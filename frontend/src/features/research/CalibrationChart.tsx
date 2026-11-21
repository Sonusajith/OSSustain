import type { Evaluation, ModelVersion } from '../../api/client'
import { asArray, asNumber, asRecord, formatCount } from './researchFormat'

interface CalibrationBin {
  bin: number
  count: number
  observedRate: number
  meanProbability: number
}

const palette = ['#1d4ed8', '#b45309']

function getBins(evaluation: Evaluation | undefined): CalibrationBin[] {
  const details = asRecord(evaluation?.details)
  return asArray(details.calibration_bins).flatMap((item) => {
    const bin = asRecord(item)
    const number = asNumber(bin.bin)
    const count = asNumber(bin.count)
    const observedRate = asNumber(bin.observed_rate)
    const meanProbability = asNumber(bin.mean_probability)
    return number === undefined || count === undefined || observedRate === undefined || meanProbability === undefined
      ? []
      : [{ bin: number, count, observedRate, meanProbability }]
  })
}

export function CalibrationChart({ models, evaluations }: { models: ModelVersion[]; evaluations: Evaluation[] }) {
  const chosen = models.filter((model) => model.selected && ['activity_only', 'extended'].includes(model.featureSet))
  const series = chosen.map((model, index) => ({
    model,
    color: palette[index % palette.length],
    bins: getBins(evaluations.find((row) => row.modelVersionId === model.id
      && row.split === 'test' && row.stratum === 'overall' && row.metric === 'calibration_curve')),
  })).filter((item) => item.bins.length > 0)
  const project = (value: number) => 26 + value * 250
  const projectY = (value: number) => 188 - value * 160

  if (!series.length) return <div className="research-state">No stored test calibration bins are available for the selected models.</div>

  return (
    <section className="research-panel" aria-labelledby="calibration-title">
      <div className="research-panel-heading">
        <div><p className="eyebrow">Held-out test set</p><h2 id="calibration-title">Calibration</h2></div>
        <span className="research-tag">Observed rate vs. mean predicted probability</span>
      </div>
      <div className="chart-legend" aria-label="Calibration series">
        {series.map(({ model, color }) => <span key={model.id}><i style={{ backgroundColor: color }} />{model.featureSet.replaceAll('_', ' ')} · {model.algorithm.replaceAll('_', ' ')}</span>)}
        <span><i className="legend-reference" />Perfect calibration reference</span>
      </div>
      <svg className="research-chart calibration-chart" viewBox="0 0 300 220" role="img" aria-label="Calibration chart comparing observed event rate with predicted probability for selected models on the held-out test set.">
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={tick}>
            <line x1="26" x2="276" y1={projectY(tick)} y2={projectY(tick)} className="chart-gridline" />
            <text x="20" y={projectY(tick) + 3} textAnchor="end" className="chart-tick">{Math.round(tick * 100)}%</text>
            <text x={project(tick)} y="204" textAnchor="middle" className="chart-tick">{Math.round(tick * 100)}%</text>
          </g>
        ))}
        <line x1={project(0)} y1={projectY(0)} x2={project(1)} y2={projectY(1)} className="calibration-reference" />
        <text x="152" y="218" textAnchor="middle" className="chart-axis-label">Mean predicted probability</text>
        <text x="9" y="108" textAnchor="middle" className="chart-axis-label" transform="rotate(-90 9 108)">Observed event rate</text>
        {series.map(({ model, color, bins }, seriesIndex) => (
          <g key={model.id} className="calibration-series">
            {bins.map((bin) => seriesIndex === 0
              ? <circle key={bin.bin} cx={project(bin.meanProbability)} cy={projectY(bin.observedRate)} r="4" fill={color}><title>{model.featureSet}: bin {bin.bin}, {bin.count} records, predicted {Math.round(bin.meanProbability * 100)}%, observed {Math.round(bin.observedRate * 100)}%</title></circle>
              : <rect key={bin.bin} x={project(bin.meanProbability) - 3.5} y={projectY(bin.observedRate) - 3.5} width="7" height="7" fill={color}><title>{model.featureSet}: bin {bin.bin}, {bin.count} records, predicted {Math.round(bin.meanProbability * 100)}%, observed {Math.round(bin.observedRate * 100)}%</title></rect>)}
          </g>
        ))}
      </svg>
      <details className="research-table-details">
        <summary>View calibration data table</summary>
        <div className="table-scroll-region">
          <table className="research-table">
            <caption>Test calibration bins: observed event rate and mean predicted probability</caption>
            <thead><tr><th scope="col">Model</th><th scope="col">Bin</th><th scope="col">Mean predicted probability</th><th scope="col">Observed event rate</th><th scope="col">Records</th></tr></thead>
            <tbody>{series.flatMap(({ model, bins }) => bins.map((bin) => (
              <tr key={`${model.id}-${bin.bin}`}>
                <th scope="row">{model.featureSet.replaceAll('_', ' ')} · {model.algorithm.replaceAll('_', ' ')}</th>
                <td>{bin.bin}</td><td>{(bin.meanProbability * 100).toFixed(1)}%</td><td>{(bin.observedRate * 100).toFixed(1)}%</td><td>{formatCount(bin.count)}</td>
              </tr>
            )))}</tbody>
          </table>
        </div>
      </details>
      <p className="research-footnote">Bins have different sample counts; sparse bins are noisy. The diagonal is a reference, not a fitted result.</p>
    </section>
  )
}
