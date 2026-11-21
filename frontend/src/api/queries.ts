import { useQuery } from '@tanstack/react-query'

import { getDatasetSummary, getRepositories } from './client'

export const cohortQueryKeys = {
  repositories: ['cohort', 'repositories'] as const,
  datasetSummary: ['cohort', 'dataset-summary'] as const,
}

export function useRepositories() {
  return useQuery({
    queryKey: cohortQueryKeys.repositories,
    queryFn: ({ signal }) => getRepositories(signal),
    staleTime: 60_000,
    retry: 1,
  })
}

export function useDatasetSummary() {
  return useQuery({
    queryKey: cohortQueryKeys.datasetSummary,
    queryFn: ({ signal }) => getDatasetSummary(signal),
    staleTime: 60_000,
    retry: 1,
  })
}
