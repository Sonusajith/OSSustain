import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useDatasetSummary, useRepositories } from '../../api/queries'
import { CohortFilters } from './CohortFilters'
import { CohortSummary } from './CohortSummary'
import { filterAndSortRepositories, readCohortFilters, writeFilter } from './cohortState'
import type { RepositorySort } from './cohortState'
import { RepositoryTable } from './RepositoryTable'

const PAGE_SIZE = 10

function LoadingState() {
  return (
    <main className="cohort-main" aria-busy="true" aria-live="polite">
      <div className="page-heading">
        <p className="eyebrow">Research cohort</p>
        <h1>Cohort overview</h1>
        <p className="page-description">Loading repository and dataset information…</p>
      </div>
      <div className="loading-summary" aria-hidden="true">
        {Array.from({ length: 4 }, (_, index) => <div className="loading-card" key={index} />)}
      </div>
      <div className="loading-table" aria-hidden="true">
        <div className="loading-line" />
        <div className="loading-line" />
        <div className="loading-line" />
      </div>
    </main>
  )
}

export function CohortOverview() {
  const [searchParams, setSearchParams] = useSearchParams()
  const repositoriesQuery = useRepositories()
  const datasetQuery = useDatasetSummary()
  const filters = useMemo(() => readCohortFilters(searchParams), [searchParams])

  if (repositoriesQuery.isPending || datasetQuery.isPending) return <LoadingState />

  if (repositoriesQuery.error || datasetQuery.error || !repositoriesQuery.data || !datasetQuery.data) {
    const error = repositoriesQuery.error ?? datasetQuery.error
    return (
      <main className="cohort-main">
        <div className="page-heading">
          <p className="eyebrow">Research cohort</p>
          <h1>Cohort overview</h1>
        </div>
        <section className="state-panel error-panel" role="alert">
          <span className="state-icon" aria-hidden="true">!</span>
          <div>
            <h2>We couldn’t load the cohort</h2>
            <p>{error instanceof Error ? error.message : 'The API did not return the cohort data.'}</p>
            <button
              className="primary-button"
              type="button"
              onClick={() => {
                void repositoriesQuery.refetch()
                void datasetQuery.refetch()
              }}
            >
              Try again
            </button>
          </div>
        </section>
      </main>
    )
  }

  const repositories = repositoriesQuery.data
  const filteredRepositories = filterAndSortRepositories(repositories, filters)
  const pageCount = Math.ceil(filteredRepositories.length / PAGE_SIZE)
  const currentPage = pageCount ? Math.min(filters.page, pageCount - 1) : 0
  const visibleRepositories = filteredRepositories.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE)
  const hasActiveFilters = Boolean(
    filters.query || filters.risk !== 'all' || filters.sizeGroup !== 'all' || filters.quality !== 'all',
  )
  const firstRow = filteredRepositories.length ? currentPage * PAGE_SIZE + 1 : 0
  const lastRow = Math.min((currentPage + 1) * PAGE_SIZE, filteredRepositories.length)

  function changeFilter(key: string, value: string) {
    setSearchParams((current) => writeFilter(current, key, value), { replace: true })
  }

  function changePage(nextPage: number) {
    setSearchParams((current) => writeFilter(current, 'page', String(nextPage), false), { replace: true })
  }

  function changeSort(sort: RepositorySort) {
    const nextDirection = filters.sort === sort && filters.direction === 'asc' ? 'desc' : 'asc'
    setSearchParams((current) => {
      const next = writeFilter(current, 'sort', sort)
      next.set('direction', nextDirection)
      return next
    }, { replace: true })
  }

  function clearFilters() {
    setSearchParams(new URLSearchParams(), { replace: true })
  }

  return (
    <main className="cohort-main">
      <div className="page-heading">
        <div>
          <p className="eyebrow">OSSustain · research cohort</p>
          <h1>Cohort overview</h1>
          <p className="page-description">
            Browse repository activity-risk estimates from the latest stored research dataset.
          </p>
        </div>
        <div className="estimation-mode">
          <span className="verified-mark" aria-hidden="true">✓</span>
          <span><small>Estimation mode</small><strong>Correlational / descriptive</strong></span>
        </div>
      </div>

      <CohortSummary dataset={datasetQuery.data} repositories={repositories} />

      <section className="repository-section" aria-labelledby="repository-section-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Repository records</p>
            <h2 id="repository-section-title">Selected cohort</h2>
          </div>
          <span className="dataset-chip">
            Dataset #{datasetQuery.data.id ?? '—'} · {repositories.length} repositories
          </span>
        </div>

        <CohortFilters filters={filters} onChange={changeFilter} onClear={clearFilters} />

        <div className="results-toolbar">
          <p aria-live="polite">
            Showing <strong>{firstRow}–{lastRow}</strong> of <strong>{filteredRepositories.length}</strong>
            {hasActiveFilters ? ' matching repositories' : ' repositories'}
          </p>
          {hasActiveFilters && <span className="filter-note">Filters are saved in the page URL</span>}
        </div>

        {repositories.length === 0 ? (
          <section className="state-panel empty-panel" aria-live="polite">
            <span className="state-icon" aria-hidden="true">∅</span>
            <div><h2>No repositories in this dataset</h2><p>The latest dataset has no cohort repository records.</p></div>
          </section>
        ) : filteredRepositories.length === 0 ? (
          <section className="state-panel empty-panel" aria-live="polite">
            <span className="state-icon" aria-hidden="true">⌕</span>
            <div>
              <h2>No matching repositories</h2>
              <p>Try changing your search or filters.</p>
              <button className="text-button" type="button" onClick={clearFilters}>Clear all filters</button>
            </div>
          </section>
        ) : (
          <>
            <RepositoryTable
              repositories={visibleRepositories}
              sort={filters.sort}
              direction={filters.direction}
              onSort={changeSort}
            />
            <div className="pagination-bar" aria-label="Repository pages">
              <span>Page {currentPage + 1} of {pageCount}</span>
              <div className="pagination-actions">
                <button type="button" onClick={() => changePage(currentPage - 1)} disabled={currentPage === 0}>
                  Previous
                </button>
                <button type="button" onClick={() => changePage(currentPage + 1)} disabled={currentPage >= pageCount - 1}>
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      <aside className="methodology-note" aria-label="Prediction interpretation">
        <span className="note-mark" aria-hidden="true">i</span>
        <p>
          Risk categories are relative to this cohort and summarize predicted contribution-activity decline over 90 days.
          Probabilities and associated indicators are observational and do not establish causes or project abandonment.
        </p>
      </aside>
    </main>
  )
}
