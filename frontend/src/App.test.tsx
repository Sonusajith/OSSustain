import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { App } from './App'
import { server } from './test/server'

const repositoryRows = [
  {
    id: 11,
    fullName: 'acme/alpha',
    owner: 'acme',
    name: 'alpha',
    sizeGroup: 'small',
    stars: 1200,
    dataQualityFlags: ['low_activity'],
    latestProbability: 0.71,
    latestRiskCategory: 'high',
    predictionDate: '2025-01-01',
  },
  {
    id: 12,
    fullName: 'acme/beta',
    owner: 'acme',
    name: 'beta',
    sizeGroup: 'medium',
    stars: 850,
    dataQualityFlags: [],
    latestProbability: 0.43,
    latestRiskCategory: 'medium',
    predictionDate: '2025-01-01',
  },
  {
    id: 13,
    fullName: 'other/gamma',
    owner: 'other',
    name: 'gamma',
    sizeGroup: 'large',
    stars: 400,
    dataQualityFlags: [],
    latestProbability: null,
    latestRiskCategory: null,
    predictionDate: null,
  },
]

const datasetSummary = {
  id: 7,
  versionHash: 'abcdef0123456789abcdef0123456789',
  cohortName: 'ossustain-study',
  createdAt: '2025-02-01T00:00:00Z',
  summary: {
    overall: { snapshots: 138 },
    by_period: { '2024-01-01': {}, '2025-01-01': {} },
  },
}

function installApi(repositories = repositoryRows) {
  server.use(
    http.get('*/api/v1/repositories', () =>
      HttpResponse.json({
        content: repositories,
        page: 0,
        pageSize: 100,
        totalElements: repositories.length,
        totalPages: 1,
      }),
    ),
    http.get('*/api/v1/research/dataset-summary', () => HttpResponse.json(datasetSummary)),
  )
}

function LocationOutput() {
  const location = useLocation()
  return <output aria-label="Current URL query">{location.search}</output>
}

function renderApp(entry = '/') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, retryDelay: 0, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[entry]}>
        <App />
        <LocationOutput />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Cohort Overview', () => {
  it('loads the live cohort and dataset summary', async () => {
    installApi()
    renderApp()

    expect(await screen.findByRole('heading', { name: 'Cohort overview' })).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: /acme\/alpha/i })).toHaveAttribute('href', '/repositories/11')
    expect(screen.getByText('High risk')).toBeInTheDocument()
    expect(screen.getByText('71.0%')).toBeInTheDocument()
    expect(screen.getByText('#7')).toBeInTheDocument()
    expect(screen.getByText('2024-01-01 – 2025-01-01')).toBeInTheDocument()
    expect(screen.getByText('Showing', { exact: false })).toHaveTextContent('Showing 1–3 of 3 repositories')
  })

  it('shows a loading state while both API requests are pending', async () => {
    server.use(
      http.get('*/api/v1/repositories', async () => {
        await delay(500)
        return HttpResponse.json({ content: [], page: 0, pageSize: 100, totalElements: 0, totalPages: 0 })
      }),
      http.get('*/api/v1/research/dataset-summary', async () => {
        await delay(500)
        return HttpResponse.json(datasetSummary)
      }),
    )
    renderApp()

    expect(screen.getByText('Loading repository and dataset information…')).toBeInTheDocument()
    expect(screen.getByRole('main')).toHaveAttribute('aria-busy', 'true')
  })

  it('shows an error and retries successfully when requested', async () => {
    const user = userEvent.setup()
    server.use(
      http.get('*/api/v1/repositories', () => HttpResponse.json({ message: 'API is offline.' }, { status: 503 })),
      http.get('*/api/v1/research/dataset-summary', () => HttpResponse.json({ message: 'API is offline.' }, { status: 503 })),
    )
    renderApp()

    expect(await screen.findByRole('heading', { name: 'We couldn’t load the cohort' })).toBeInTheDocument()
    expect(screen.getByText('API is offline.')).toBeInTheDocument()
    server.use(
      http.get('*/api/v1/repositories', () =>
        HttpResponse.json({ content: repositoryRows, page: 0, pageSize: 100, totalElements: repositoryRows.length, totalPages: 1 }),
      ),
      http.get('*/api/v1/research/dataset-summary', () => HttpResponse.json(datasetSummary)),
    )
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('link', { name: /acme\/alpha/i })).toBeInTheDocument()
  })

  it('shows an explicit empty state for a dataset with no repositories', async () => {
    installApi([])
    renderApp()

    expect(await screen.findByRole('heading', { name: 'No repositories in this dataset' })).toBeInTheDocument()
  })

  it('restores query filters from the URL and filters flagged records', async () => {
    installApi()
    renderApp('/?q=alpha&risk=high&quality=flagged')

    expect(await screen.findByRole('link', { name: /acme\/alpha/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /acme\/beta/i })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Search repository')).toHaveValue('alpha')
    expect(screen.getByLabelText('Risk category')).toHaveValue('high')
    expect(screen.getByLabelText('Data quality')).toHaveValue('flagged')
  })

  it('updates URL filter state, resets the page, and sorts through table headings', async () => {
    const user = userEvent.setup()
    installApi()
    renderApp('/?page=1')

    await screen.findByRole('link', { name: /acme\/alpha/i })
    await user.selectOptions(screen.getByLabelText('Risk category'), 'medium')
    await waitFor(() => expect(screen.getByLabelText('Current URL query')).toHaveTextContent('risk=medium'))
    expect(screen.getByLabelText('Current URL query')).not.toHaveTextContent('page=1')
    expect(screen.getByRole('link', { name: /acme\/beta/i })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /repository/i }))
    expect(screen.getByLabelText('Current URL query')).toHaveTextContent('sort=fullName')
    expect(screen.getByLabelText('Current URL query')).toHaveTextContent('direction=desc')
  })

  it('paginates the filtered results and keeps the page in the URL', async () => {
    const twelveRows = [
      ...repositoryRows,
      ...Array.from({ length: 9 }, (_, index) => ({
        ...repositoryRows[0],
        id: 20 + index,
        fullName: `more/repository-${index + 1}`,
        dataQualityFlags: [],
      })),
    ]
    installApi(twelveRows)
    renderApp()

    expect(await screen.findByRole('link', { name: /acme\/alpha/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByLabelText('Current URL query')).toHaveTextContent('page=1')
    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
  })
})
