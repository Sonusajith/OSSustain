import type { components, paths } from './generated'

export type Repository = components['schemas']['RepositorySummary']
export type RepositoryDetail = components['schemas']['RepositoryDetail']
export type RepositoryPage = paths['/repositories']['get']['responses'][200]['content']['application/json']
export type RepositoryMetrics = paths['/repositories/{id}/metrics']['get']['responses'][200]['content']['application/json']
export type RepositoryComparison = paths['/compare']['get']['responses'][200]['content']['application/json']
export type Prediction = components['schemas']['Prediction']
export type PredictionDetail = components['schemas']['PredictionDetail']
export type PredictionIndicator = PredictionDetail['indicators'][number]
export type PredictionHistory = paths['/repositories/{id}/predictions']['get']['responses'][200]['content']['application/json']
export type DatasetSummary = paths['/research/dataset-summary']['get']['responses'][200]['content']['application/json']
export type ModelVersion = components['schemas']['ModelVersion']
export type ModelPage = paths['/research/models']['get']['responses'][200]['content']['application/json']
export type Evaluation = components['schemas']['Evaluation']
export type EvaluationPage = paths['/research/evaluations']['get']['responses'][200]['content']['application/json']
export type FeatureImportance = components['schemas']['FeatureImportance']
export type FeatureImportancePage = paths['/research/feature-importance']['get']['responses'][200]['content']['application/json']
export type LabelDefinition = paths['/research/label-definition']['get']['responses'][200]['content']['application/json']
export type Analysis = components['schemas']['Analysis']
export type CsrfToken = components['schemas']['CsrfToken']
export type CurrentUser = components['schemas']['CurrentUser']
export type LoginRequest = components['schemas']['LoginRequest']
export type PasswordChangeRequest = components['schemas']['PasswordChangeRequest']
export type AdminUser = components['schemas']['AdminUser']
export type AdminUserPage = components['schemas']['AdminUserPage']
export type CreatedUser = components['schemas']['CreatedUser']
export type AdminAnalysisPage = components['schemas']['AdminAnalysisPage']

async function postJson<T>(url: string, body: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${url}`, {
      method: 'POST',
      credentials: 'include',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRF-TOKEN': (await getCsrfToken()).token },
      body: JSON.stringify(body),
    })
  } catch {
    throw new ApiRequestError('Could not connect to the OSSustain API. Check that the backend is running.')
  }
  if (!response.ok) throw await responseError(response)
  return (await response.json()) as T
}

async function patchJson<T>(url: string, body: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${url}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRF-TOKEN': (await getCsrfToken()).token },
      body: JSON.stringify(body),
    })
  } catch {
    throw new ApiRequestError('Could not connect to the OSSustain API. Check that the backend is running.')
  }
  if (!response.ok) throw await responseError(response)
  return (await response.json()) as T
}

async function postNoContent(url: string): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${url}`, {
      method: 'POST',
      credentials: 'include',
      headers: { Accept: 'application/json', 'X-CSRF-TOKEN': (await getCsrfToken()).token },
    })
  } catch {
    throw new ApiRequestError('Could not connect to the OSSustain API. Check that the backend is running.')
  }
  if (!response.ok) throw await responseError(response)
}

async function getCsrfToken(): Promise<CsrfToken> {
  return getJson<CsrfToken>('/auth/csrf')
}

async function responseError(response: Response): Promise<ApiRequestError> {
  let message = `The API request failed (${response.status}).`
  try { message = getMessage(await response.json()) ?? message } catch { /* Keep the status message. */ }
  return new ApiRequestError(message, response.status)
}

export async function getCurrentUser(signal?: AbortSignal): Promise<CurrentUser | null> {
  try { return await getJson<CurrentUser>('/auth/me', signal) }
  catch (error) {
    if (error instanceof ApiRequestError && error.status === 401) return null
    throw error
  }
}

export function login(request: LoginRequest): Promise<CurrentUser> { return postJson<CurrentUser>('/auth/login', request) }
export function logout(): Promise<void> { return postNoContent('/auth/logout') }
export function changePassword(request: PasswordChangeRequest): Promise<CurrentUser> {
  return postJson<CurrentUser>('/auth/password', request)
}
export function getAdminUsers(page = 0, pageSize = 50, signal?: AbortSignal): Promise<AdminUserPage> {
  return getJson<AdminUserPage>(`/admin/users?page=${page}&pageSize=${pageSize}`, signal)
}
export function createAdminUser(username: string, role: 'ADMIN' | 'RESEARCHER'): Promise<CreatedUser> {
  return postJson<CreatedUser>('/admin/users', { username, role })
}
export function setAdminUserEnabled(id: number, enabled: boolean): Promise<AdminUser> {
  return patchJson<AdminUser>(`/admin/users/${id}/enabled`, { enabled })
}
export function getAdminAnalyses(page = 0, pageSize = 50, signal?: AbortSignal): Promise<AdminAnalysisPage> {
  return getJson<AdminAnalysisPage>(`/admin/analyses?page=${page}&pageSize=${pageSize}`, signal)
}
export function cancelAdminAnalysis(id: string): Promise<Analysis> {
  return postJson<Analysis>(`/admin/analyses/${encodeURIComponent(id)}/cancel`, {})
}

export function submitAnalysis(repository: string): Promise<Analysis> {
  return postJson<Analysis>('/analyses', { repository })
}

export function getAnalysis(id: string, signal?: AbortSignal): Promise<Analysis> {
  return getJson<Analysis>(`/analyses/${encodeURIComponent(id)}`, signal)
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080/api/v1').replace(/\/$/, '')
const PAGE_SIZE = 100

export class ApiRequestError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

function getMessage(value: unknown): string | undefined {
  if (typeof value !== 'object' || value === null || !('message' in value)) return undefined
  return typeof value.message === 'string' ? value.message : undefined
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${url}`, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch {
    throw new ApiRequestError('Could not connect to the OSSustain API. Check that the backend is running.')
  }

  if (!response.ok) {
    let message = `The API request failed (${response.status}).`
    try {
      message = getMessage(await response.json()) ?? message
    } catch {
      // Keep the status-based message when an error body is unavailable.
    }
    throw new ApiRequestError(message, response.status)
  }

  return (await response.json()) as T
}

async function getRepositoryPage(page: number, signal?: AbortSignal): Promise<RepositoryPage> {
  const query = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) })
  return getJson<RepositoryPage>(`/repositories?${query.toString()}`, signal)
}

export async function getRepositories(signal?: AbortSignal): Promise<Repository[]> {
  const firstPage = await getRepositoryPage(0, signal)
  const laterPages = await Promise.all(
    Array.from({ length: Math.max(0, firstPage.totalPages - 1) }, (_, index) =>
      getRepositoryPage(index + 1, signal),
    ),
  )
  return [firstPage, ...laterPages].flatMap((page) => page?.content ?? [])
}

export function getDatasetSummary(signal?: AbortSignal): Promise<DatasetSummary> {
  return getJson<DatasetSummary>('/research/dataset-summary', signal)
}

export function getRepositoryDetail(repositoryId: number, signal?: AbortSignal): Promise<RepositoryDetail> {
  return getJson<RepositoryDetail>(`/repositories/${repositoryId}`, signal)
}

export function getRepositoryMetrics(repositoryId: number, signal?: AbortSignal): Promise<RepositoryMetrics> {
  return getJson<RepositoryMetrics>(`/repositories/${repositoryId}/metrics`, signal)
}

export function getRepositoryComparison(repositoryIds: number[], signal?: AbortSignal): Promise<RepositoryComparison> {
  const query = new URLSearchParams({ ids: repositoryIds.join(',') })
  return getJson<RepositoryComparison>(`/compare?${query.toString()}`, signal)
}

export function getPredictionHistory(repositoryId: number, signal?: AbortSignal): Promise<PredictionHistory> {
  return getJson<PredictionHistory>(`/repositories/${repositoryId}/predictions`, signal)
}

export async function getLatestPrediction(repositoryId: number, signal?: AbortSignal): Promise<PredictionDetail | null> {
  try {
    return await getJson<PredictionDetail>(`/repositories/${repositoryId}/predictions/latest`, signal)
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) return null
    throw error
  }
}

export function getResearchModels(signal?: AbortSignal): Promise<ModelPage> {
  return getJson<ModelPage>('/research/models?page=0&pageSize=200', signal)
}

async function getEvaluationPage(page: number, signal?: AbortSignal): Promise<EvaluationPage> {
  return getJson<EvaluationPage>(`/research/evaluations?page=${page}&pageSize=200`, signal)
}

export async function getAllEvaluations(signal?: AbortSignal): Promise<Evaluation[]> {
  const firstPage = await getEvaluationPage(0, signal)
  const laterPages = await Promise.all(
    Array.from({ length: Math.max(0, firstPage.totalPages - 1) }, (_, index) =>
      getEvaluationPage(index + 1, signal),
    ),
  )
  return [firstPage, ...laterPages].flatMap((page) => page?.content ?? [])
}

export function getFeatureImportance(modelVersionId: number, signal?: AbortSignal): Promise<FeatureImportancePage> {
  const query = new URLSearchParams({ modelVersionId: String(modelVersionId), page: '0', pageSize: '200' })
  return getJson<FeatureImportancePage>(`/research/feature-importance?${query.toString()}`, signal)
}

export function getLabelDefinition(signal?: AbortSignal): Promise<LabelDefinition> {
  return getJson<LabelDefinition>('/research/label-definition', signal)
}
