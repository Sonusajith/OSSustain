import { useEffect, useState } from 'react'

import { usePublicRepository, usePublicRepositorySearch } from '../../api/queries'
import { GitHubSearchError, parseRepositoryInput, type PublicGitHubRepository } from '../../api/githubRepositories'

interface RepositoryDiscoveryProps {
  selectedRepository: PublicGitHubRepository | null
  onSelect: (repository: PublicGitHubRepository) => void
  onClear: () => void
}

function repositorySummary(repository: PublicGitHubRepository) {
  return [repository.language, `${repository.stargazers_count.toLocaleString()} stars`, `${repository.forks_count.toLocaleString()} forks`]
    .filter(Boolean)
    .join(' · ')
}

function GitHubErrorMessage({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const rateLimitError = error instanceof GitHubSearchError && error.retryAt
  return (
    <div className="repository-discovery-error" role="alert">
      <p>{error.message}</p>
      {rateLimitError && <p>Try again after {new Date(rateLimitError).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}.</p>}
      <button className="secondary-button" type="button" onClick={onRetry}>Retry</button>
    </div>
  )
}

function RepositoryCard({ repository, onSelect, action }: {
  repository: PublicGitHubRepository
  onSelect: (repository: PublicGitHubRepository) => void
  action: string
}) {
  return (
    <article className="discovered-repository">
      <div>
        <h3>{repository.full_name}</h3>
        <p className="repository-summary">{repositorySummary(repository)}</p>
        {repository.description && <p className="repository-description">{repository.description}</p>}
        {repository.archived && <p className="repository-archived">This repository is archived.</p>}
      </div>
      <button className="secondary-button" type="button" onClick={() => onSelect(repository)}>{action}</button>
    </article>
  )
}

export function RepositoryDiscovery({ selectedRepository, onSelect, onClear }: RepositoryDiscoveryProps) {
  const [input, setInput] = useState('')
  const [debouncedInput, setDebouncedInput] = useState('')
  const parsed = parseRepositoryInput(input)
  const debouncedParsed = parseRepositoryInput(debouncedInput)
  const isSearching = parsed.kind === 'search'
  const searchQuery = debouncedParsed.kind === 'search' && isSearching ? debouncedParsed.query : ''
  const search = usePublicRepositorySearch(searchQuery, searchQuery.length >= 2 && !selectedRepository)
  const directInput = parsed.kind === 'lookup' ? parsed : null
  const lookup = usePublicRepository(directInput?.owner ?? '', directInput?.repository ?? '', Boolean(directInput && !selectedRepository))

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedInput(input), 350)
    return () => window.clearTimeout(timer)
  }, [input])

  if (selectedRepository) {
    return (
      <section className="repository-selection" aria-label="Selected repository">
        <p className="eyebrow">Selected public repository</p>
        <h2>{selectedRepository.full_name}</h2>
        <p>{repositorySummary(selectedRepository)}</p>
        {selectedRepository.description && <p>{selectedRepository.description}</p>}
        <div className="repository-selection-actions">
          <a href={selectedRepository.html_url} target="_blank" rel="noreferrer">View on GitHub</a>
          <button className="secondary-button" type="button" onClick={onClear}>Choose a different repository</button>
        </div>
      </section>
    )
  }

  const changedDuringDebounce = parsed.kind === 'search' && (debouncedParsed.kind !== 'search' || debouncedParsed.query !== parsed.query)
  const hasSearchText = input.trim().length > 0

  return (
    <section className="repository-discovery" aria-labelledby="repository-discovery-heading">
      <label htmlFor="repository-discovery-input">Search GitHub or paste a repository URL</label>
      <input
        id="repository-discovery-input"
        autoComplete="off"
        value={input}
        onChange={(event) => setInput(event.target.value)}
        placeholder="Search by name, owner/repository, or https://github.com/..."
        aria-describedby="repository-discovery-help"
        aria-controls="repository-discovery-results"
      />
      <p id="repository-discovery-help">Public repositories only. Search is unauthenticated, rate limited by GitHub, and sends no GitHub token from your browser.</p>
      <div id="repository-discovery-results" className="repository-discovery-results" aria-live="polite" aria-busy={changedDuringDebounce || search.isFetching || lookup.isFetching}>
        {parsed.kind === 'invalid' && hasSearchText && <p className="repository-discovery-hint">{parsed.message}</p>}
        {isSearching && input.trim().length < 2 && <p className="repository-discovery-hint">Enter at least two characters to search.</p>}
        {changedDuringDebounce && <p role="status">Waiting to search GitHub…</p>}
        {!changedDuringDebounce && search.isFetching && <p role="status">Searching public GitHub repositories…</p>}
        {!changedDuringDebounce && search.isError && <GitHubErrorMessage error={search.error} onRetry={() => void search.refetch()} />}
        {!changedDuringDebounce && search.isSuccess && search.data.length === 0 && <p>No public repositories matched. Try a different name.</p>}
        {!changedDuringDebounce && search.data?.map((repository) => (
          <RepositoryCard key={repository.id} repository={repository} onSelect={onSelect} action="Select repository" />
        ))}
        {directInput && lookup.isFetching && <p role="status">Checking this public repository on GitHub…</p>}
        {directInput && lookup.isError && <GitHubErrorMessage error={lookup.error} onRetry={() => void lookup.refetch()} />}
        {directInput && lookup.data && <RepositoryCard repository={lookup.data} onSelect={onSelect} action="Use this repository" />}
      </div>
      <h2 id="repository-discovery-heading" className="visually-hidden">Repository search results</h2>
    </section>
  )
}
