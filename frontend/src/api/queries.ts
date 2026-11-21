import { useQuery } from '@tanstack/react-query'

import {
  getDatasetSummary,
  getLatestPrediction,
  getPredictionHistory,
  getRepositories,
  getRepositoryDetail,
  getRepositoryMetrics,
} from './client'

export const cohortQueryKeys = {
  repositories: ['cohort', 'repositories'] as const,
  datasetSummary: ['cohort', 'dataset-summary'] as const,
  repository: (id: number) => ['repository', id] as const,
  repositoryMetrics: (id: number) => ['repository', id, 'metrics'] as const,
  repositoryPrediction: (id: number) => ['repository', id, 'latest-prediction'] as const,
  repositoryHistory: (id: number) => ['repository', id, 'prediction-history'] as const,
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

export function useRepositoryDetail(repositoryId: number, enabled: boolean) {
  return useQuery({
    queryKey: cohortQueryKeys.repository(repositoryId),
    queryFn: ({ signal }) => getRepositoryDetail(repositoryId, signal),
    enabled,
    staleTime: 60_000,
    retry: 1,
  })
}

export function useRepositoryMetrics(repositoryId: number, enabled: boolean) {
  return useQuery({
    queryKey: cohortQueryKeys.repositoryMetrics(repositoryId),
    queryFn: ({ signal }) => getRepositoryMetrics(repositoryId, signal),
    enabled,
    staleTime: 60_000,
    retry: 1,
  })
}

export function useLatestPrediction(repositoryId: number, enabled: boolean) {
  return useQuery({
    queryKey: cohortQueryKeys.repositoryPrediction(repositoryId),
    queryFn: ({ signal }) => getLatestPrediction(repositoryId, signal),
    enabled,
    staleTime: 60_000,
    retry: 1,
  })
}

export function usePredictionHistory(repositoryId: number, enabled: boolean) {
  return useQuery({
    queryKey: cohortQueryKeys.repositoryHistory(repositoryId),
    queryFn: ({ signal }) => getPredictionHistory(repositoryId, signal),
    enabled,
    staleTime: 60_000,
    retry: 1,
  })
}
