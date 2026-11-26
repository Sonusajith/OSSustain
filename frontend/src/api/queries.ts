import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

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
  getAnalysis,
  submitAnalysis,
  getCurrentUser,
  login,
  logout,
  changePassword,
  getAdminUsers,
  createAdminUser,
  setAdminUserEnabled,
  getAdminAnalyses,
  cancelAdminAnalysis,
} from './client'
import { getPublicRepository, searchPublicRepositories } from './githubRepositories'

export const cohortQueryKeys = {
  currentUser: ['auth', 'current-user'] as const,
  adminUsers: ['admin', 'users'] as const,
  adminAnalyses: ['admin', 'analyses'] as const,
  analysis: (id: string) => ['analysis', id] as const,
  repositorySearch: (query: string) => ['github', 'repository-search', query] as const,
  publicRepository: (owner: string, repository: string) => ['github', 'repository', owner, repository] as const,
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

export function usePublicRepositorySearch(query: string, enabled: boolean) {
  return useQuery({
    queryKey: cohortQueryKeys.repositorySearch(query),
    queryFn: ({ signal }) => searchPublicRepositories(query, signal),
    enabled,
    staleTime: 60_000,
    retry: false,
  })
}

export function usePublicRepository(owner: string, repository: string, enabled: boolean) {
  return useQuery({
    queryKey: cohortQueryKeys.publicRepository(owner, repository),
    queryFn: ({ signal }) => getPublicRepository(owner, repository, signal),
    enabled,
    staleTime: 60_000,
    retry: false,
  })
}

export function useCurrentUser() {
  return useQuery({
    queryKey: cohortQueryKeys.currentUser,
    queryFn: ({ signal }) => getCurrentUser(signal),
    retry: false,
    staleTime: 30_000,
  })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: login,
    onSuccess: (user) => queryClient.setQueryData(cohortQueryKeys.currentUser, user),
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.setQueryData(cohortQueryKeys.currentUser, null)
      void queryClient.invalidateQueries({ queryKey: cohortQueryKeys.adminUsers })
      void queryClient.invalidateQueries({ queryKey: cohortQueryKeys.adminAnalyses })
    },
  })
}

export function useChangePassword() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: changePassword,
    onSuccess: (user) => queryClient.setQueryData(cohortQueryKeys.currentUser, user),
  })
}

export function useAdminUsers() {
  return useQuery({ queryKey: cohortQueryKeys.adminUsers, queryFn: ({ signal }) => getAdminUsers(0, 100, signal), retry: 1 })
}

export function useCreateAdminUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ username, role }: { username: string; role: 'ADMIN' | 'RESEARCHER' }) => createAdminUser(username, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cohortQueryKeys.adminUsers }),
  })
}

export function useSetAdminUserEnabled() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => setAdminUserEnabled(id, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cohortQueryKeys.adminUsers }),
  })
}

export function useAdminAnalyses() {
  return useQuery({ queryKey: cohortQueryKeys.adminAnalyses, queryFn: ({ signal }) => getAdminAnalyses(0, 100, signal), retry: 1 })
}

export function useCancelAdminAnalysis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: cancelAdminAnalysis,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cohortQueryKeys.adminAnalyses }),
  })
}

export function useSubmitAnalysis() {
  return useMutation({ mutationFn: submitAnalysis })
}

export function useAnalysis(id: string | undefined) {
  return useQuery({
    queryKey: cohortQueryKeys.analysis(id ?? ''),
    queryFn: ({ signal }) => getAnalysis(id ?? '', signal),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'queued' || status === 'running' ? 2000 : false
    },
    retry: 1,
  })
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
