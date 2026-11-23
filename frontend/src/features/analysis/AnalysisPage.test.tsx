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
    fireEvent.change(screen.getByLabelText('GitHub repository'), { target: { value: 'acme/project' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analyze' }))

    expect(await screen.findByText(/61.0%/)).toBeInTheDocument()
    expect(screen.getByText('acme/project')).toBeInTheDocument()
    expect(screen.getByText(/rolling 180 day observation/)).toBeInTheDocument()
    expect(screen.getByText(/commits 30d: increases risk \(\+12.0 percentage points\)/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('7 / 300')).toBeInTheDocument())
  })

  it('explains when the per-IP submission limit is reached', async () => {
    server.use(http.post('http://localhost:8080/api/v1/analyses', () => HttpResponse.json(
      { timestamp: '2026-11-23T00:00:00Z', status: 429, code: 'submission_limit', message: 'The hourly submission limit has been reached. Try again later.', path: '/api/v1/analyses' },
      { status: 429 },
    )))
    renderPage()
    fireEvent.change(screen.getByLabelText('GitHub repository'), { target: { value: 'acme/project' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analyze' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('hourly submission limit')
  })
})
