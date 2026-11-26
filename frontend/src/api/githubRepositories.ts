export interface PublicGitHubRepository {
  id: number
  full_name: string
  html_url: string
  description: string | null
  stargazers_count: number
  forks_count: number
  language: string | null
  archived: boolean
}

export class GitHubSearchError extends Error {
  constructor(message: string, readonly retryAt?: number) {
    super(message)
    this.name = 'GitHubSearchError'
  }
}

export type RepositoryInput =
  | { kind: 'search'; query: string }
  | { kind: 'lookup'; owner: string; repository: string }
  | { kind: 'invalid'; message: string }

const GITHUB_API = 'https://api.github.com'
const GITHUB_API_VERSION = '2022-11-28'
const REPOSITORY_PART = /^[A-Za-z0-9_.-]{1,100}$/
let githubSearchBlockedUntil = 0

export function parseRepositoryInput(value: string): RepositoryInput {
  const input = value.trim()
  if (!input) return { kind: 'invalid', message: 'Enter a repository name, owner/repository, or GitHub URL.' }

  let path = input
  if (/^https?:\/\//i.test(input)) {
    try {
      const url = new URL(input)
      if (url.hostname.toLowerCase() !== 'github.com' || url.username || url.password) {
        return { kind: 'invalid', message: 'Use a repository URL from github.com.' }
      }
      path = url.pathname.replace(/^\/+|\/+$/g, '')
    } catch {
      return { kind: 'invalid', message: 'That GitHub URL is not valid.' }
    }
  } else if (input.includes('://') || /(^|\s)github\.com\//i.test(input)) {
    return { kind: 'invalid', message: 'Paste a full https://github.com/owner/repository URL.' }
  }

  if (path.includes('/')) {
    const parts = path.split('/')
    const owner = parts[0]
    const repository = parts[1]?.replace(/\.git$/i, '')
    if (parts.length !== 2 || !owner || !repository || !REPOSITORY_PART.test(owner) || !REPOSITORY_PART.test(repository)) {
      return { kind: 'invalid', message: 'Enter owner/repository or a GitHub repository URL with exactly two path parts.' }
    }
    return { kind: 'lookup', owner, repository }
  }

  if (input.length < 2) return { kind: 'invalid', message: 'Enter at least two characters to search GitHub.' }
  return { kind: 'search', query: input }
}

export async function searchPublicRepositories(query: string, signal?: AbortSignal): Promise<PublicGitHubRepository[]> {
  const parameters = new URLSearchParams({ q: `${query} in:name`, per_page: '8', sort: 'stars', order: 'desc' })
  const response = await githubRequest<{ items: PublicGitHubRepository[] }>(`/search/repositories?${parameters}`, signal)
  return response.items
}

export function getPublicRepository(owner: string, repository: string, signal?: AbortSignal): Promise<PublicGitHubRepository> {
  return githubRequest<PublicGitHubRepository>(`/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}`, signal)
}

async function githubRequest<T>(path: string, signal?: AbortSignal): Promise<T> {
  const isSearchRequest = path.startsWith('/search/')
  if (isSearchRequest && Date.now() < githubSearchBlockedUntil) {
    throw new GitHubSearchError('GitHub search is rate limited. Wait before searching again.', githubSearchBlockedUntil)
  }

  let response: Response
  try {
    response = await fetch(`${GITHUB_API}${path}`, {
      headers: { Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': GITHUB_API_VERSION },
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new GitHubSearchError('Could not reach GitHub. Check your connection and try again.')
  }

  const remaining = response.headers.get('x-ratelimit-remaining')
  const resetHeader = response.headers.get('x-ratelimit-reset')
  const resetSeconds = resetHeader ? Number(resetHeader) : Number.NaN
  if (isSearchRequest && remaining === '0') {
    githubSearchBlockedUntil = Number.isFinite(resetSeconds) ? resetSeconds * 1000 : Date.now() + 60_000
  }

  if (!response.ok) {
    const retryHeader = response.headers.get('retry-after')
    const retrySeconds = retryHeader ? Number(retryHeader) : Number.NaN
    const retryAt = remaining === '0' && Number.isFinite(resetSeconds) ? resetSeconds * 1000
      : Number.isFinite(retrySeconds) ? Date.now() + retrySeconds * 1000
        : undefined

    if (response.status === 403 || response.status === 429) {
      if (remaining === '0' || response.status === 429 || retryHeader) {
        if (isSearchRequest && retryAt) githubSearchBlockedUntil = Math.max(githubSearchBlockedUntil, retryAt)
        throw new GitHubSearchError('GitHub search is rate limited. Wait before searching again.', retryAt)
      }
      throw new GitHubSearchError('GitHub could not complete the search. Try again shortly.')
    }
    if (response.status === 404) throw new GitHubSearchError('Repository not found. Check the owner and name, and make sure it is public.')
    if (response.status === 422) throw new GitHubSearchError('GitHub could not process that search. Try a shorter repository name.')
    throw new GitHubSearchError(`GitHub search failed (${response.status}). Try again.`)
  }
  return response.json() as Promise<T>
}
