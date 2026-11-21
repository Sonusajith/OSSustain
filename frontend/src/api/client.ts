import type { components, paths } from './generated'

export type Repository = components['schemas']['RepositorySummary']
export type RepositoryPage = paths['/repositories']['get']['responses'][200]['content']['application/json']
export type DatasetSummary = paths['/research/dataset-summary']['get']['responses'][200]['content']['application/json']

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
  return [firstPage, ...laterPages].flatMap((page) => page.content)
}

export function getDatasetSummary(signal?: AbortSignal): Promise<DatasetSummary> {
  return getJson<DatasetSummary>('/research/dataset-summary', signal)
}
