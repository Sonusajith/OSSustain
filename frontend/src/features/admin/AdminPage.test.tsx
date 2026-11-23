import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AdminPage } from './AdminPage'
import { server } from '../../test/server'

function renderAdmin() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}><MemoryRouter><AdminPage /></MemoryRouter></QueryClientProvider>)
}

describe('AdminPage', () => {
  it('creates an account and presents the one-time password', async () => {
    const user = userEvent.setup()
    server.use(
      http.get('http://localhost:8080/api/v1/admin/users', () => HttpResponse.json({ content: [], page: 0, pageSize: 100, totalElements: 0 })),
      http.get('http://localhost:8080/api/v1/admin/analyses', () => HttpResponse.json({ content: [], page: 0, pageSize: 100, totalElements: 0 })),
      http.post('http://localhost:8080/api/v1/admin/users', () => HttpResponse.json({
        user: { id: 4, username: 'researcher-one', roles: ['RESEARCHER'], enabled: true, mustChangePassword: true, createdAt: '2026-11-23T00:00:00Z' },
        temporaryPassword: 'one-time-password',
      }, { status: 201 })),
    )
    renderAdmin()
    await user.type(screen.getByLabelText('Username'), 'researcher-one')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('one-time-password')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('must change it at first sign-in')
  })

  it('shows loading and retry for administrator data', async () => {
    server.use(http.get('http://localhost:8080/api/v1/admin/users', () => HttpResponse.json(
      { message: 'Admin data unavailable.' }, { status: 503 },
    )))
    renderAdmin()
    expect(await screen.findByText('Admin data unavailable.', {}, { timeout: 3000 })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry accounts' }))
  })
})
