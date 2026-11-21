import type { Repository } from '../../api/client'

export type RiskFilter = 'all' | 'high' | 'medium' | 'low'
export type SizeFilter = 'all' | 'small' | 'medium' | 'large'
export type QualityFilter = 'all' | 'flagged' | 'clear'
export type RepositorySort = 'fullName' | 'stars' | 'riskCategory' | 'predictionDate'
export type SortDirection = 'asc' | 'desc'

export interface CohortFilters {
  query: string
  risk: RiskFilter
  sizeGroup: SizeFilter
  quality: QualityFilter
  sort: RepositorySort
  direction: SortDirection
  page: number
}

const risks: RiskFilter[] = ['all', 'high', 'medium', 'low']
const sizes: SizeFilter[] = ['all', 'small', 'medium', 'large']
const qualities: QualityFilter[] = ['all', 'flagged', 'clear']
const sorts: RepositorySort[] = ['fullName', 'stars', 'riskCategory', 'predictionDate']

export function readCohortFilters(params: URLSearchParams): CohortFilters {
  const risk = params.get('risk') as RiskFilter | null
  const sizeGroup = params.get('sizeGroup') as SizeFilter | null
  const quality = params.get('quality') as QualityFilter | null
  const sort = params.get('sort') as RepositorySort | null
  const direction = params.get('direction') as SortDirection | null
  const page = Number.parseInt(params.get('page') ?? '0', 10)

  return {
    query: (params.get('q') ?? '').slice(0, 100),
    risk: risk && risks.includes(risk) ? risk : 'all',
    sizeGroup: sizeGroup && sizes.includes(sizeGroup) ? sizeGroup : 'all',
    quality: quality && qualities.includes(quality) ? quality : 'all',
    sort: sort && sorts.includes(sort) ? sort : 'fullName',
    direction: direction === 'desc' ? 'desc' : 'asc',
    page: Number.isFinite(page) && page >= 0 ? page : 0,
  }
}

function riskRank(value: string | null | undefined): number {
  if (value === 'high') return 3
  if (value === 'medium') return 2
  if (value === 'low') return 1
  return 0
}

export function filterAndSortRepositories(
  repositories: readonly Repository[],
  filters: CohortFilters,
): Repository[] {
  const search = filters.query.trim().toLocaleLowerCase()
  const rows = repositories.filter((repository) => {
    const matchesSearch = !search || (repository.fullName ?? '').toLocaleLowerCase().includes(search)
    const matchesRisk = filters.risk === 'all' || repository.latestRiskCategory === filters.risk
    const matchesSize = filters.sizeGroup === 'all' || repository.sizeGroup === filters.sizeGroup
    const hasFlags = (repository.dataQualityFlags?.length ?? 0) > 0
    const matchesQuality =
      filters.quality === 'all' ||
      (filters.quality === 'flagged' ? hasFlags : !hasFlags)
    return matchesSearch && matchesRisk && matchesSize && matchesQuality
  })

  const direction = filters.direction === 'asc' ? 1 : -1
  rows.sort((left, right) => {
    const primaryComparison = (() => {
      switch (filters.sort) {
        case 'stars':
          return (left.stars ?? 0) - (right.stars ?? 0)
        case 'riskCategory':
          return riskRank(left.latestRiskCategory) - riskRank(right.latestRiskCategory)
        case 'predictionDate':
          return (left.predictionDate ?? '').localeCompare(right.predictionDate ?? '')
        default:
          return (left.fullName ?? '').localeCompare(right.fullName ?? '')
      }
    })()
    const comparison = primaryComparison || (left.fullName ?? '').localeCompare(right.fullName ?? '')
    return comparison * direction
  })
  return rows
}

export function writeFilter(
  params: URLSearchParams,
  key: string,
  value: string,
  resetPage = true,
): URLSearchParams {
  const next = new URLSearchParams(params)
  if (value) next.set(key, value)
  else next.delete(key)
  if (resetPage) next.delete('page')
  return next
}
