import type { ChangeEvent } from 'react'

import type { CohortFilters as FilterState } from './cohortState'

interface CohortFiltersProps {
  filters: FilterState
  onChange: (key: string, value: string) => void
  onClear: () => void
}

export function CohortFilters({ filters, onChange, onClear }: CohortFiltersProps) {
  const update = (key: string) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    onChange(key, event.currentTarget.value)
  }
  const hasFilters = Boolean(
    filters.query || filters.risk !== 'all' || filters.sizeGroup !== 'all' || filters.quality !== 'all',
  )

  return (
    <form className="filter-panel" aria-label="Filter repository cohort" onSubmit={(event) => event.preventDefault()}>
      <div className="filter-field search-field">
        <label htmlFor="repository-search">Search repository</label>
        <div className="search-input-wrap">
          <span className="search-mark" aria-hidden="true">⌕</span>
          <input
            id="repository-search"
            type="search"
            maxLength={100}
            placeholder="e.g. facebook/react"
            value={filters.query}
            onChange={update('q')}
          />
        </div>
      </div>

      <div className="filter-field">
        <label htmlFor="risk-filter">Risk category</label>
        <select id="risk-filter" value={filters.risk} onChange={update('risk')}>
          <option value="all">All categories</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      <div className="filter-field">
        <label htmlFor="size-filter">Size group</label>
        <select id="size-filter" value={filters.sizeGroup} onChange={update('sizeGroup')}>
          <option value="all">All sizes</option>
          <option value="small">Small</option>
          <option value="medium">Medium</option>
          <option value="large">Large</option>
        </select>
      </div>

      <div className="filter-field">
        <label htmlFor="quality-filter">Data quality</label>
        <select id="quality-filter" value={filters.quality} onChange={update('quality')}>
          <option value="all">All records</option>
          <option value="flagged">Flagged</option>
          <option value="clear">No flags</option>
        </select>
      </div>

      <div className="filter-field sort-field">
        <label htmlFor="sort-filter">Sort by</label>
        <select id="sort-filter" value={filters.sort} onChange={update('sort')}>
          <option value="fullName">Repository name</option>
          <option value="riskCategory">Risk category</option>
          <option value="stars">Stars at selection</option>
          <option value="predictionDate">Prediction date</option>
        </select>
      </div>

      <div className="filter-field direction-field">
        <label htmlFor="direction-filter">Order</label>
        <select id="direction-filter" value={filters.direction} onChange={update('direction')}>
          <option value="asc">Ascending</option>
          <option value="desc">Descending</option>
        </select>
      </div>

      {hasFilters && (
        <button className="clear-filters" type="button" onClick={onClear}>
          Clear filters
        </button>
      )}
    </form>
  )
}
