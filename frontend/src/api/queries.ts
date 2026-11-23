import { useQuery } from '@tanstack/react-query'

import {
  getDatasetSummary,
  getAllEvaluations,
  getFeatureImportance,
  getLabelDefinition,
  getLatestPrediction,
  getPredictionHistory,
  getRepositories,
  getResearchModels,
  getRepositoryDetail,
  getRepositoryComparison,
  getRepositoryMetrics,
} from './client'

export const cohortQueryKeys = {
  repositories: ['cohort', 'repositories'] as const,
  datasetSummary: ['cohort', 'dataset-summary'] as const,
  repository: (id: number) => ['repository', id] as const,
  repositoryMetrics: (id: number) => ['repository', id, 'metrics'] as const,
  comparison: (ids: number[]) => ['comparison', ...ids] as const,
  repositoryPrediction: (id: number) => ['repository', id, 'latest-prediction'] as const,
  repositoryHistory: (id: number) => ['repository', id, 'prediction-history'] as const,
  researchModels: ['research', 'models'] as const,
  researchEvaluations: ['research', 'evaluations'] as const,
  researchImportance: (modelVersionId: number) => ['research', 'importance', modelVersionId] as const,
  researchLabelDefinition: ['research', 'label-definition'] as const,
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

export function useResearchModels() {
  return useQuery({
    queryKey: cohortQueryKeys.researchModels,
    queryFn: ({ signal }) => getResearchModels(signal),
    staleTime: 60_000,
    retry: 1,
  })
}

export function useResearchEvaluations() {
  return useQuery({
    queryKey: cohortQueryKeys.researchEvaluations,
    queryFn: ({ signal }) => getAllEvaluations(signal),
    staleTime: 60_000,
    retry: 1,
  })
}

export function useResearchFeatureImportance(modelVersionId: number, enabled: boolean) {
  return useQuery({
    queryKey: cohortQueryKeys.researchImportance(modelVersionId),
    queryFn: ({ signal }) => getFeatureImportance(modelVersionId, signal),
    enabled,
    staleTime: 60_000,
    retry: 1,
  })
}

export function useLabelDefinition() {
  return useQuery({
    queryKey: cohortQueryKeys.researchLabelDefinition,
    queryFn: ({ signal }) => getLabelDefinition(signal),
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

export function useRepositoryComparison(repositoryIds: number[], enabled: boolean) {
  return useQuery({
    queryKey: cohortQueryKeys.comparison(repositoryIds),
    queryFn: ({ signal }) => getRepositoryComparison(repositoryIds, signal),
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
