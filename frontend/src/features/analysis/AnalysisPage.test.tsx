import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AnalysisPage } from './AnalysisPage'
import { server } from '../../test/server'

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter><AnalysisPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AnalysisPage', () => {
  it('submits a public repository and displays the completed result and limitations', async () => {
    server.use(
      http.get('https://api.github.com/repos/acme/project', () => HttpResponse.json({
        id: 1, full_name: 'acme/project', html_url: 'https://github.com/acme/project', description: 'Example project',
        stargazers_count: 1234, forks_count: 56, language: 'TypeScript', archived: false,
      })),
      http.post('http://localhost:8080/api/v1/analyses', () => HttpResponse.json({
        id: '11111111-1111-4111-8111-111111111111', repository: 'acme/project', status: 'queued',
        requestsUsed: 0, errorCode: null, createdAt: '2026-11-23T00:00:00Z', startedAt: null,
        finishedAt: null, result: null,
      }, { status: 202 })),
      http.get('http://localhost:8080/api/v1/analyses/:id', () => HttpResponse.json({
        id: '11111111-1111-4111-8111-111111111111', repository: 'acme/project', status: 'succeeded',
        requestsUsed: 7, errorCode: null, createdAt: '2026-11-23T00:00:00Z',
        startedAt: '2026-11-23T00:00:01Z', finishedAt: '2026-11-23T00:00:05Z',
        result: {
          modelVersionId: 4, probability: 0.61, riskCategory: 'medium', predictionDate: '2026-11-23',
          featureSet: 'extended', algorithm: 'random_forest', limitations: ['rolling_180_day_observation'],
          features: { commits_30d: 8 },
          indicators: [{ feature_name: 'commits_30d', direction: 'increases_risk', probability_delta: 0.12 }],
          requestsUsed: 7, completedAt: '2026-11-23T00:00:05Z',
        },
      })),
    )

    renderPage()
    fireEvent.change(screen.getByLabelText('Search GitHub or paste a repository URL'), { target: { value: 'https://github.com/acme/project' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Use this repository' }))
    fireEvent.click(screen.getByRole('button', { name: 'Analyze acme/project' }))

    expect(await screen.findByText(/61.0%/)).toBeInTheDocument()
    expect(screen.getAllByText('acme/project').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/rolling 180 day observation/)).toBeInTheDocument()
    expect(screen.getByText(/commits 30d: increases risk \(\+12.0 percentage points\)/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('7 / 300')).toBeInTheDocument())
  })

  it('explains when the per-IP submission limit is reached', async () => {
    server.use(
      http.get('https://api.github.com/repos/acme/project', () => HttpResponse.json({
        id: 1, full_name: 'acme/project', html_url: 'https://github.com/acme/project', description: null,
        stargazers_count: 4, forks_count: 0, language: null, archived: false,
      })),
      http.post('http://localhost:8080/api/v1/analyses', () => HttpResponse.json(
        { timestamp: '2026-11-23T00:00:00Z', status: 429, code: 'submission_limit', message: 'The hourly submission limit has been reached. Try again later.', path: '/api/v1/analyses' },
        { status: 429 },
      )),
    )
    renderPage()
    fireEvent.change(screen.getByLabelText('Search GitHub or paste a repository URL'), { target: { value: 'acme/project' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Use this repository' }))
    fireEvent.click(screen.getByRole('button', { name: 'Analyze acme/project' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('hourly submission limit')
  })

  it('searches public repositories and preserves the selected identity for analysis', async () => {
    server.use(
      http.get('https://api.github.com/search/repositories', ({ request }) => {
        expect(new URL(request.url).searchParams.get('q')).toBe('acme in:name')
        return HttpResponse.json({ items: [{
          id: 3, full_name: 'acme/widget', html_url: 'https://github.com/acme/widget', description: 'A widget',
          stargazers_count: 88, forks_count: 9, language: 'Rust', archived: false,
        }] })
      }),
      http.post('http://localhost:8080/api/v1/analyses', async ({ request }) => {
        expect(await request.json()).toEqual({ repository: 'acme/widget' })
        return HttpResponse.json({
          id: '22222222-2222-4222-8222-222222222222', repository: 'acme/widget', status: 'queued',
          requestsUsed: 0, errorCode: null, createdAt: '2026-11-23T00:00:00Z', startedAt: null,
          finishedAt: null, result: null,
        }, { status: 202 })
      }),
      http.get('http://localhost:8080/api/v1/analyses/:id', () => HttpResponse.json({
        id: '22222222-2222-4222-8222-222222222222', repository: 'acme/widget', status: 'queued',
        requestsUsed: 0, errorCode: null, createdAt: '2026-11-23T00:00:00Z', startedAt: null,
        finishedAt: null, result: null,
      })),
    )
    renderPage()
    fireEvent.change(screen.getByLabelText('Search GitHub or paste a repository URL'), { target: { value: 'acme' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Select repository' }))
    expect(screen.getByRole('heading', { name: 'acme/widget' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Analyze acme/widget' }))
    expect(await screen.findByText('Analysis is queued. This page will update automatically.')).toBeInTheDocument()
  })

  it('shows an empty state when GitHub finds no public repositories', async () => {
    server.use(http.get('https://api.github.com/search/repositories', () => HttpResponse.json({ items: [] })))
    renderPage()
    fireEvent.change(screen.getByLabelText('Search GitHub or paste a repository URL'), { target: { value: 'no-such-project' } })
    expect(await screen.findByText('No public repositories matched. Try a different name.')).toBeInTheDocument()
  })

  it('explains GitHub search rate limits and when to try again', async () => {
    const reset = String(Math.floor(Date.now() / 1000) - 1)
    server.use(http.get('https://api.github.com/search/repositories', () => HttpResponse.json(
      { message: 'API rate limit exceeded' },
      { status: 403, headers: { 'x-ratelimit-remaining': '0', 'x-ratelimit-reset': reset } },
    )))
    renderPage()
    fireEvent.change(screen.getByLabelText('Search GitHub or paste a repository URL'), { target: { value: 'rate-limit-test' } })
    expect(await screen.findByRole('alert')).toHaveTextContent('GitHub search is rate limited')
    expect(screen.getByRole('alert')).toHaveTextContent('Try again after')
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('explains when a pasted repository is missing or private', async () => {
    server.use(http.get('https://api.github.com/repos/private/repository', () => HttpResponse.json(
      { message: 'Not Found' }, { status: 404 },
    )))
    renderPage()
    fireEvent.change(screen.getByLabelText('Search GitHub or paste a repository URL'), { target: { value: 'private/repository' } })
    expect(await screen.findByRole('alert')).toHaveTextContent('Repository not found')
    expect(screen.getByRole('alert')).toHaveTextContent('make sure it is public')
  })

  it('lets the user retry a failed analysis for the selected repository', async () => {
    let submissions = 0
    server.use(
      http.get('https://api.github.com/repos/acme/project', () => HttpResponse.json({
        id: 1, full_name: 'acme/project', html_url: 'https://github.com/acme/project', description: null,
        stargazers_count: 4, forks_count: 0, language: null, archived: false,
      })),
      http.post('http://localhost:8080/api/v1/analyses', () => {
        submissions += 1
        return HttpResponse.json({
          id: `${submissions}1111111-1111-4111-8111-111111111111`, repository: 'acme/project', status: 'queued',
          requestsUsed: 0, errorCode: null, createdAt: '2026-11-23T00:00:00Z', startedAt: null,
          finishedAt: null, result: null,
        }, { status: 202 })
      }),
      http.get('http://localhost:8080/api/v1/analyses/:id', () => HttpResponse.json({
        id: '11111111-1111-4111-8111-111111111111', repository: 'acme/project',
        status: submissions === 1 ? 'failed' : 'queued', requestsUsed: 3,
        errorCode: submissions === 1 ? 'repository_unavailable' : null,
        createdAt: '2026-11-23T00:00:00Z', startedAt: null, finishedAt: null, result: null,
      })),
    )
    renderPage()
    fireEvent.change(screen.getByLabelText('Search GitHub or paste a repository URL'), { target: { value: 'acme/project' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Use this repository' }))
    fireEvent.click(screen.getByRole('button', { name: 'Analyze acme/project' }))
    expect(await screen.findByRole('button', { name: 'Try this repository again' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Try this repository again' }))
    await waitFor(() => expect(submissions).toBe(2))
    expect(await screen.findByText('Analysis is queued. This page will update automatically.')).toBeInTheDocument()
  })
})
