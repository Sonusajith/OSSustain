import { Link } from 'react-router-dom'

import type { Repository } from '../../api/client'
import type { RepositorySort, SortDirection } from './cohortState'

interface RepositoryTableProps {
  repositories: readonly Repository[]
  sort: RepositorySort
  direction: SortDirection
  onSort: (sort: RepositorySort) => void
}

const columns: { key: RepositorySort; label: string }[] = [
  { key: 'fullName', label: 'Repository' },
  { key: 'stars', label: 'Stars at selection' },
  { key: 'riskCategory', label: 'Risk category' },
  { key: 'predictionDate', label: 'Prediction date' },
]

function SortHeading({
  column,
  sort,
  direction,
  onSort,
}: {
  column: (typeof columns)[number]
  sort: RepositorySort
  direction: SortDirection
  onSort: (sort: RepositorySort) => void
}) {
  const active = column.key === sort
  const ariaSort = active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'
  return (
    <th scope="col" aria-sort={ariaSort}>
      <button className="table-sort-button" type="button" onClick={() => onSort(column.key)}>
        {column.label}<span aria-hidden="true">{active ? (direction === 'asc' ? ' ↑' : ' ↓') : ''}</span>
      </button>
    </th>
  )
}

function RiskBadge({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="risk-badge risk-unavailable">No prediction</span>
  const label = `${value[0]?.toUpperCase()}${value.slice(1)} risk`
  return <span className={`risk-badge risk-${value}`}>{label}</span>
}

export function RepositoryTable({ repositories, sort, direction, onSort }: RepositoryTableProps) {
  return (
    <div className="table-scroll-region" role="region" aria-label="Repository cohort results" tabIndex={0}>
      <table className="repository-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <SortHeading key={column.key} column={column} sort={sort} direction={direction} onSort={onSort} />
            ))}
            <th scope="col">Probability</th>
            <th scope="col">Size group</th>
            <th scope="col">Data quality</th>
          </tr>
        </thead>
        <tbody>
          {repositories.map((repository) => {
            const flags = repository.dataQualityFlags ?? []
            const name = repository.fullName ?? 'Repository name unavailable'
            return (
              <tr key={repository.id ?? name}>
                <th scope="row">
                  <Link className="repository-link" to={`/repositories/${repository.id ?? ''}`}>
                    <span className="repo-mark" aria-hidden="true">◉</span>
                    <span>{name}</span>
                  </Link>
                </th>
                <td className="numeric-cell">{repository.stars === undefined ? '—' : new Intl.NumberFormat().format(repository.stars)}</td>
                <td><RiskBadge value={repository.latestRiskCategory} /></td>
                <td>
                  {repository.predictionDate ? (
                    <time dateTime={repository.predictionDate}>{repository.predictionDate}</time>
                  ) : '—'}
                </td>
                <td className="probability-cell">
                  {repository.latestProbability === null || repository.latestProbability === undefined
                    ? '—'
                    : `${(repository.latestProbability * 100).toFixed(1)}%`}
                </td>
                <td><span className="size-label">{repository.sizeGroup ?? 'Unknown'}</span></td>
                <td>
                  {flags.length ? (
                    <span className="quality-flag" title={flags.join(', ')}>
                      <span aria-hidden="true">⚑</span> Flagged <span className="flag-count">{flags.length}</span>
                    </span>
                  ) : <span className="quality-clear"><span aria-hidden="true">✓</span> No flags</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
